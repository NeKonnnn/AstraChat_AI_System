# vLLM и MoE-модели

## Что поменять

### 1. Конфиг `llm-svc/config/config.yml`

В секции **model** выставить:

```yaml
model:
  backend: "vllm"   # было: "llama.cpp"
  # Путь: ID с HuggingFace или локальная папка с моделью (config.json, веса)
  path: "Qwen/Qwen2.5-MoE-A2B-7B-Instruct"   # пример HF; или "/app/models/llm/MyMoE"
  name: "qwen-moe"
  ctx_size: 32768
  trust_remote_code: true
  tensor_parallel_size: 1
  gpu_memory_utilization: 0.9
  quantization: null   # или "awq" / "gptq" для квантованных MoE
```

- **path** — для vLLM не .gguf, а либо HuggingFace ID (`org/name`), либо папка в контейнере с конфигом и весами (например `/app/models/llm/MyMoE`, если смонтировали в `./models`).
- **backend** обязательно `"vllm"`.

### 2. Запуск только с GPU

vLLM работает только на GPU. Нужен образ с CUDA и доступ контейнера к видеокарте.

## Что пересобрать и как запустить

```bash
# Сборка llm-svc с GPU (CUDA + vLLM)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build llm-svc

# Запуск всего стека с GPU
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Либо только перезапуск llm-svc после правки конфига:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --force-recreate llm-svc
```

## Проверка

В логах должно быть: `INITIALIZING VLLM BACKEND` и затем `vLLM model loaded successfully`. При первом запуске с HF ID vLLM скачает модель в кэш.
