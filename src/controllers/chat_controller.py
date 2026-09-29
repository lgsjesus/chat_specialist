import json
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from src.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SearchRequest,
    SearchResponse,
)
from src.services.query_planner import query_planner
from src.services.rag_service import rag_service

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(request: ChatRequest):
    """Executa consulta RAG com QueryPlanner: clarificação de intenção via IA, busca vetorial e síntese LLM."""
    try:
        response = await query_planner.answer_query(
            question=request.question,
            history=request.history,
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
    """Endpoint de streaming (SSE): clarificação de intenção via QueryPlanner e respostas token a token."""
    try:
        query_plan, token_stream = await query_planner.stream_query(
            question=request.question,
            history=request.history,
            custom_filter=request.filters,
        )

        async def event_generator():
            # Notifica o cliente sobre a intenção identificada e pergunta clarificada
            initial_meta = json.dumps({"plan": query_plan.model_dump()}, ensure_ascii=False)
            yield f"data: {initial_meta}\n\n"

            async for token in token_stream:
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
