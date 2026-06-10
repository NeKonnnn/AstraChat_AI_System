# Установка vLLM на Windows

## Проблема
vLLM установлен, но C++ расширения отсутствуют. Это означает, что vLLM не может работать.

## Решение: Установка vLLM с C++ расширениями

### Шаг 1: Установите Visual Studio Build Tools

1. Скачайте Visual Studio Build Tools с официального сайта:
   https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022

2. Установите компонент "Desktop development with C++":
   - Откройте Visual Studio Installer
   - Выберите "Modify" для Build Tools
   - Установите флажок "Desktop development with C++"
   - Убедитесь, что установлены:
     - MSVC v143 - VS 2022 C++ x64/x86 build tools
     - Windows 10/11 SDK
     - C++ CMake tools for Windows

### Шаг 2: Установите CUDA Toolkit

1. Скачайте CUDA Toolkit с официального сайта NVIDIA:
   https://developer.nvidia.com/cuda-downloads

2. Выберите версию, совместимую с вашей видеокартой и vLLM:
   - vLLM 0.13.0 поддерживает CUDA 11.8 и 12.1+
   - Рекомендуется CUDA 12.1 или новее

3. Установите CUDA Toolkit

### Шаг 3: Переустановите vLLM

```bash
# Активируйте виртуальное окружение
F:\memo_new_api\venv_312\Scripts\activate

# Удалите старую версию vLLM
pip uninstall vllm -y

# Установите vLLM заново (будет скомпилирован с C++ расширениями)
pip install vllm
```

### Шаг 4: Проверьте установку

```bash
python -c "import vllm; import vllm._C; print('vLLM установлен правильно!')"
```

Если команда выполняется без ошибок, vLLM готов к работе!

## Альтернативные решения

### Вариант A: Использовать Docker (рекомендуется для Windows)

Если установка Build Tools и CUDA слишком сложна, используйте Docker:

```bash
# Запустите llm-svc в Docker контейнере
docker-compose -f docker-compose-llm-svc.yml up -d
```

Docker контейнер уже настроен с vLLM и всеми зависимостями.

### Вариант B: Использовать WSL2

1. Установите WSL2 (Windows Subsystem for Linux)
2. Установите CUDA в WSL2
3. Запустите vLLM в WSL2 окружении

### Вариант C: Использовать модель в формате GGUF

Если у вас есть модель в формате GGUF, вы можете использовать llama.cpp:

1. Измените `config.yml`:
   ```yaml
   model:
     path: "F:/memo_new_api/models/your-model.gguf"
     backend: "llama.cpp"
   ```

2. llama.cpp работает без CUDA и Build Tools!

## Текущая ситуация

- ✅ Конфигурация настроена правильно
- ✅ Путь к модели указан верно
- ✅ Модель найдена
- ❌ vLLM C++ расширения отсутствуют
- ❌ llama.cpp не может загрузить HuggingFace модель (требуется GGUF)

## Рекомендация

Для модели Qwen3-VL-30B-A3B-Instruct-AWQ (HuggingFace формат):
- **Лучший вариант**: Использовать Docker с vLLM
- **Альтернатива**: Установить Build Tools и CUDA для компиляции vLLM

Для моделей в формате GGUF:
- Используйте llama.cpp (работает сразу, без дополнительной настройки)

















































