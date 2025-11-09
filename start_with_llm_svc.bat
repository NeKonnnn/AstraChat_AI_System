@echo off
chcp 65001 >nul 2>&1
title MemoAI with LLM-SVC Integration

REM Переходим в директорию, где находится батник
cd /d %~dp0

echo ========================================
echo    MemoAI with llm-svc integration
echo    (Background launch)
echo ========================================
echo.

echo Checking configuration...
if not exist "llm-svc\config\config.yml" (
    echo ERROR: File llm-svc\config\config.yml not found!
    echo Create configuration according to INTEGRATION_GUIDE.md
    pause
    exit /b 1
)

echo Checking models directory...
if not exist "models" (
    echo WARNING: Directory models\ not found!
    echo Create directory and place your .gguf models there
    mkdir models
)

echo Checking virtual environment...
if not exist "venv_312\Scripts\activate.bat" (
    echo ERROR: Virtual environment venv_312 not found!
    echo Create virtual environment: python -m venv venv_312
    pause
    exit /b 1
)

echo All files found
echo.

echo.
echo Starting llm-svc service in background...
start /B "LLM-SVC" cmd /c "chcp 65001 >nul 2>&1 && cd /d %~dp0 && cd llm-svc && ..\venv_312\Scripts\python.exe -m app.main"

echo Starting Backend server in background (with llm-svc)...
start /B "MemoAI Backend" cmd /c "chcp 65001 >nul 2>&1 && cd /d %~dp0 && set USE_LLM_SVC=true && venv_312\Scripts\python.exe backend\main.py"

echo Starting Frontend server in background...
start /B "MemoAI Frontend" cmd /c "chcp 65001 >nul 2>&1 && cd frontend && npm start"

echo.
echo Waiting for servers to start (15 seconds)...
echo llm-svc is loading model, this may take several minutes...
timeout /t 15 /nobreak >nul

echo.
echo ========================================
echo    Services started in background:
echo    - llm-svc: http://localhost:8001 (loading model...)
echo    - Backend: http://localhost:8000 (with llm-svc integration)
echo    - Frontend: http://localhost:3000
echo ========================================
echo.
echo IMPORTANT: Wait for complete model loading in llm-svc!
echo This may take 2-5 minutes for large models.
echo.
echo Press any key to exit...
pause >nul
