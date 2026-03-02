# Роуты API: эмбеддинги, реранкер, хелсчек
from fastapi import APIRouter
from .endpoints import embed, rerank, health

router = APIRouter()
router.include_router(embed.router, tags=["Эмбеддинги"])
router.include_router(rerank.router, tags=["Реранкер"])
router.include_router(health.router, tags=["Здоровье"])
