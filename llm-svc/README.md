# Llama CPP API Service

Этот сервис предоставляет API, совместимый с OpenAI, для работы с локальными LLM через llama-cpp-python, чтобы интегрировать их с LibreChat.

## API Endpoints
* POST `/v1/chat/completions` - Генерация ответов чата
* GET `/v1/health` - Проверка статуса сервиса
* GET `/v1/models` - Список доступных моделей

## Документация API
После запуска автоматически генерируется документация:

Swagger UI: http://localhost:8000/docs

ReDoc: http://localhost:8000/redoc


## Особенности

- Полная совместимость с OpenAI API
- Поддержка любых моделей в формате GGUF
- Асинхронная обработка запросов
- Поддержка GPU через CUDA
- Интеграция с LibreChat через custom endpoints
- Подробное логирование и мониторинг здоровья

### Основные разделы конфигурации:

1. **server** - Настройки сервера
   - host: Хост для запуска сервера
   - port: Порт для запуска сервера
   - log_level: Уровень логирования

2. **cors** - Настройки CORS
   - allowed_origins: Разрешенные источники запросов

3. **model** - Настройки модели LLM
   - path: Путь к файлу модели
   - name: Имя модели
   - ctx_size: Размер контекста
   - gpu_layers: Количество слоев для GPU

4. **generation** - Настройки генерации
   - default_temperature: Температура по умолчанию
   - default_max_tokens: Максимальное количество токенов по умолчанию

5. **nexus** - Настройки Nexus (опционально)
   - enabled: Включить/выключить загрузку моделей из Nexus
   - url: URL сервера Nexus
   - repo: Название репозитория
   - name: Название артефакта
   - id: ID артефакта
   - version: Версия артефакта
   - file_name: Имя файла артефакта
   - login: Логин для аутентификации в Nexus (опционально)
   - password: Пароль для аутентификации в Nexus (опционально)
   - cert_path: Путь к сертификату для SSL аутентификации (опционально)

## Конфигурация

Все настройки приложения теперь хранятся в YAML файле `config/config.yml`.

### Переопределение конфигурации

Вы можете переопределить путь к конфигурационному файлу с помощью переменной окружения:

```bash
export CONFIG_PATH=/path/to/your/config.yml
```

### Пример настройки для разных окружений

Создайте базовый конфиг `config/config.yml`

* Скопируйте пример конфигурации:

   ```bash
   cp config/config.example.yml config/config.yml
   ```

* Для разработки создайте `config/development.yml` и переопределите нужные параметры

* Для продакшена создайте `config/production.yml`

Затем укажите путь к нужному конфигу при запуске:

```bash
CONFIG_PATH=config/development.yml python -m app.main
```

Или в Docker Compose:
```yaml
environment:
  - CONFIG_PATH=/app/config/production.yml
```

## Разработка
Для разработки без Docker:

``` bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Тестирование

Запуск всех тестов:

```bash
python -m pytest test/ -v
```

Запуск только тестов API:

```bash
python -m pytest test/test_api.py -v
```

Запуск только тестов LlamaHandler:

```bash
python -m pytest test/test_llama_handler.py -v
```

Запуск конкретного теста:

```bash
python -m pytest test/test_api.py::test_health_check -v
```

Запуск тестов с покрытием:

```bash
pytest test/ --cov=app --cov-report=html
````

Запуск тестов в Docker:

```bash
docker-compose -f docker-compose.test.yml up -d
pytest test/ -v
```

## Быстрый старт

1. Клонируйте репозиторий и перейдите в директорию проекта:

```bash
git clone <repository-url>
cd librechat-llama-integration
```

Скачайте модель:

```bash
mkdir -p models
python models/download_model.py \
  --model-url https://huggingface.co/lmstudio-community/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q8_0.gguf \
  --output-path models/Qwen3-4B-Instruct-2507-Q8_0.gguf
```

Альтернативно, вы можете настроить загрузку модели из Nexus при запуске сервиса,
установив параметры в разделе `nexus` конфигурационного файла `config/config.yml`
и включив опцию `nexus.enabled: true`. В этом случае модель будет автоматически
загружаться при старте сервиса, если её ещё нет локально.

## Сборка и запуск образа
Соберите образ:

```bash
docker build -t llm-svc .
``` 

Запустите контейнер:

``` bash
docker run -d -p 8000:8000 llm-svc
```

Обратитесь к сервису 

Базовый запрос к чату:

* без поддержки stream `stream=false`

```bash 
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-Instruct-4b-chat",
    "messages": [
      {"role": "user", "content": "Расскажи о квантовых компьютерах"}
    ],
    "stream": false
  }'
```

 Потоковый запрос:

* c поддержкой stream `stream=true`

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "model": "Qwen3-Instruct-4b-chat",
    "messages": [
      {"role": "system", "content": "Ты полезный ассистент"},
      {"role": "user", "content": "Напиши короткий рассказ"}
    ],
    "stream": true
  }'
