# Настройка vLLM

Этот документ описывает, как настроить и использовать vLLM в llm-svc.

## Обзор

llm-svc теперь поддерживает два бэкенда для работы с LLM:
- **llama.cpp** - для GGUF моделей (квантованные модели, меньше памяти)
- **vLLM** - для оригинальных моделей HuggingFace (высокая производительность, больше памяти)

## Установка vLLM

vLLM уже добавлен в `requirements.txt`. Для установки выполните:

```bash
pip install vllm
```

**Важно:** vLLM требует CUDA и работает только на GPU. Для CPU используйте llama.cpp.

## Настройка конфигурации

В файле `config/config.yml` настройте параметры модели:

```yaml
model:
  # Путь к модели
  # Для GGUF моделей (llama.cpp) - путь к файлу:
  # path: "/app/models/llm/your-model.gguf"
  
  # Для HuggingFace моделей (vLLM) - путь к папке с моделью:
  path: "/app/models/llm/your-model-folder"
  
  # Имя модели
  name: "your-model-name"
  
  # Выбор бэкенда: "llama.cpp" или "vllm"
  backend: "vllm"  # или "llama.cpp"
  
  # Размер контекста
  ctx_size: 4096
  
  # Параметры для vLLM (используются только если backend: "vllm")
  tensor_parallel_size: 1  # Количество GPU для параллельной обработки
  gpu_memory_utilization: 0.9  # Использование памяти GPU (0.0 - 1.0)
  trust_remote_code: true  # Доверять удаленному коду из HuggingFace (необходимо для некоторых моделей)
  quantization: "awq"  # Тип квантования: "awq", "gptq", "fp8" или null для автоматического определения
```

### Пример для AWQ модели (Qwen3-Omni-30B-A3B-Instruct-AWQ-4bit)

```yaml
model:
  path: "/app/models/llm/Qwen3-Omni-30B-A3B-Instruct-AWQ-4bit"
  name: "qwen3-omni-30b-awq"
  backend: "vllm"
  ctx_size: 32768
  tensor_parallel_size: 1
  gpu_memory_utilization: 0.9
  trust_remote_code: true
  quantization: "awq"
```

## Выбор между llama.cpp и vLLM

### Используйте llama.cpp, если:
- У вас GGUF модели (квантованные)
- Ограниченная память GPU
- Нужна работа на CPU
- Модели меньше 7B параметров

### Используйте vLLM, если:
- У вас оригинальные модели HuggingFace (включая AWQ, GPTQ)
- Много памяти GPU (16GB+)
- Нужна максимальная производительность
- Большие модели (7B+ параметров)
- Нужна поддержка continuous batching
- Используете квантованные модели (AWQ, GPTQ) для экономии памяти

### Поддержка квантованных моделей

vLLM поддерживает различные типы квантования:
- **AWQ** (Activation-aware Weight Quantization) - эффективная 4-bit квантация
- **GPTQ** - квантация для GPT моделей
- **FP8** - 8-bit floating point квантация

Для использования квантованных моделей:
1. Укажите путь к папке с моделью (не к файлу)
2. Установите `quantization: "awq"` (или другой тип) в конфиге
3. vLLM автоматически определит формат модели, если `quantization` не указан

## Примеры конфигураций

### Пример 1: llama.cpp с GGUF моделью
```yaml
model:
  path: "/app/models/llm/model.gguf"
  name: "my-model"
  backend: "llama.cpp"
  ctx_size: 4096
  gpu_layers: -1  # Все слои на GPU
```

### Пример 2: vLLM с HuggingFace моделью
```yaml
model:
  path: "/app/models/llm/llama-2-7b-chat-hf"
  name: "llama-2-7b-chat"
  backend: "vllm"
  ctx_size: 4096
  tensor_parallel_size: 1
  gpu_memory_utilization: 0.9
```

### Пример 3: vLLM с несколькими GPU
```yaml
model:
  path: "/app/models/llm/llama-70b-chat-hf"
  name: "llama-70b-chat"
  backend: "vllm"
  ctx_size: 4096
  tensor_parallel_size: 4  # Использовать 4 GPU
  gpu_memory_utilization: 0.95
```

### Пример 4: vLLM с AWQ квантованной моделью
```yaml
model:
  path: "/app/models/llm/Qwen3-Omni-30B-A3B-Instruct-AWQ-4bit"
  name: "qwen3-omni-30b-awq"
  backend: "vllm"
  ctx_size: 32768
  tensor_parallel_size: 1
  gpu_memory_utilization: 0.9
  trust_remote_code: true  # Необходимо для Qwen моделей
  quantization: "awq"  # Явно указываем тип квантования
```

## Переменные окружения

Вы также можете настроить бэкенд через переменные окружения:

```bash
export LLM_BACKEND="vllm"
export LLM_MODEL_PATH="/app/models/llm/your-model"
export LLM_MODEL_NAME="your-model-name"
```

## Проверка работы

После настройки конфигурации перезапустите llm-svc. В логах вы должны увидеть:

```
Loading vLLM model from /app/models/llm/your-model
vLLM model loaded successfully
```

Или для llama.cpp:

```
Loading model from /app/models/llm/model.gguf
Model loaded successfully
```

## API совместимость

Оба бэкенда предоставляют одинаковый API, совместимый с OpenAI:

```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

## Устранение неполадок

### Ошибка: "vLLM is not available"
- Убедитесь, что vLLM установлен: `pip install vllm`
- Проверьте, что у вас есть CUDA и GPU

### Ошибка: "Model not found"
- Проверьте путь к модели в конфигурации
- Для vLLM путь должен указывать на директорию с моделью HuggingFace

### Ошибка: "Out of memory"
- Уменьшите `gpu_memory_utilization`
- Используйте квантованную модель с llama.cpp
- Уменьшите `ctx_size`

### Медленная работа
- Для vLLM убедитесь, что используете GPU
- Проверьте `tensor_parallel_size` для использования нескольких GPU
- Для llama.cpp увеличьте `gpu_layers`





