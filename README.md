# 智能语音对话系统

基于阿里云千问Qwen-Omni模型的网页端语音对话系统，支持实时语音识别、自然语言处理和语音合成。

## 功能特点

- **实时语音检测**：采用VAD (Voice Activity Detection) 技术，自动检测用户语音
- **语音识别与合成**：将用户语音转为文本，模型回复同时支持文本与语音输出
- **多轮对话记忆**：保留最近5轮对话历史，提供连贯的交互体验
- **优化的性能**：
  - TCP连接保持活跃，减少连接建立时间
  - WAV头预缓存，优化音频处理
  - 响应GZip压缩，减少网络传输量
  - 对话历史管理，限制内存使用

## 系统架构

### 后端组件

- **api_server.py**: FastAPI服务器，处理HTTP请求，提供REST API
- **audio_agent.py**: 核心音频处理代理，与千问大模型交互

### 前端组件

- **static/index.html**: 主页面
- **static/js/app.js**: 主应用逻辑，处理用户界面与交互
- **static/css/**: 样式文件
- **static/favicon.svg**: 网站图标

### 文件结构

```
omni_vad_demo/
├── api_server.py        # FastAPI服务器入口
├── audio_agent.py       # 音频处理代理
├── requirements.txt     # Python依赖
├── start_https_server.sh  # Linux/Mac启动脚本
├── start_https_server.bat # Windows启动脚本
├── cert.pem             # SSL证书
├── key.pem              # SSL密钥
├── static/              # 静态资源目录
│   ├── index.html       # 主HTML页面
│   ├── favicon.svg      # 网站图标
│   ├── css/             # CSS样式
│   └── js/              # JavaScript文件
│       └── app.js       # 主应用逻辑
└── archive/             # 归档的冗余文件
    ├── base64_decode.py # 测试脚本
    ├── hello.py         # 测试脚本
    ├── main.py          # 旧版服务器
    ├── audio-client.js  # 旧版音频客户端库
    └── vad_test.html    # 旧版HTML页面
```

## 安装部署

### 环境要求

- Python 3.8+
- 阿里云千问API密钥
- HTTPS支持（浏览器中使用麦克风需要HTTPS）

### 步骤

1. **克隆仓库并安装依赖**:

```bash
git clone <仓库URL>
cd omni_vad_demo
pip install -r requirements.txt
```

2. **配置API密钥**:

设置环境变量`DASHSCOPE_API_KEY`为您的阿里云千问API密钥:

```bash
# Linux/Mac
export DASHSCOPE_API_KEY="你的API密钥"

# Windows
set DASHSCOPE_API_KEY=你的API密钥
```

3. **HTTPS证书配置**:

对于本地开发，可以使用mkcert生成自签名证书:

```bash
# 安装mkcert
# Windows: choco install mkcert
# MacOS: brew install mkcert

# 生成证书
mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1 你的IP地址
```

4. **启动服务**:

```bash
# Windows
.\start_https_server.bat

# Linux/Mac
./start_https_server.sh
```

默认情况下，服务将在`https://localhost:8000`上运行。

## 使用方法

1. 使用HTTPS在浏览器中访问服务
2. 点击"启动对话"按钮授予麦克风权限
3. 开始说话，系统会自动检测语音并处理
4. 点击"清除历史"按钮可以开始新的对话
5. 点击"结束对话"按钮停止服务

## 性能优化

系统已进行多项性能优化:

1. **音频处理优化**:
   - WAV头预缓存，避免重复生成
   - 使用BytesIO减少内存使用

2. **响应优化**:
   - GZip压缩响应，减少网络传输
   - 对话历史限制，控制内存使用

3. **提示词优化**:
   - 避免重复提示词，提高对话效率
   - 系统提示词指导模型更简洁回答

## 注意事项

- 浏览器访问必须使用HTTPS（因为麦克风访问需要安全上下文）
- 确保API密钥有效且有足够的调用额度
- iOS设备可能需要用户交互才能播放音频
- 项目默认限制对话历史为5轮
- 若要支持多进程，使用命令行启动:`uvicorn api_server:app --host=0.0.0.0 --port=8000 --ssl-keyfile=key.pem --ssl-certfile=cert.pem --workers=4`

## 技术详情

- 前端使用纯JavaScript，无框架依赖
- 使用WebAPI MediaRecorder录制音频
- 使用@ricky0123/vad-web进行语音活动检测
- 使用WebAPI SpeechSynthesis作为备用语音合成
- 后端使用FastAPI和Uvicorn
- 使用OpenAI兼容方式调用阿里云千问模型
