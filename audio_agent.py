import os
import base64
import struct
import time
import json
import asyncio
from agno.agent import Agent
from openai import OpenAI
from typing import Dict, Any, AsyncGenerator, List, Union, Optional
from io import BytesIO  # 添加BytesIO导入

# 配置OpenAI客户端
def get_openai_client():
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

# 系统提示词
SYSTEM_PROMPT = """# 角色设定
你将扮演一个礼貌且乐于助人的人工电话销售客服，姓名：悠悠跑腿电话客服，年龄30岁，女，，专门为一家名为UU跑腿公司提供服务，主要通过电话引导未认证过的用户进行认证，语气沉稳专业，不要有AI语气、模拟真人自然对话。
你的专业是：悠悠跑腿电话客服 + 引导未认证的跑男账号进行认证 +鼓励跑男接单。

# 对话主题
- 邀请未认证的跑男积极进行认证。
- 鼓励跑男认证后多多接单。，不要重复用户的问话,模拟真实用户的口吻。不要有 aI 味。"""

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
        # 文本长度限制
        self.max_text_length = 1000  # 每条消息最大字符数
    
    def _prepare_messages(self, audio_data: bytes, text_prompt: str = "", audio_format: str = "webm") -> List[Dict[str, Any]]:
        """准备发送给模型的消息列表
        
        Args:
            audio_data: 音频数据字节
            text_prompt: 提示文本
            audio_format: 音频格式
            
        Returns:
            准备好的消息列表
        """
        # 构建消息列表，包含历史记录
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": SYSTEM_PROMPT}],
            },
        ]
        
        # 添加历史消息
        for msg in self.chat_history:
            messages.append(msg)
            
        # 添加当前用户消息
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
                # 只有当text_prompt不为空时才添加文本提示
                *([{"type": "text", "text": text_prompt}] if text_prompt.strip() else []),
            ],
        })
        
        return messages
    
    def _update_chat_history(self, user_text: str, assistant_text: str, text_prompt: str = ""):
        """更新聊天历史
        
        Args:
            user_text: 用户消息文本（转录或提示）
            assistant_text: 助手回复文本
            text_prompt: 原始提示文本
        """
        # 添加用户消息到历史
        if user_text:
            self.chat_history.append({
                "role": "user",
                "content": [{"type": "text", "text": user_text}]
            })
            print(f"添加用户文本到历史: {user_text}")
        elif text_prompt and text_prompt.strip():
            self.chat_history.append({
                "role": "user", 
                "content": [{"type": "text", "text": text_prompt}]
            })
            print(f"添加用户提示文本到历史: {text_prompt}")
        else:
            self.chat_history.append({
                "role": "user", 
                "content": [{"type": "text", "text": "(用户发送了一段音频)"}]
            })
            print("添加默认用户消息到历史")
            
        # 添加助手回复
        self.chat_history.append({
            "role": "assistant",
            "content": [{"type": "text", "text": assistant_text}]
        })
        
        # 保持历史长度在限制范围内
        if len(self.chat_history) > self.max_history * 2:  # 每轮对话有2条消息（用户+助手）
            # 只保留最近的对话
            self.chat_history = self.chat_history[-self.max_history*2:]
            print(f"对话历史超过{self.max_history}轮，已删除最早的对话")
        
        # 限制每条消息的文本长度以控制内存使用
        for msg in self.chat_history:
            if "content" in msg and isinstance(msg["content"], list):
                for item in msg["content"]:
                    if item.get("type") == "text" and len(item.get("text", "")) > self.max_text_length:
                        item["text"] = item["text"][:self.max_text_length] + "..."
    
    def process_audio(self, audio_data: bytes, text_prompt: str = "", audio_format: str = "webm") -> Dict[str, Any]:
        """处理音频并调用模型获取回复（同步方法）
        
        Args:
            audio_data: 音频数据字节
            text_prompt: 提示文本
            audio_format: 音频格式，可以是'webm'或'wav'等
        
        Returns:
            包含文本和音频回复的字典
        """
        start_time = time.time()
        try:
            print(f"发送请求到模型，音频大小: {len(audio_data)} 字节，格式: {audio_format}")
            
            # 准备消息
            messages = self._prepare_messages(audio_data, text_prompt, audio_format)
            
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
                                    except Exception as e:
                                        print(f"解码音频数据块时出错: {e}")
                                
                                # 获取转录文本
                                transcript = chunk.choices[0].delta.audio.get("transcript")
                                if transcript:
                                    transcript_text += transcript
                            except Exception as e:
                                print(f"处理音频数据时出错: {e}")
                        elif hasattr(chunk.choices[0].delta, "content"):
                            content = chunk.choices[0].delta.content
                            if content:
                                response["text"] += str(content)
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
            
            # 更新对话历史 - 选择合适的信息来源
            final_user_text = transcript_text if transcript_text else text_prompt
            self._update_chat_history(final_user_text, response["text"], text_prompt)
            
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

    async def stream_audio(self, audio_data: bytes, text_prompt: str = "", audio_format: str = "webm") -> AsyncGenerator[str, None]:
        """处理音频并以流式方式返回响应（异步流式方法）
        
        Args:
            audio_data: 音频数据字节
            text_prompt: 提示文本
            audio_format: 音频格式，可以是'webm'或'wav'等
        
        Yields:
            服务器发送的事件格式字符串，包含文本或音频数据
        """
        start_time = time.time()
        try:
            print(f"发送流式请求到模型，音频大小: {len(audio_data)} 字节，格式: {audio_format}")
            
            # 准备消息
            messages = self._prepare_messages(audio_data, text_prompt, audio_format)
            
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
            transcript_text = ""
            full_text_response = ""
            audio_chunks_count = 0
            audio_total_size = 0
            
            try:
                for chunk in completion:
                    # 等待一小段时间以减轻服务器压力
                    await asyncio.sleep(0.01)
                    
                    if chunk.choices:
                        if hasattr(chunk.choices[0].delta, "audio"):
                            try:
                                # 获取音频数据
                                audio_data = chunk.choices[0].delta.audio.get("data")
                                if audio_data:
                                    # 解码并添加WAV头
                                    try:
                                        audio_chunk = base64.b64decode(audio_data)
                                        audio_chunks_count += 1
                                        audio_total_size += len(audio_chunk)
                                        
                                        # 把原始PCM添加WAV头
                                        wav_chunk = add_wav_header(audio_chunk)
                                        # 重新编码为base64
                                        b64_chunk = base64.b64encode(wav_chunk).decode('utf-8')
                                        # 以服务器发送事件的格式返回
                                        event_data = {
                                            "event": "audio",
                                            "data": b64_chunk
                                        }
                                        yield f"data: {json.dumps(event_data)}\n\n"
                                    except Exception as e:
                                        print(f"流式处理音频数据块时出错: {e}")
                                
                                # 获取转录文本
                                transcript = chunk.choices[0].delta.audio.get("transcript")
                                if transcript:
                                    transcript_text += transcript
                            except Exception as e:
                                print(f"处理音频数据时出错: {e}")
                        elif hasattr(chunk.choices[0].delta, "content"):
                            content = chunk.choices[0].delta.content
                            if content:
                                full_text_response += str(content)
                                # 以服务器发送事件的格式返回文本
                                event_data = {
                                    "event": "text",
                                    "data": str(content)
                                }
                                yield f"data: {json.dumps(event_data)}\n\n"
                    elif hasattr(chunk, "usage"):
                        # 返回用量统计
                        event_data = {
                            "event": "usage",
                            "data": {
                                "prompt_tokens": chunk.usage.prompt_tokens,
                                "completion_tokens": chunk.usage.completion_tokens,
                                "total_tokens": chunk.usage.total_tokens
                            }
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                        print(f"流式响应用量统计: {chunk.usage}")
                
                # 发送完成事件
                yield f"data: {json.dumps({'event': 'done'})}\n\n"
                
                # 输出统计信息
                print(f"共处理{audio_chunks_count}个音频数据块，总大小: {audio_total_size} 字节")
                
            except Exception as e:
                print(f"流式处理响应时出错: {e}")
                # 返回错误事件
                event_data = {
                    "event": "error",
                    "data": str(e)
                }
                yield f"data: {json.dumps(event_data)}\n\n"
                raise
            
            # 更新对话历史
            final_response_text = full_text_response if full_text_response else transcript_text
            
            # 更新对话历史 - 选择合适的信息来源
            final_user_text = transcript_text if transcript_text else text_prompt
            self._update_chat_history(final_user_text, final_response_text, text_prompt)
            
            total_time = time.time() - start_time
            print(f"流式处理总时间: {total_time:.2f}秒")
            
        except Exception as e:
            print(f"流式处理音频时出错: {e}")
            # 返回错误事件
            event_data = {
                "event": "error",
                "data": str(e)
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            raise

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