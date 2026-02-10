# Модуль настроек для astrachat Backend

Централизованное управление конфигурацией и подключениями к внешним сервисам.

## Структура

```
backend/settings/
├── __init__.py          # Экспорт всех классов
├── connections.py       # Классы конфигурации подключений
├── config.py           # Основной класс Settings
└── README.md           # Документация
```

## Использование

### Базовое использование

```python
from settings import get_settings

# Получение настроек
settings = get_settings()

# Доступ к конфигурации подключений
mongodb_config = settings.mongodb
postgresql_config = settings.postgresql
minio_config = settings.minio
llm_service_config = settings.llm_service

# Использование строк подключения
mongodb_connection_string = mongodb_config.connection_string
postgresql_connection_string = postgresql_config.connection_string
```

### Использование в существующем коде

```python
from settings import get_settings

settings = get_settings()

# Вместо os.getenv("MONGODB_HOST", "localhost")
host = settings.mongodb.host

# Вместо формирования строки подключения вручную
connection_string = settings.mongodb.connection_string
```

### Получение URL для LLM Service

```python
from settings import get_settings

settings = get_settings()
llm_url = settings.get_llm_service_url()  # Автоматически выбирает Docker или локальный URL
```

## Классы подключений

### MongoDBConnectionConfig

- `host`: Хост MongoDB
- `port`: Порт MongoDB
- `database`: Имя базы данных
- `user`: Пользователь (опционально)
- `password`: Пароль (опционально)
- `connection_string`: Свойство, возвращающее готовую строку подключения

### PostgreSQLConnectionConfig

- `host`: Хост PostgreSQL
- `port`: Порт PostgreSQL
- `database`: Имя базы данных
- `user`: Пользователь
- `password`: Пароль
- `embedding_dim`: Размерность векторов для эмбеддингов
- `connection_string`: Свойство, возвращающее готовую строку подключения

### MinIOConnectionConfig

- `endpoint`: Endpoint MinIO
- `port`: Порт MinIO
- `access_key`: Access key
- `secret_key`: Secret key
- `use_ssl`: Использовать SSL
- `bucket_name`: Имя bucket для временных файлов
- `documents_bucket_name`: Имя bucket для документов
- `full_endpoint`: Свойство, возвращающее полный endpoint с портом

### LLMServiceConnectionConfig

- `enabled`: Включен ли LLM Service
- `timeout`: Таймаут запросов
- `retry_attempts`: Количество попыток повтора
- `retry_delay`: Задержка между попытками
- `base_url`: Базовый URL (определяется из config.yml)
- `external_url`: Внешний URL (определяется из config.yml)

## Приоритет источников конфигурации

1. **Переменные окружения** (env) - высший приоритет
2. **YAML файл** (config.yml) - средний приоритет
3. **Значения по умолчанию** - низший приоритет

## Миграция существующего кода

### До миграции

```python
import os

host = os.getenv("MONGODB_HOST", "localhost")
port = os.getenv("MONGODB_PORT", "27017")
database = os.getenv("MONGODB_DATABASE", "astrachat")
user = os.getenv("MONGODB_USER", "").strip()
password = os.getenv("MONGODB_PASSWORD", "").strip()

if user and password:
    connection_string = f"mongodb://{user}:{password}@{host}:{port}/"
else:
    connection_string = f"mongodb://{host}:{port}/"
```

### После миграции

```python
from settings import get_settings

settings = get_settings()
connection_string = settings.mongodb.connection_string
```

## Примеры использования

### Инициализация MongoDB

```python
from settings import get_settings
from database.mongodb.connection import MongoDBConnection

settings = get_settings()
mongodb_config = settings.mongodb

connection = MongoDBConnection(
    mongodb_config.connection_string,
    mongodb_config.database
)
await connection.connect()
```

### Инициализация PostgreSQL

```python
from settings import get_settings
from database.postgresql.connection import PostgreSQLConnection

settings = get_settings()
pg_config = settings.postgresql

connection = PostgreSQLConnection(
    host=pg_config.host,
    port=pg_config.port,
    database=pg_config.database,
    user=pg_config.user,
    password=pg_config.password
)
await connection.connect()
```

### Инициализация MinIO

```python
from settings import get_settings
from database.minio import get_minio_client

settings = get_settings()
minio_config = settings.minio

# MinIO клиент использует настройки из settings автоматически
minio_client = get_minio_client()
```

## Перезагрузка конфигурации

```python
from settings import reset_settings

# Принудительная перезагрузка (например, после изменения config.yml)
settings = reset_settings()
```















