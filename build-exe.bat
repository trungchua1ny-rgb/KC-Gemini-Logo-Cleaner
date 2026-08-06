@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" python -m venv .venv
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-dev.txt
if errorlevel 1 exit /b 1

".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed --name "KC Gemini Logo Cleaner" --collect-all cv2 main.py
if errorlevel 1 exit /b 1

echo Da tao ban chay tai dist\KC Gemini Logo Cleaner\
pause

