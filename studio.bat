@echo off
rem TTS 작업실 켜기 (바탕화면 아이콘이 이 파일을 연다). 이 창을 닫으면 꺼진다.
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [TTS] setup.bat 을 먼저 실행하세요.
  pause
  exit /b 1
)
title TTS 작업실 - 이 창을 닫으면 꺼집니다
".venv\Scripts\python.exe" launch.py
if errorlevel 1 pause
