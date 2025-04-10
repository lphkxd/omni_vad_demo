import os
import base64
import struct
import time
from agno.agent import Agent
from openai import OpenAI
from typing import Dict, Any
from io import BytesIO  # 添加BytesIO导入

# 配置OpenAI客户端
def get_openai_client():
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

# 预缓存常用采样率的WAV头
WAV_HEADERS = {}

def generate_wav_header(sample_rate: int = 24000) -> bytes:
    """生成WAV文件头"""
    # WAV文件头格式
    # RIFF header
    riff_header = b'RIFF'
    file_size_placeholder = struct.pack('<I', 0)  # 占位，实际使用时会替换
    wave_header = b'WAVE'
    
    # fmt chunk
    fmt_header = b'fmt '
    fmt_chunk_size = 16
    audio_format = 1  # PCM
    num_channels = 1  # 单声道
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    
    # data chunk
    data_header = b'data'
    data_chunk_size_placeholder = struct.pack('<I', 0)  # 占位，实际使用时会替换
    
    # 构建WAV头部分（不包含文件大小和数据大小）
    header = (
        riff_header +
        file_size_placeholder +
        wave_header +
        fmt_header +
        struct.pack('<I', fmt_chunk_size) +
        struct.pack('<H', audio_format) +
        struct.pack('<H', num_channels) +
        struct.pack('<I', sample_rate) +
        struct.pack('<I', byte_rate) +
        struct.pack('<H', block_align) +
        struct.pack('<H', bits_per_sample) +
        data_header +
        data_chunk_size_placeholder
    )
    
    return header

# 初始化常用采样率的WAV头缓存
for sr in [24000, 16000, 44100, 48000]:
    WAV_HEADERS[sr] = generate_wav_header(sr)

def add_wav_header(audio_data: bytes, sample_rate: int = 24000) -> bytes:
    """添加WAV文件头，使用预缓存的头部"""
    # 如果没有预缓存当前采样率的头部，生成一个
    if sample_rate not in WAV_HEADERS:
        WAV_HEADERS[sample_rate] = generate_wav_header(sample_rate)
    
    # 获取预缓存的头部
    header_template = WAV_HEADERS[sample_rate]
    
    # 计算文件大小和数据大小
    data_chunk_size = len(audio_data)
    file_size = data_chunk_size + 36  # 文件总长度减去8字节
    
    # 创建包含正确大小信息的头部
    header = bytearray(header_template)
    struct.pack_into('<I', header, 4, file_size)  # 在位置4写入文件大小
    struct.pack_into('<I', header, 40, data_chunk_size)  # 在位置40写入数据大小
    
    return bytes(header) + audio_data

# 音频编码函数
def encode_audio(audio_data):
    """将音频数据编码为base64字符串"""
    return base64.b64encode(audio_data).decode("utf-8")

