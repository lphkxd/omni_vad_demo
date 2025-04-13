import os
import base64
import uvicorn
import time
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, Response, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Optional, AsyncGenerator
from pydantic import BaseModel
import logging

from audio_agent import audio_agent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 设置一些库的日志级别为WARNING，减少非关键日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(title="音频处理API", description="处理音频并通过大模型获取回复的API服务")

# 添加Gzip压缩中间件，对大于1000字节的响应进行压缩，提高传输效率
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 添加favicon.ico路由
@app.get("/favicon.ico")
async def get_favicon():
    """处理favicon.ico请求"""
    return RedirectResponse(url="/static/favicon.svg")

class AudioRequest(BaseModel):
    audio_data: str
    text_prompt: str = "这段音频在说什么"
    audio_format: str = "webm"  # 默认使用webm格式，前端现在发送的是wav

@app.post("/process_audio")
async def process_audio(request: AudioRequest):
    start_time = time.time()
    try:
        # 记录请求大小和格式
        request_size = len(request.audio_data)
        logger.info(f"收到音频请求，大小: {request_size} 字节，格式: {request.audio_format}")
        
        # 解码base64音频数据
        decode_start = time.time()
        audio_bytes = base64.b64decode(request.audio_data)
        decode_time = time.time() - decode_start
        logger.info(f"base64解码耗时: {decode_time:.2f}秒")
        
        # 处理音频，传递格式参数
        process_start = time.time()
        result = audio_agent.process_audio(audio_bytes, request.text_prompt, request.audio_format)
        process_time = time.time() - process_start
        logger.info(f"音频处理耗时: {process_time:.2f}秒")
        
        # 构建响应
        response = {
            "text": result["text"],
            "audio": result.get("audio"),
            "usage": result.get("usage")
        }
        
        # 记录响应信息
        if response["audio"]:
            audio_size = len(response["audio"])
            logger.info(f"返回音频数据，base64大小: {audio_size} 字节")
        
        total_time = time.time() - start_time
        logger.info(f"总处理时间: {total_time:.2f}秒")
        
        # 记录模型使用情况（如果可用）
        if response["usage"]:
            logger.info(f"模型用量: 提示词 {response['usage'].prompt_tokens} 词元，回复 {response['usage'].completion_tokens} 词元，总计 {response['usage'].total_tokens} 词元")
        
        return response
        
    except Exception as e:
        logger.error(f"处理音频时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stream_audio")
async def stream_audio(request: AudioRequest):
    """处理音频并以流式方式返回响应"""
    try:
        # 记录请求信息
        request_size = len(request.audio_data)
        logger.info(f"收到流式音频请求，大小: {request_size} 字节，格式: {request.audio_format}")
        
        # 解码base64音频数据
        audio_bytes = base64.b64decode(request.audio_data)
        
        # 创建响应流
        return StreamingResponse(
            audio_agent.stream_audio(audio_bytes, request.text_prompt, request.audio_format),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"流式处理音频时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clear_history")
async def clear_chat_history():
    """清除对话历史记录"""
    try:
        audio_agent.clear_history()
        return {"status": "success", "message": "对话历史已清除"}
    except Exception as e:
        logger.error(f"清除对话历史时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}

@app.get("/")
async def redirect_to_index():
    """重定向到前端页面"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")

if __name__ == "__main__":
    # 获取端口，默认为8000
    port = int(os.environ.get("PORT", 8000))
    
    # 检查是否存在SSL证书和密钥
    ssl_keyfile = os.environ.get("SSL_KEYFILE", "key.pem")
    ssl_certfile = os.environ.get("SSL_CERTFILE", "cert.pem")
    
    # 如果证书和密钥文件存在，则启用HTTPS
    ssl_enabled = os.path.exists(ssl_keyfile) and os.path.exists(ssl_certfile)
    
    workers = min(4, os.cpu_count() or 1)  # 根据CPU核心数设置工作进程数
    
    if ssl_enabled:
        logger.info(f"使用HTTPS启动服务，证书: {ssl_certfile}, 密钥: {ssl_keyfile}")
        # 在以下情况下不使用多工作进程
        if workers > 1:
            logger.warning("使用SSL时，必须通过命令行启动多工作进程。将使用单进程模式。")
            logger.info("如需多工作进程，请使用: uvicorn api_server:app --host=0.0.0.0 --port={} --ssl-keyfile={} --ssl-certfile={} --workers={}".format(
                port, ssl_keyfile, ssl_certfile, workers
            ))
            workers = 1
        # 启动HTTPS服务器
        uvicorn.run(app, host="0.0.0.0", port=port, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)
    else:
        logger.warning(
            "未找到SSL证书和密钥文件，将使用HTTP启动服务。"
            "注意: 浏览器中使用麦克风功能需要HTTPS连接。"
            "可以使用以下命令生成自签名证书:\n"
            "choco install mkcert  # Windows\n"
            "brew install mkcert   # MacOS\n"
            "mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1 你的IP地址"
        )
        # 在以下情况下不使用多工作进程
        if workers > 1:
            logger.info("要使用{}个工作进程，请使用命令: uvicorn api_server:app --host=0.0.0.0 --port={} --workers={}".format(
                workers, port, workers
            ))
            workers = 1
        # 启动HTTP服务器
        uvicorn.run(app, host="0.0.0.0", port=port) 