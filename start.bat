@echo off
chcp 65001 >nul
title 羽毛球预约助手
cd /d "%~dp0"

if not exist "frontend\dist\index.html" (
    echo [1/2] 构建前端...
    pushd frontend
    call npm install
    call npm run build
    popd
) else (
    echo [1/2] 前端已构建
)

echo [2/2] 启动服务...
echo.
python run.py
pause
