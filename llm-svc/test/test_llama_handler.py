import pytest
from unittest.mock import MagicMock

from app.services.llama_handler import LlamaHandler
from app.models.schemas import Message


@pytest.fixture
def llama_handler():
    """Создание экземпляра LlamaHandler для тестов."""
    return LlamaHandler()


@pytest.mark.asyncio
async def test_generate_response_not_loaded(llama_handler):
    """Тест генерации ответа когда модель не загружена."""
    llama_handler.is_initialized = False

    with pytest.raises(ValueError, match="Model not loaded"):
        await llama_handler.generate_response([Message(role="user", content="Hello")])


@pytest.mark.asyncio
async def test_cleanup(llama_handler):
    """Тест очистки ресурсов."""
    llama_handler.model = MagicMock()
    llama_handler.is_initialized = True

    await llama_handler.cleanup()

    assert llama_handler.model is None
    assert llama_handler.is_initialized is False


def test_is_loaded(llama_handler):
    """Тест проверки загрузки модели."""
    # Модель не загружена
    assert llama_handler.is_loaded() is False

    # Модель загружена
    llama_handler.model = MagicMock()
    llama_handler.is_initialized = True
    assert llama_handler.is_loaded() is True

