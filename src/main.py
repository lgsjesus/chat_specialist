import sys
import asyncio
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.controllers.router import api_router
from src.infra.database import database
from src.utils.create_database import enable_pgvector, test_connection


# Configura saída do console para UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ajuste de event loop para Windows se necessário
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação (startup e shutdown)."""
    print("\n🚀 Iniciando TeleTech Chat Specialist API...")
    try:
        await test_connection()
        await enable_pgvector()
        print("✅ Banco de dados e extensão pgvector inicializados com sucesso.")
    except Exception as exc:
        print(f"⚠️ Alerta durante startup do banco de dados: {exc}")

    yield

    print("\n🛑 Encerrando aplicação e liberando pools de conexão...")
    await database.engine.dispose()
    print("✅ Recursos finalizados.")


app = FastAPI(
    title="TeleTech Chat Specialist - RAG API",
    description="API de Atendimento e Consulta Corporativa RAG da TeleTech Brasil utilizando LangChain (LCEL) e PostgreSQL pgvector.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configuração de CORS para permitir integração com interfaces web/mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handler global para capturar e formatar erros não tratados."""
    print(f"❌ Erro interno não tratado em {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Ocorreu um erro interno no processamento da requisição.",
            "error": str(exc),
        },
    )


# Inclusão dos roteadores (Health, Chat RAG e Ingestão)
app.include_router(api_router)


@app.get("/", tags=["Root"])
async def root():
    """Endpoint raiz com informações e links úteis da API."""
    return {
        "service": "TeleTech Chat Specialist - RAG API",
        "version": "1.0.0",
        "documentation": "/docs",
        "health": "/health",
        "endpoints": {
            "chat": "/api/v1/chat",
            "chat_stream": "/api/v1/chat/stream",
            "search": "/api/v1/chat/search",
            "ingest_knowledge_docs": "/api/v1/ingest/knowledge-docs",
            "ingest_single_doc": "/api/v1/ingest/document",
        },
    }


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