```

Формат потокового ответа (SSE)

```plaintext
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"Qwen3-Instruct-4b-chat","choices":[{"index":0,"delta":{"content":"Привет"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"Qwen3-Instruct-4b-chat","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}

data: [DONE]
```

## Настройка LibreChat
В LibreChat перейдите в настройки (шестерёнка в левом нижнем углу)

* Выберите "OpenAI" как провайдера
* В поле "OpenAI API Key" введите любой текст
* В поле "OpenAPI API Base" введите http://localhost:8000/v1

Сохраните настройки и начните общение

Запустите сервисы:

```bash
docker-compose up -d
```
Откройте LibreChat в браузере: http://localhost:3080


### Различия между типами сообщений в Chat Completion API
Разберём различия между типами сообщений и предназначение каждого из них в контексте Chat Completion API:

1. `ChatCompletionRequestSystemMessage`

    Предназначение: Системные сообщения используются для задания поведения ассистента, установки контекста или предоставления инструкций высокого уровня.
    
    Особенности:
    
    Роль: `system`
    
    * Содержит инструкции для модели о том, как она должна себя вести
    
    * Обычно передаётся первым в диалоге
    
    * Может устанавливать личность ассистента, тон общения, правила поведения
    
    * Не основано на взаимодействии с пользователем
    
    Пример:
    
    ```python
    {
      "role": "system",
      "content": "Ты - полезный ассистент, который говорит на русском языке и специализируется на программировании."
    }
    ```

2. `ChatCompletionRequestUserMessage`

    Предназначение: Сообщения от пользователя, представляющие запросы, вопросы или инструкции, на которые должна ответить модель.
    
    Особенности:
    
    Роль: `user`
    
    * Содержит непосредственный запрос пользователя
    
    * Может быть текстом или сложной структурой (в случае multimodal моделей)
    
    * Формирует основной контекст для генерации ответа
    
    Пример:
    
    ```python
    {
      "role": "user", 
      "content": "Объясни, что такое асинхронное программирование в Python."
    }
    ```

3. `ChatCompletionRequestAssistantMessage`

    Предназначение: Сообщения от ассистента (модели), представляющие ответы на предыдущие запросы пользователя.
    
    Особенности:
    
    Роль: `assistant`
    
    * Содержит сгенерированные моделью ответы
    
      * Могут включать вызовы функций/tools (через поле tool_calls)
    
      * Используются для поддержания контекста диалога
    
      * Могут быть предоставлены как примеры желаемого поведения (few-shot learning)
    
    Пример:
    
    ```python
    {
      "role": "assistant",
      "content": "Асинхронное программирование в Python позволяет выполнять операции без блокировки основного потока..."
    }
    ```

4. `ChatCompletionRequestToolMessage`

    Предназначение: Сообщения, содержащие результаты выполнения функций (tools), которые были вызваны ассистентом.
    
    Особенности:
    
    Роль: `tool`
    
    * Содержит результаты выполнения внешних функций
    
    * Обязательно включает tool_call_id для связи с конкретным вызовом функции
    
    * Позволяет модели использовать внешние API и сервисы
    
    * Используется в комбинации с вызовами функций от ассистента
    
    Пример:
    
    ```python
    {
      "role": "tool",
      "content": "{\"temperature\": 22, \"humidity\": 45}",
      "tool_call_id": "call_abc123"
    }
    ```

5. `ChatCompletionRequestFunctionMessage`

    Предназначение: Сообщения, содержащие результаты выполнения функций (устаревший формат, в основном заменён на ToolMessage).
    
    Особенности:
    
    Роль: `function`
    
    * Аналогично ToolMessage, но для устаревшего API функций
    
    * Содержит результат выполнения функции и имя функции
    
    * Использовалось в более старых версиях API до введения инструментов (tools)
    
    Пример:
    
    ```python
    {
      "role": "function", 
      "content": "{\"temperature\": 22, \"humidity\": 45}",
      "name": "get_weather"
    }
    ```

### Сравнительная таблица

| *Тип сообщения*	   | *Роль*    | *Предназначение*                           | *Обязательные поля*   |
|--------------------|-----------|--------------------------------------------|-----------------------|
| `SystemMessage`    | system    | Инструкции                                 | content               |
| `UserMessage`	     | user      | Запросы пользователя                       | content               |
| `AssistantMessage` | assistant | Ответы модели                              | content (опционально) |
| `ToolMessage`      | tool      | Результаты выполнения инструментов         | content, tool_call_id |
| `FunctionMessage`  | function  | Результаты выполнения функций (устаревшее) | content, name         |


### Практическое использование в диалоге

Типичная последовательность сообщений в диалоге:

* `SystemMessage` - задаёт поведение модели
* `UserMessage` - запрос пользователя
* `AssistantMessage` - ответ модели (может включать вызовы инструментов)
* `ToolMessage` - результаты выполнения инструментов (если были вызваны)
* `AssistantMessage` - окончательный ответ с учётом результатов инструментов

## Лицензия

MIT License