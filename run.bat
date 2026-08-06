@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Dang tao moi truong chay lan dau...
  python -m venv .venv
  if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -c "import cv2, PIL, numpy" >nul 2>&1
if errorlevel 1 (
  echo Dang cai thu vien can thiet...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" main.py
exit /b 0

:error
echo.
echo Khong the khoi dong. Hay kiem tra Python 3.10 tro len da duoc cai dat.
pause
exit /b 1