# 创建Agent类
class AudioProcessingAgent(Agent):
    name = "audio_processing_agent"
    description = "处理音频内容并调用大模型进行分析"
    
    def __init__(self):
        super().__init__()
        self.client = get_openai_client()
        # 初始化聊天历史记录
        self.chat_history = []
        # 最大保存的对话轮数
        self.max_history = 5  # 保持5轮对话历史
    
    def process_audio(self, audio_data: bytes, text_prompt: str = "", audio_format: str = "webm") -> Dict[str, Any]:
        """处理音频并调用模型获取回复
        
        Args:
            audio_data: 音频数据字节
            text_prompt: 提示文本
            audio_format: 音频格式，可以是'webm'或'wav'等
        
        Returns:
            包含文本和音频回复的字典
        """
        start_time = time.time()
        try:
            # api_server.py中已经处理了base64解码，直接使用传入的音频数据
            # 移除重复的base64编码操作
            print(f"发送请求到模型，音频大小: {len(audio_data)} 字节，格式: {audio_format}")
            
            # 构建消息列表，包含历史记录
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "你是一个友好、专业的AI助手。请用中文回答问题，保持对话的连贯性。"}],
                },
            ]
            
            # 添加历史消息
            for msg in self.chat_history:
                messages.append(msg)
                
            # 添加当前用户消息
            # 这里仍需要编码，因为API需要base64格式
            base64_audio = base64.b64encode(audio_data).decode("utf-8")
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": f"data:;base64,{base64_audio}",
                            "format": audio_format,
                        },
                    },
                    {"type": "text", "text": text_prompt},
                ],
            })
            
            # 调用模型
            model_start = time.time()
            completion = self.client.chat.completions.create(
                model="qwen-omni-turbo",
                messages=messages,
                modalities=["text", "audio"],
                audio={"voice": "Chelsie", "format": "wav"},
                stream=True,
                stream_options={"include_usage": True},
            )
            
            # 处理响应
            response = {"text": "", "audio": None, "usage": None}
            audio_chunks = []  # 存储原始音频数据块
            transcript_text = ""
            audio_chunks_count = 0
            audio_total_size = 0
            
            try:
                for chunk in completion:
                    if chunk.choices:
                        if hasattr(chunk.choices[0].delta, "audio"):
                            try:
                                # 获取音频数据
                                audio_data = chunk.choices[0].delta.audio.get("data")
                                if audio_data:
                                    # 解码并保存原始音频数据
                                    try:
                                        audio_chunk = base64.b64decode(audio_data)
                                        audio_chunks.append(audio_chunk)
                                        audio_chunks_count += 1
                                        audio_total_size += len(audio_chunk)
                                        # 简化日志，不再输出每个音频块
                                    except Exception as e:
                                        print(f"解码音频数据块时出错: {e}")
                                
                                # 获取转录文本
                                transcript = chunk.choices[0].delta.audio.get("transcript")
                                if transcript:
                                    transcript_text += transcript
                                    # 简化日志，不再输出每个转录片段
                            except Exception as e:
                                print(f"处理音频数据时出错: {e}")
                        elif hasattr(chunk.choices[0].delta, "content"):
                            content = chunk.choices[0].delta.content
                            if content:
                                response["text"] += str(content)
                                # 简化日志，不再输出每个文本片段
                    elif hasattr(chunk, "usage"):
                        response["usage"] = chunk.usage
                        print(f"收到用量统计: {chunk.usage}")
                        break  # 收到用量统计后结束循环
            except Exception as e:
                print(f"处理响应时出错: {e}")
                raise
            
            # 在处理完成后输出统计信息
            print(f"共收到{audio_chunks_count}个音频数据块，总大小: {audio_total_size} 字节")
            
            model_time = time.time() - model_start
            print(f"模型处理耗时: {model_time:.2f}秒")

            # 处理音频数据
            if audio_chunks:
                try:
                    # 优化音频数据处理，使用BytesIO减少内存使用
                    audio_process_start = time.time()
                    audio_buffer = BytesIO()
                    for chunk in audio_chunks:
                        audio_buffer.write(chunk)
                    raw_audio = audio_buffer.getvalue()
                    # 添加WAV头
                    wav_audio = add_wav_header(raw_audio)
                    # 编码为base64
                    response["audio"] = base64.b64encode(wav_audio).decode('utf-8')
                    audio_process_time = time.time() - audio_process_start
                    print(f"音频后处理耗时: {audio_process_time:.2f}秒")
                    print(f"最终音频数据大小: {len(wav_audio)} 字节")
                except Exception as e:
                    print(f"处理最终音频数据时出错: {e}")
            else:
                print("没有收集到任何音频数据")
            
            # 如果有转录文本但没有其他文本内容，使用转录文本
            if not response["text"] and transcript_text:
                response["text"] = transcript_text
                print(f"使用转录文本作为响应: {transcript_text}")
            
            # 更新对话历史
            if transcript_text:
                # 添加用户消息（使用转录的文本）
                self.chat_history.append({
                    "role": "user",
                    "content": [{"type": "text", "text": transcript_text}]
                })
            else:
                # 如果没有转录文本，使用提示文本
                self.chat_history.append({
                    "role": "user", 
                    "content": [{"type": "text", "text": text_prompt}]
                })
            
            # 添加助手回复
            self.chat_history.append({
                "role": "assistant",
                "content": [{"type": "text", "text": response["text"]}]
            })
            
            # 保持历史长度在限制范围内，超过5轮就抛弃前面的对话
            MAX_TEXT_LENGTH = 1000  # 每条消息最大字符数
            if len(self.chat_history) > self.max_history * 2:  # 每轮对话有2条消息（用户+助手）
                # 只保留最近的5轮对话
                self.chat_history = self.chat_history[-self.max_history*2:]
                print(f"对话历史超过{self.max_history}轮，已删除最早的对话")
            
            # 限制每条消息的文本长度以控制内存使用
            for msg in self.chat_history:
                if "content" in msg and isinstance(msg["content"], list):
                    for item in msg["content"]:
                        if item.get("type") == "text" and len(item.get("text", "")) > MAX_TEXT_LENGTH:
                            item["text"] = item["text"][:MAX_TEXT_LENGTH] + "..."
            
            total_time = time.time() - start_time
            print(f"总处理时间: {total_time:.2f}秒")
            print(f"最终文本响应: {response['text']}")
            print(f"当前对话历史数量: {len(self.chat_history)//2} 轮")
            
            return response
            
        except Exception as e:
            print(f"处理音频时出错: {e}")
            raise
            
    def clear_history(self):
        """清除对话历史"""
        self.chat_history = []
        print("对话历史已清除")

# 实例化Agent
audio_agent = AudioProcessingAgent()

# 如果直接运行此脚本，进行测试
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # 测试用例
    test_file = Path("welcome.mp3")
    if test_file.exists():
        with open(test_file, "rb") as audio_file:
            audio_data = audio_file.read()
            base64_audio = encode_audio(audio_data)
            result = audio_agent.process_audio(audio_data)
            print(f"文本回复: {result['text']}")
            if result['audio']:
                print(f"收到音频回复，大小: {len(result['audio'])} 字节")
            if result['usage']:
                print(f"用量统计: {result['usage']}")
    else:
        print(f"测试文件 {test_file} 不存在") 