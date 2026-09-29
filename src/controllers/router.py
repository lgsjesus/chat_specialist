from fastapi import APIRouter
from src.controllers.chat_controller import router as chat_router
from src.controllers.health_controller import router as health_router
from src.controllers.ingestion_controller import router as ingestion_router

api_router = APIRouter()

# Rotas de Saúde
api_router.include_router(health_router)

# Rotas de Negócio sob /api/v1
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(chat_router)
v1_router.include_router(ingestion_router)

api_router.include_router(v1_router)