@echo off
chcp 65001 >nul
REM Скрипт для запуска MinIO локально
REM MinIO находится в E:\minIO

REM Пути (можно изменить, если MinIO в другом месте)
set MINIO_DIR=E:\minIO
set DATA_DIR=E:\minIO-data

REM Проверяем существование MinIO
if not exist "%MINIO_DIR%\minio.exe" (
    echo ОШИБКА: MinIO не найден в %MINIO_DIR%
    echo Убедитесь, что minio.exe находится в указанной папке
    echo Или измените путь MINIO_DIR в этом скрипте
    pause
    exit /b 1
)

cd /d %MINIO_DIR%

echo ========================================
echo Запуск MinIO сервера
echo ========================================
echo.
echo MinIO: %MINIO_DIR%\minio.exe
echo Данные: %DATA_DIR%
echo.

REM Устанавливаем переменные окружения для MinIO
set MINIO_ROOT_USER=minioadmin
set MINIO_ROOT_PASSWORD=minioadmin

echo MinIO будет доступен:
echo   API: http://localhost:9000
echo   Console: http://localhost:9001
echo   Login: minioadmin / minioadmin
echo.
echo Нажмите Ctrl+C для остановки сервера
echo.

REM Создаем папку для данных, если её нет
if not exist "%DATA_DIR%" (
    mkdir "%DATA_DIR%"
    echo Создана папка для данных: %DATA_DIR%
    echo.
)

REM Запускаем MinIO сервер
minio.exe server %DATA_DIR% --console-address ":9001"

pause

