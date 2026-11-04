@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
start "Ollama" cmd /c "ollama serve >nul 2>&1"
timeout /t 2 /nobreak >nul
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000