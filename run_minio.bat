@echo off
title MinIO Launcher
echo ========================================
echo Запуск MinIO через обертку
echo ========================================
echo.
echo Вызываю start_minio.bat...
echo.

call start_minio.bat

echo.
echo ========================================
echo start_minio.bat завершил работу
echo Код возврата: %errorlevel%
echo ========================================
echo.
pause

