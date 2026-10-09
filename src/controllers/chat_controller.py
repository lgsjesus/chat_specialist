import json
import time
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from opentelemetry import trace

from src.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SearchRequest,
    SearchResponse,
)
from src.services.query_planner import query_planner
from src.services.rag_service import rag_service
from src.utils.telemetry import (
    record_exception,
    safe_add_event,
    safe_set_attribute,
    setup_telemetry,
)

tracer = setup_telemetry(__name__)
router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(request: ChatRequest):
    """Executa consulta RAG com QueryPlanner: clarificação de intenção via IA, busca vetorial e síntese LLM."""
    with tracer.start_as_current_span("http.chat") as span:
        safe_set_attribute(span, "http.route", "/chat")
        safe_set_attribute(span, "chat.question", request.question)
        safe_set_attribute(span, "chat.history_messages", len(request.history or []))
        safe_set_attribute(span, "chat.filters", request.filters)
        t0 = time.perf_counter()
        span.add_event("request.received")
        try:
            response = await query_planner.answer_query(
                question=request.question,
                history=request.history,
                custom_filter=request.filters,
            )
            _record_response(span, response, t0)
            return response
        except Exception as exc:
            record_exception(span, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao processar consulta RAG: {str(exc)}",
            )


def _record_response(span, response: ChatResponse, t0: float):
    """Registra no span o resumo da resposta: fontes recuperadas, scores e latências."""
    total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    scores = [s.score for s in response.sources if s.score is not None]
    safe_set_attribute(span, "chat.sources_count", len(response.sources))
    if scores:
        safe_set_attribute(span, "chat.score.best", min(scores))
        safe_set_attribute(span, "chat.score.worst", max(scores))
    safe_set_attribute(span, "chat.answer_chars", len(response.answer))
    safe_set_attribute(span, "chat.rag_latency_ms", response.latency_ms)
    safe_set_attribute(span, "chat.total_latency_ms", total_ms)
    safe_add_event(span, "response.sent", {"total_latency_ms": total_ms, "sources": len(response.sources)})


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Endpoint de streaming (SSE): clarificação de intenção via QueryPlanner e respostas token a token."""
    # Span manual: o ciclo de vida se estende até o fim do streaming (fora do escopo desta função).
    span = tracer.start_span("http.chat_stream")
    safe_set_attribute(span, "http.route", "/chat/stream")
    safe_set_attribute(span, "chat.question", request.question)
    safe_set_attribute(span, "chat.history_messages", len(request.history or []))
    safe_set_attribute(span, "chat.filters", request.filters)
    span.add_event("request.received")
    t0 = time.perf_counter()
    try:
        with trace.use_span(span, end_on_exit=False):
            query_plan, token_stream = await query_planner.stream_query(
                question=request.question,
                history=request.history,
                custom_filter=request.filters,
            )
        safe_add_event(span, "plan.ready", {"clarified_query": query_plan.clarified_query})

        async def event_generator():
            n_tokens = 0
            first_token_ms = None
            try:
                # Notifica o cliente sobre a intenção identificada e pergunta clarificada
                initial_meta = json.dumps({"plan": query_plan.model_dump()}, ensure_ascii=False)
                yield f"data: {initial_meta}\n\n"

                iterator = token_stream.__aiter__()
                while True:
                    # Reanexa o span como pai APENAS durante o avanço do gerador (nunca através de um yield)
                    with trace.use_span(span, end_on_exit=False):
                        try:
                            token = await iterator.__anext__()
                        except StopAsyncIteration:
                            break
                    if first_token_ms is None:
                        first_token_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                        safe_add_event(span, "stream.first_token", {"elapsed_ms": first_token_ms})
                    n_tokens += 1
                    payload = json.dumps({"token": token}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                yield "data: [DONE]\n\n"
            except BaseException as exc:
                if not isinstance(exc, GeneratorExit):
                    record_exception(span, exc)
                else:
                    span.add_event("stream.client_disconnected")
                raise
            finally:
                total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                safe_set_attribute(span, "chat.stream_chunks", n_tokens)
                safe_set_attribute(span, "chat.time_to_first_token_ms", first_token_ms)
                safe_set_attribute(span, "chat.total_latency_ms", total_ms)
                span.add_event("stream.finished", {"total_latency_ms": total_ms, "chunks": n_tokens})
                span.end()

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as exc:
        record_exception(span, exc)
        span.end()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no streaming RAG: {str(exc)}",
        )


@router.post("/search", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def search_chunks(request: SearchRequest):
    """Endpoint de diagnóstico de recuperação vetorial. Retorna os chunks e pontuações de similaridade sem acionar o LLM."""
    with tracer.start_as_current_span("http.chat_search") as span:
        safe_set_attribute(span, "http.route", "/chat/search")
        safe_set_attribute(span, "chat.question", request.question)
        safe_set_attribute(span, "chat.filters", request.filters)
        t0 = time.perf_counter()
        try:
            results = await rag_service.search(
                query=request.question,
                filter_dict=request.filters,
            )
            total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            safe_set_attribute(span, "chat.sources_count", len(results))
            safe_set_attribute(span, "chat.total_latency_ms", total_ms)
            safe_add_event(span, "response.sent", {"total_latency_ms": total_ms, "results": len(results)})
            return SearchResponse(
                question=request.question,
                results=results,
                total=len(results),
            )
        except Exception as exc:
            record_exception(span, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro na busca de similaridade: {str(exc)}",
            )

