@echo off
title Запуск MinIO

set MINIO_DIR=E:\minIO
set DATA_DIR=E:\minIO-data

cls
echo ========================================
echo Запуск MinIO сервера
echo ========================================
echo.

echo [1/4] Проверка minio.exe...
if not exist "%MINIO_DIR%\minio.exe" (
    echo ОШИБКА: minio.exe не найден в %MINIO_DIR%
    echo.
    pause
    exit /b 1
)
echo OK: найден
echo.

echo [2/4] Проверка папки данных...
if not exist "%DATA_DIR%" (
    mkdir "%DATA_DIR%"
)
echo OK: %DATA_DIR%
echo.

echo [3/4] Проверка портов...
netstat -ano | findstr ":9001" >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo Порт 9001 уже занят - MinIO возможно уже запущен
    echo Открываю консоль...
    start http://localhost:9001
    echo.
    pause
    exit /b 0
)
echo OK: порты свободны
echo.

echo [4/4] Запуск сервера...
echo.
echo API: http://localhost:9000
echo Console: http://localhost:9001  
echo Login: minioadmin / minioadmin
echo.

cd /d "%MINIO_DIR%"

REM Запускаем MinIO через PowerShell для надежности
powershell -Command "Start-Process cmd -ArgumentList '/k','cd /d E:\minIO && set MINIO_ROOT_USER=minioadmin && set MINIO_ROOT_PASSWORD=minioadmin && minio.exe server E:\minIO-data --console-address :9001' -WindowStyle Normal"

echo Ожидание запуска...
timeout /t 6 /nobreak >nul

netstat -ano | findstr ":9001" >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo Успешно запущен!
    echo Открываю браузер...
    timeout /t 1 /nobreak >nul
    start http://localhost:9001
) else (
    echo.
    echo Ошибка запуска - проверьте окно MinIO Server
)

echo.
pause
