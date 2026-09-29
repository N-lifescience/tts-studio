@echo off
rem 처음 한 번 더블클릭: 파이썬·ffmpeg·Node 설치, 환경 만들기, 바탕화면 아이콘까지.
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
pause
