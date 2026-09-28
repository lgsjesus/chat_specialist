from fastapi import APIRouter, status
from sqlalchemy import text
from src.infra.database import database

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Verifica a integridade da aplicação e a conectividade com o PostgreSQL e a extensão pgvector."""
    db_connected = False
    pgvector_ready = False
    error_msg = None

    try:
        async with database.session() as session:
            # 1. Verifica conexão básica
            res = await session.execute(text("SELECT 1;"))
            if res.scalar() == 1:
                db_connected = True

            # 2. Verifica extensão pgvector
            vec_res = await session.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
            )
            if vec_res.scalar() == "vector":
                pgvector_ready = True
    except Exception as exc:
        error_msg = str(exc)

    return {
        "status": "healthy" if db_connected and pgvector_ready else "degraded",
        "database_connected": db_connected,
        "pgvector_ready": pgvector_ready,
        "error": error_msg,
    }
