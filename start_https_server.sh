#!/bin/bash

echo "===== HTTPS语音对话服务器启动工具 ====="
echo ""

# 检查mkcert是否安装
if ! command -v mkcert &> /dev/null; then
    echo "[!] 未找到mkcert工具，请先安装："
    echo "   macOS: brew install mkcert"
    echo "   Linux: 请参考 https://github.com/FiloSottile/mkcert#linux"
    echo ""
    read -p "是否继续尝试生成证书? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消操作"
        exit 1
    fi
fi

# 检查证书文件是否存在
if [ -f key.pem ] && [ -f cert.pem ]; then
    echo "[√] 找到SSL证书和密钥文件"
else
    echo "[!] 未找到SSL证书或密钥文件，将尝试生成..."
    echo ""
    
    # 获取本机IP地址
    echo "正在获取IP地址..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        ip_addr=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
    else
        # Linux
        ip_addr=$(hostname -I | awk '{print $1}')
    fi
    
    if [ -n "$ip_addr" ]; then
        echo "检测到IP地址: $ip_addr"
        echo ""
        read -p "是否要使用此IP地址生成证书? [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo "正在生成包含本机IP的证书..."
            mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1 "$ip_addr"
        else
            echo "正在生成基本证书..."
            mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1
        fi
    else
        echo "未能检测到IP地址，将生成基本证书..."
        mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1
    fi
    
    if [ -f key.pem ] && [ -f cert.pem ]; then
        echo "[√] 证书生成成功！"
    else
        echo "[×] 证书生成失败，请手动执行:"
        echo "    mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1 你的IP地址"
        echo ""
        exit 1
    fi
fi

# 设置环境变量以便服务器使用SSL
export SSL_KEYFILE=key.pem
export SSL_CERTFILE=cert.pem

echo ""
echo "[*] 正在启动HTTPS服务器..."
echo ""
echo "请注意以下事项:"
echo " 1. 浏览器会显示证书警告，这是正常的，因为使用了自签名证书"
echo " 2. 请通过 https://localhost:8000 或 https://你的IP地址:8000 访问服务"
echo " 3. 使用Ctrl+C可以停止服务器"
echo ""

# 启动服务器
python3 api_server.py

echo ""
echo "服务器已停止" 