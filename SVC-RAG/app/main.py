import logging
import time
import uuid
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api import router as api_router
from app.dependencies import get_db

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.logging.level.upper(), logging.INFO),
    format=settings.logging.format,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Uvicorn может поднять порог root-логгера — явно включаем INFO для наших модулей (баннеры метрик RAG)
        root = logging.getLogger()
        if root.level > logging.INFO:
            root.setLevel(logging.INFO)
        for _name in (
            "app",
            "app.services",
            "app.services.rag_search_helpers",
            "app.services.retrieval_eval",
            "app.services.rag_service",
            "app.services.kb_service",
            "app.services.memory_rag_service",
            "app.services.project_rag_service",
        ):
            logging.getLogger(_name).setLevel(logging.INFO)

        await get_db()
        logger.info("SVC-RAG: БД подключена, таблицы готовы")
    except Exception as e:
        logger.error("SVC-RAG: ошибка старта БД: %s", e, exc_info=True)
        raise
    yield
    logger.info("SVC-RAG: shutdown")


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.app.title,
        description=settings.app.description,
        version=settings.app.version,
        lifespan=lifespan,
        docs_url=settings.server.docs_url,
        redoc_url=settings.server.redoc_url,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allowed_origins,
        allow_credentials=settings.cors.allow_credentials,
        allow_methods=settings.cors.allow_methods,
        allow_headers=settings.cors.allow_headers,
    )
    app.include_router(api_router, prefix="/v1")
    return app


app = create_application()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    logger.info("%s %s %s", request_id, request.method, request.url.path)
    response = await call_next(request)
    logger.info("%s %s %s %s", request_id, request.method, request.url.path, response.status_code)
    return response


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        log_level=settings.server.log_level.lower(),
    )
