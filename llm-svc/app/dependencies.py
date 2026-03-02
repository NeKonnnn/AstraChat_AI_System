from app.services.models_service import LlamaService
async def get_llama_service() -> LlamaService:
    """Зависимость для получения сервиса LLM"""
    return await LlamaService.get_instance()
# Для обратной совместимости
get_llama_handler = get_llama_service
async def cleanup_llama_service() -> None:
    """Очистка сервиса LLM"""
    service = await LlamaService.get_instance()
    await service.cleanup()
