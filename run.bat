@echo off
REM Run main.py with the system Python311 (bypasses any active venv)
setlocal
set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Error: Python311 not found at %PYTHON_EXE%
    echo Install Python 3.11 or update run.bat with the correct path.
    exit /b 1
)

cd /d "%~dp0"
"%PYTHON_EXE%" main.py %*
exit /b %ERRORLEVEL%
