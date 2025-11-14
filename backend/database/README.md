# Модуль работы с базами данных

Этот модуль обеспечивает работу с двумя базами данных:
- **MongoDB** - для хранения диалогов
- **PostgreSQL + pgvector** - для RAG системы

## Структура модуля

```
backend/database/
├── __init__.py              # Основные экспорты
├── init_db.py               # Инициализация подключений
├── mongodb/                 # MongoDB модуль
│   ├── __init__.py
│   ├── connection.py        # Подключение к MongoDB
│   ├── models.py            # Модели данных (Conversation, Message)
│   └── repository.py        # Репозиторий для работы с диалогами
└── postgresql/              # PostgreSQL модуль
    ├── __init__.py
    ├── connection.py        # Подключение к PostgreSQL
    ├── models.py            # Модели данных (Document, DocumentVector)
    └── repository.py        # Репозитории для работы с документами и векторами
```

## Использование

### Инициализация

```python
from backend.database.init_db import init_databases, get_conversation_repository, get_vector_repository

# Инициализация всех подключений
await init_databases()

# Получение репозиториев
conversation_repo = get_conversation_repository()
vector_repo = get_vector_repository()
```

### Работа с диалогами (MongoDB)

```python
from backend.database.mongodb.models import Conversation, Message
from datetime import datetime

# Создание диалога
conversation = Conversation(
    conversation_id="conv_123",
    user_id="user_456",
    title="Разговор о Python",
    messages=[]
)

# Добавление сообщения
message = Message(
    message_id="msg_1",
    role="user",
    content="Привет!",
    timestamp=datetime.utcnow()
)

# Сохранение в БД
await conversation_repo.create_conversation(conversation)
await conversation_repo.add_message("conv_123", message)

# Поиск диалогов
conversations = await conversation_repo.get_user_conversations("user_456")
search_results = await conversation_repo.search_conversations("Python")
```

### Работа с RAG (PostgreSQL + pgvector)

```python
from backend.database.postgresql.models import Document, DocumentVector
from backend.database.init_db import get_document_repository, get_vector_repository

document_repo = get_document_repository()
vector_repo = get_vector_repository()

# Создание документа
document = Document(
    filename="example.pdf",
    content="Содержимое документа...",
    metadata={"type": "pdf", "pages": 10}
)

doc_id = await document_repo.create_document(document)

# Создание вектора
vector = DocumentVector(
    document_id=doc_id,
    chunk_index=0,
    embedding=[0.1, 0.2, 0.3, ...],  # Вектор эмбеддинга
    content="Фрагмент текста",
    metadata={"start_char": 0, "end_char": 500}
)

await vector_repo.create_vector(vector)

# Поиск похожих документов
query_embedding = [0.15, 0.25, 0.35, ...]
similar_docs = await vector_repo.similarity_search(query_embedding, limit=10)
```

## Переменные окружения

Убедитесь, что в вашем `.env` файле заданы следующие переменные:

```env
# MongoDB
MONGODB_HOST=mongodb
MONGODB_PORT=27017
MONGODB_DATABASE=memoai
MONGODB_USER=admin
MONGODB_PASSWORD=password

# PostgreSQL
POSTGRES_HOST=postgresql
POSTGRES_PORT=5432
POSTGRES_DB=memoai
POSTGRES_USER=admin
POSTGRES_PASSWORD=password
EMBEDDING_DIM=384
```

## Docker Compose

Модуль автоматически подключается к БД через Docker Compose:

```yaml
services:
  mongodb:
    image: mongo:7
    # ...
  
  postgresql:
    image: pgvector/pgvector:pg16
    # ...
```

## Зависимости

Необходимые пакеты уже добавлены в `requirements.txt`:
- `motor` - асинхронный драйвер для MongoDB
- `pymongo` - синхронный драйвер для MongoDB
- `asyncpg` - асинхронный драйвер для PostgreSQL
- `psycopg2-binary` - синхронный драйвер для PostgreSQL
- `numpy` - для работы с векторами

## Миграции

При первом запуске модуль автоматически:
- Создает индексы в MongoDB
- Создает таблицы в PostgreSQL
- Настраивает pgvector расширение






















