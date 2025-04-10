@echo off
setlocal enabledelayedexpansion
echo ===== HTTPS语音对话服务器启动工具 =====
echo.

REM 检查证书文件是否存在
if exist key.pem if exist cert.pem (
    echo [√] 找到SSL证书和密钥文件
) else (
    echo [!] 未找到SSL证书或密钥文件，将尝试生成...
    echo.
    echo 注意: 需要先安装mkcert工具
    echo 在管理员权限的PowerShell中执行以下命令安装mkcert:
    echo   choco install mkcert
    echo   mkcert -install
    echo.
    
    REM 获取本机IP地址
    echo 正在获取IP地址...
    set ip_found=false
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do (
        if "!ip_found!"=="false" (
            set ip_addr=%%a
            set ip_found=true
            set ip_addr=!ip_addr:~1!
            echo 检测到IP地址: !ip_addr!
        )
    )
    
    echo.
    echo 是否要使用此IP地址生成证书? [Y/N]
    set /p use_ip=
    
    if /i "!use_ip!"=="Y" (
        echo 正在生成包含本机IP的证书...
        mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1 !ip_addr!
    ) else (
        echo 正在生成基本证书...
        mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1
    )
    
    if exist key.pem if exist cert.pem (
        echo [√] 证书生成成功！
    ) else (
        echo [×] 证书生成失败，请手动执行:
        echo     mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1 你的IP地址
        echo.
        echo 请先安装mkcert:
        echo     1. 以管理员身份运行PowerShell
        echo     2. 执行: choco install mkcert
        echo     3. 执行: mkcert -install
        echo.
        pause
        exit /b
    )
)

REM 设置环境变量以便服务器使用SSL
set SSL_KEYFILE=key.pem
set SSL_CERTFILE=cert.pem

echo.
echo [*] 正在启动HTTPS服务器...
echo.
echo 请注意以下事项:
echo  1. 浏览器会显示证书警告，这是正常的，因为使用了自签名证书
echo  2. 请通过 https://localhost:8000 或 https://你的IP地址:8000 访问服务
echo  3. 使用Ctrl+C可以停止服务器
echo.

REM 启动服务器
python api_server.py

echo.
echo 服务器已停止
pause 