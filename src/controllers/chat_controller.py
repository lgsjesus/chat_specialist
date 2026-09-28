import json
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from src.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SearchRequest,
    SearchResponse,
)
from src.services.rag_service import rag_service

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(request: ChatRequest):
    """Executa consulta RAG: busca vetorial com filtros opcionais, injeção de contexto em LCEL e inferência LLM."""
    try:
        response = await rag_service.answer_query(
            query=request.question,
            custom_filter=request.filters,
        )
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar consulta RAG: {str(exc)}",
        )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Endpoint de streaming (SSE) para respostas em tempo real token a token via LCEL."""
    try:
        async def event_generator():
            async for token in rag_service.stream_query(
                query=request.question,
                custom_filter=request.filters,
            ):
                payload = json.dumps({"token": token}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no streaming RAG: {str(exc)}",
        )


@router.post("/search", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def search_chunks(request: SearchRequest):
    """Endpoint de diagnóstico de recuperação vetorial. Retorna os chunks e pontuações de similaridade sem acionar o LLM."""
    try:
        results = await rag_service.search(
            query=request.question,
            filter_dict=request.filters,
        )
        return SearchResponse(
            question=request.question,
            results=results,
            total=len(results),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na busca de similaridade: {str(exc)}",
        )
