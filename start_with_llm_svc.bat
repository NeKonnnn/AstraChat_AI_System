@echo off
echo ========================================
echo    MemoAI с llm-svc интеграцией
echo    (Фоновый запуск)
echo ========================================
echo.

echo Проверка конфигурации...
if not exist "llm-svc\config\config.yml" (
    echo ОШИБКА: Файл llm-svc\config\config.yml не найден!
    echo Создайте конфигурацию согласно INTEGRATION_GUIDE.md
    pause
    exit /b 1
)

echo Проверка директории models...
if not exist "models" (
    echo ВНИМАНИЕ: Директория models\ не найдена!
    echo Создайте директорию и поместите туда ваши .gguf модели
    mkdir models
)

echo Проверка виртуального окружения...
if not exist "venv_312\Scripts\activate.bat" (
    echo ОШИБКА: Виртуальное окружение venv_312 не найдено!
    echo Создайте виртуальное окружение: python -m venv venv_312
    pause
    exit /b 1
)

echo Все файлы найдены
echo.

echo.
echo Запуск llm-svc сервиса в фоне...
start /B "LLM-SVC" cmd /c "venv_312\Scripts\activate.bat && cd llm-svc && python -m app.main"

echo Запуск Backend сервера в фоне (с llm-svc)...
start /B "MemoAI Backend" cmd /c "venv_312\Scripts\activate.bat && set USE_LLM_SVC=true && python backend\main.py"

echo Запуск Frontend сервера в фоне...
start /B "MemoAI Frontend" cmd /c "cd frontend && npm start"

echo.
echo Ожидание запуска серверов (15 секунд)...
echo llm-svc загружает модель, это может занять несколько минут...
timeout /t 15 /nobreak >nul

echo.
echo ========================================
echo    Сервисы запущены в фоне:
echo    - llm-svc: http://localhost:8001 (загружает модель...)
echo    - Backend: http://localhost:8000 (с llm-svc интеграцией)
echo    - Frontend: http://localhost:3000
echo ========================================
echo.
echo ВАЖНО: Дождитесь полной загрузки модели в llm-svc!
echo Это может занять 2-5 минут для больших моделей.
echo.
echo Нажмите любую клавишу для выхода...
pause >nul
