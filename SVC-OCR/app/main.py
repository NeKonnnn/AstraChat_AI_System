import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import ocr
from app.dependencies.surya_handler import get_surya_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GPB OCR Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr.router, prefix="/api", tags=["ocr"])

@app.on_event("startup")
async def startup_event():
    logger.info("Starting OCR Service...")
    # Предзагрузка моделей
    await get_surya_handler()
    logger.info("Service Ready!")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "GPB-CORSUR-SVC-OCR"}