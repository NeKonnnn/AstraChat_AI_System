@echo off
title MemoAI Web Interface Launcher

echo.
echo ======================================================
echo             MemoAI Web Interface
echo               Запуск серверов
echo ======================================================
echo.

:: Проверка файлов
if not exist "venv_312\" (
    echo Виртуальная среда myvenv не найдена!
    pause
    exit /b 1
)

if not exist "frontend\package.json" (
    echo Frontend не найден!
    pause
    exit /b 1
)

if not exist "backend\main.py" (
    echo Backend не найден!
    pause
    exit /b 1
)

echo Все файлы найдены
echo.

echo Активация виртуальной среды...
call myvenv\Scripts\activate.bat

echo.
echo Запуск Backend сервера в фоне...
start /B "MemoAI Backend" cmd /c "venv_312\Scripts\activate.bat && python backend\main.py"

echo Запуск Frontend сервера в фоне...
start /B "MemoAI Frontend" cmd /c "cd frontend && npm start"

echo.
echo Ожидание запуска серверов (10 секунд)...
timeout /t 10 /nobreak >nul

echo.
echo ======================================================
echo MemoAI Web Interface запущен!
echo.
echo Приложение: http://localhost:3000
echo Backend API: http://localhost:8000  
echo API Docs: http://localhost:8000/docs
echo ======================================================
echo.

echo Открытие браузера...
start http://localhost:3000

echo.
echo Нажмите любую клавишу для выхода...
echo ВНИМАНИЕ: Серверы продолжат работать в фоне
pause >nul

echo Launcher завершен (серверы работают в фоне)
exit /b 0
