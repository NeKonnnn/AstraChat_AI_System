import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import diarization
from app.dependencies.diarization_handler import get_diarization_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GPB Diarization Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(diarization.router, prefix="/api", tags=["diarization"])

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Diarization Service...")
    await get_diarization_handler()
    logger.info("Service Ready!")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "diarization"}