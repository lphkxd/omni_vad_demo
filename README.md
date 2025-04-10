# 语音AI对话系统

这是一个基于语音识别和大语言模型的交互式对话系统，允许用户通过语音与AI助手进行自然对话。系统使用浏览器内置的VAD(语音活动检测)功能识别用户语音，通过阿里云Qwen大模型API处理并生成回复，支持文本和语音双模态响应。

## 功能特性

- 🎤 **实时语音检测**：自动检测和处理用户语音输入
- 🧠 **智能对话处理**：使用强大的大语言模型理解和回应用户查询
- 🔊 **语音合成回复**：支持AI回复的文本到语音转换
- 📝 **对话历史记录**：保存对话历史，实现连贯的多轮对话
- 🌐 **HTTPS支持**：提供安全连接，允许浏览器访问麦克风
- 📊 **实时状态反馈**：直观显示系统处理状态和错误信息

## 系统要求

- Python 3.8+
- 现代浏览器（Chrome、Firefox、Edge等）
- 麦克风设备
- 互联网连接
- [DashScope API密钥](https://dashscope.aliyun.com/)（阿里云通义千问API）

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/omni_vad_demo.git
cd omni_vad_demo
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

设置DashScope API密钥：

```bash
# Windows
set DASHSCOPE_API_KEY=your_api_key_here

# Linux/macOS
export DASHSCOPE_API_KEY=your_api_key_here
```

### 4. 启动服务器

#### 使用HTTPS（推荐，支持麦克风访问）

Windows:
```bash
start_https_server.bat
```

Linux/macOS:
```bash
chmod +x start_https_server.sh
./start_https_server.sh
```

> **注意**: 首次启动需要安装mkcert并生成自签名证书。脚本会指导您完成此过程。

#### 使用HTTP（仅用于测试，麦克风功能受限）

```bash
python api_server.py
```

### 5. 访问应用

使用浏览器访问:
- HTTPS模式: `https://localhost:8000` 或 `https://你的IP地址:8000`
- HTTP模式: `http://localhost:8000` 或 `http://你的IP地址:8000`

## 使用指南

1. 点击"启动对话"按钮开始会话
2. 允许浏览器访问麦克风（如提示）
3. 开始说话，系统会自动检测语音并处理
4. AI将通过文本和语音方式回复
5. 点击"清除历史"按钮可重置对话上下文
6. 点击"结束对话"停止语音检测

## 项目结构

```
omni_vad_demo/
├── api_server.py          # 主服务器应用
├── audio_agent.py         # 音频处理和AI接口
├── start_https_server.bat # Windows HTTPS启动脚本
├── start_https_server.sh  # Linux/macOS HTTPS启动脚本
├── key.pem                # SSL密钥（自动生成）
├── cert.pem               # SSL证书（自动生成）
├── static/                # 前端资源
│   ├── index.html         # 主页面
│   ├── css/               # 样式表
│   └── js/                # JavaScript文件
│       └── app.js         # 前端主逻辑
└── README.md              # 项目说明
```

## 技术细节

- **后端**: FastAPI, Python
- **前端**: HTML, CSS, JavaScript
- **语音处理**: Web Audio API, VAD (Voice Activity Detection)
- **AI模型**: 阿里云Qwen-Omni模型（通过DashScope API）
- **语音合成**: 浏览器原生TTS + 阿里云语音合成

## 常见问题

### 无法访问麦克风

浏览器只允许在安全环境（HTTPS或localhost）下访问麦克风。请使用HTTPS模式或确保通过localhost访问。

### 证书警告

由于使用自签名证书，浏览器可能显示安全警告。这是正常的，您可以选择"继续访问"。

### 语音识别问题

确保您的麦克风工作正常，并且在相对安静的环境中使用。系统需要清晰的语音输入。

### API限制

免费的DashScope API有使用限制。如果遇到API错误，可能是达到了调用限制。

## 许可证

[MIT](LICENSE)

## 致谢

- [VAD-Web](https://github.com/ricky0123/vad-web) - 提供浏览器端语音活动检测
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能API框架
- [阿里云DashScope](https://dashscope.aliyun.com/) - 提供AI模型服务
