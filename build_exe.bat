@echo off
chcp 65001 >nul
title 打包 BadmintonBooking.exe
cd /d "%~dp0"

echo 安装打包依赖...
python -m pip install -r requirements.txt pyinstaller

echo.
python build_exe.py

echo.
pause
