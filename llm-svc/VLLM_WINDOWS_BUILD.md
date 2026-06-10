# Компиляция vLLM на Windows

## ⚠️ Важные предупреждения

1. **vLLM официально не поддерживает Windows** - компиляция может быть сложной и нестабильной
2. **Требуется много времени** - компиляция может занять 30-60 минут
3. **Требуется много места** - ~10-20 GB для всех зависимостей
4. **Рекомендация**: Используйте llama.cpp - он работает отлично на Windows без компиляции

## 📋 Требования

### 1. Visual Studio Build Tools 2019 или 2022

**Скачать:**
- Visual Studio Build Tools 2022: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
- Или полную версию Visual Studio Community (бесплатная)

**При установке выберите:**
- ✅ Desktop development with C++
- ✅ Windows 10/11 SDK (последняя версия)
- ✅ MSVC v143 - VS 2022 C++ x64/x86 build tools
- ✅ C++ CMake tools for Windows

### 2. CUDA Toolkit 11.8 или 12.x

**Скачать:**
- CUDA Toolkit 12.4: https://developer.nvidia.com/cuda-12-4-0-download-archive
- Или CUDA Toolkit 11.8: https://developer.nvidia.com/cuda-11-8-0-download-archive

**Важно:**
- Установите полный CUDA Toolkit (не только драйвер)
- После установки добавьте в PATH:
  - `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin`
  - `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\libnvvp`

### 3. Python 3.8-3.11 (рекомендуется 3.10 или 3.11)

**Важно:** vLLM может не работать с Python 3.12+ на Windows

**Скачать:**
- Python 3.11: https://www.python.org/downloads/release/python-3110/

### 4. Git

**Скачать:**
- Git for Windows: https://git-scm.com/download/win

## 🔧 Пошаговая установка

### Шаг 1: Подготовка окружения

```powershell
# Создайте новое виртуальное окружение с Python 3.11
python -m venv venv_vllm
.\venv_vllm\Scripts\activate

# Обновите pip
python -m pip install --upgrade pip setuptools wheel
```

### Шаг 2: Установка зависимостей для компиляции

```powershell
# Установите необходимые пакеты
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Установите зависимости для компиляции
pip install ninja packaging
```

### Шаг 3: Установка vLLM из исходников

```powershell
# Клонируйте репозиторий vLLM
git clone https://github.com/vllm-project/vllm.git
cd vllm

# Или установите напрямую из GitHub
pip install git+https://github.com/vllm-project/vllm.git
```

### Шаг 4: Компиляция (если установка из исходников)

```powershell
# Установите vLLM с компиляцией
pip install -e . --verbose

# Или с указанием CUDA
VLLM_USE_TRITON=0 pip install -e . --verbose
```

## 🐛 Решение проблем

### Проблема 1: "Microsoft Visual C++ 14.0 or greater is required"

**Решение:**
```powershell
# Установите Visual Studio Build Tools
# Или используйте предкомпилированные пакеты:
pip install vllm --no-build-isolation
```

### Проблема 2: "CUDA not found"

**Решение:**
```powershell
# Проверьте установку CUDA
nvcc --version

# Установите переменные окружения
$env:CUDA_PATH = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4"
$env:PATH = "$env:CUDA_PATH\bin;$env:PATH"
```

### Проблема 3: "Triton compilation failed"

**Решение:**
```powershell
# Отключите Triton (может работать медленнее)
$env:VLLM_USE_TRITON = "0"
pip install -e . --verbose
```

### Проблема 4: Ошибки компиляции C++

**Решение:**
```powershell
# Используйте предкомпилированные wheels (если доступны)
pip install vllm --only-binary :all:

# Или попробуйте более старую версию
pip install vllm==0.6.0
```

## 🚀 Альтернативные способы

### Вариант 1: Использовать WSL2 (Windows Subsystem for Linux)

```powershell
# Установите WSL2
wsl --install

# В WSL2 установка vLLM намного проще
wsl
pip install vllm
```

### Вариант 2: Использовать Docker

```powershell
# Запустите vLLM в Docker контейнере
docker run --gpus all -p 8000:8000 vllm/vllm-openai:latest
```

### Вариант 3: Использовать llama.cpp (РЕКОМЕНДУЕТСЯ)

```yaml
# В config.yml просто измените:
model:
  backend: "llama.cpp"  # Работает без компиляции!
```

## ✅ Проверка установки

```powershell
# Активируйте виртуальное окружение
.\venv_vllm\Scripts\activate

# Проверьте импорт
python -c "import vllm; print('vLLM version:', vllm.__version__)"

# Проверьте C++ расширения
python -c "import vllm._C; print('C++ extensions OK')"
```

## 📝 Примечания

1. **Время компиляции**: Первая компиляция может занять 30-60 минут
2. **Место на диске**: Требуется ~10-20 GB свободного места
3. **Память**: Рекомендуется минимум 16 GB RAM
4. **GPU**: vLLM требует NVIDIA GPU с поддержкой CUDA

## 🎯 Рекомендация

**Для Windows настоятельно рекомендуется использовать llama.cpp:**
- ✅ Работает из коробки
- ✅ Поддерживает CPU и GPU
- ✅ Не требует компиляции
- ✅ Отличная производительность
- ✅ Меньше проблем с зависимостями

Просто установите в `config/config.yml`:
```yaml
model:
  backend: "llama.cpp"
```















































