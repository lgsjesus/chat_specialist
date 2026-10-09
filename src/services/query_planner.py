import json
import logging
import uuid
from typing import Any, AsyncGenerator, Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.infra.ai_factory import get_chat_model
from src.schemas.chat import ChatMessage, ChatResponse, QueryPlan
from src.services.rag_service import rag_service
from src.utils.telemetry import (
    LLMTelemetryCallback,
    record_exception,
    safe_add_event,
    safe_set_attribute,
    setup_telemetry,
)

logger = logging.getLogger(__name__)

QUERY_PLANNER_SYSTEM_PROMPT = """Você é o Query Planner da TeleTech Brasil, especialista em telecomunicações e inteligência de recuperação de dados (RAG).
Sua função é analisar a mensagem do usuário (e o histórico recente de diálogo, se houver) antes da busca vetorial na base de conhecimento oficial da TeleTech.

Objetivos:
1. IDENTIFICAR A INTENÇÃO: Entender com precisão o que o usuário quer saber ou resolver (ex: contratação de plano fibra/móvel, valores e promoções, cancelamento e multa de fidelidade, contestação de fatura, suporte técnico, cobertura/disponibilidade).
2. CLARIFICAR E REESCREVER A CONSULTA (clarified_query):
   - Elimine saudações e ruídos conversacionais ("olá", "bom dia", "por favor me tira uma dúvida").
   - Resolva pronomes e anáforas com base no histórico ("quanto custa ele?" -> "qual o valor mensal do plano TeleTech Fibra 500 Mega?").
   - Enriqueça a consulta com terminologia técnica e institucional da TeleTech Brasil (ex: "TeleTech Fibra", "TeleTech Móvel 5G", "franquia de dados", "fidelidade 12 meses", "SVA").
   - Esta pergunta reescrita será enviada DIRETAMENTE para a busca semântica no banco vetorial pgvector.
   - Se ficar com duvidas não tente advinhar, questione ao usuário.
3. EXTRAIR ENTIDADES: Produtos, planos, serviços ou tópicos citados (ex: ['TeleTech Fibra 500 Mega', 'Multa Contratual']).
4. EXTRAIR PALAVRAS-CHAVE: Termos essenciais para busca semântica.

Você DEVE responder SEMPRE em formato JSON estrito, sem markdown adicional ao redor se possível, seguindo a estrutura:
{{
  "intent": "Resumo claro e conciso da intenção do usuário",
  "clarified_query": "Consulta enriquecida e desambiguada otimizada para recuperação vetorial",
  "entities": ["entidade1", "entidade2"],
  "keywords": ["termo1", "termo2", "termo3"]
}}
"""


class QueryPlanner:
    def __init__(self):
        self.llm = get_chat_model()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_PLANNER_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "Pergunta atual do usuário: {question}"),
        ])
        self.tracer = setup_telemetry(__name__)
        # Tenta configurar saída estruturada se suportada pelo modelo
        try:
            self.structured_llm = self.llm.with_structured_output(QueryPlan)
            self.structured_chain = self.prompt | self.structured_llm
        except Exception as exc:
            logger.warning("Falha ao inicializar structured_output no LLM (%s). Usando fallback JSON.", exc)
            self.structured_chain = None

        # Fallback LCEL chain direta
        self.raw_chain = self.prompt | self.llm

    def _format_history(self, history: Optional[list[ChatMessage]]) -> list[HumanMessage | AIMessage]:
        """Converte mensagens do schema Pydantic para classes de mensagem do LangChain."""
        if not history:
            return []
        formatted = []
        for msg in history:
            role = msg.role.lower()
            if role == "user":
                formatted.append(HumanMessage(content=msg.content))
            elif role in ("assistant", "system"):
                formatted.append(AIMessage(content=msg.content))
        return formatted

    async def plan(
        self,
        question: str,
        history: Optional[list[ChatMessage]] = None,
    ) -> QueryPlan:
        """Analisa a pergunta do usuário e o histórico, extraindo a intenção e clarificando a busca."""
        with self.tracer.start_as_current_span("planner.plan") as span:
            safe_set_attribute(span, "planner.question", question)
            safe_set_attribute(span, "planner.history_messages", len(history or []))
            result = await self._plan(question, history, span)
            safe_set_attribute(span, "planner.intent", result.intent)
            safe_set_attribute(span, "planner.clarified_query", result.clarified_query)
            safe_set_attribute(span, "planner.entities", ", ".join(result.entities))
            safe_set_attribute(span, "planner.keywords", ", ".join(result.keywords))
            return result

    async def _plan(self, question: str, history: Optional[list[ChatMessage]], span) -> QueryPlan:
        history_msgs = self._format_history(history)
        cfg = {"callbacks": [LLMTelemetryCallback("planner.plan")]}

        # 1. Tentativa via structured output (Pydantic nativo)
        if self.structured_chain:
            try:
                plan_result: QueryPlan = await self.structured_chain.ainvoke({
                    "question": question,
                    "history": history_msgs,
                }, config=cfg)
                if isinstance(plan_result, QueryPlan):
                    safe_set_attribute(span, "planner.strategy", "structured_output")
                    return plan_result
            except Exception as exc:
                logger.warning("Erro ao executar structured_chain (%s). Tentando parser JSON manual.", exc)
                safe_add_event(span, "planner.structured_failed", {"error": str(exc)})

        # 2. Fallback: chamada raw e parser de JSON
        try:
            raw_response = await self.raw_chain.ainvoke({
                "question": question,
                "history": history_msgs,
            }, config=cfg)
            content = raw_response.content if hasattr(raw_response, "content") else str(raw_response)

            # Limpa possíveis blocos ```json ... ```
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            parsed = json.loads(cleaned)
            safe_set_attribute(span, "planner.strategy", "json_fallback")
            return QueryPlan(
                intent=parsed.get("intent", "Consulta de informações TeleTech"),
                clarified_query=parsed.get("clarified_query", question),
                entities=parsed.get("entities", []),
                keywords=parsed.get("keywords", []),
            )
        except Exception as exc:
            logger.error("Falha no parser de intenção do QueryPlanner (%s). Utilizando fallback padrão.", exc)
            safe_add_event(span, "planner.json_fallback_failed", {"error": str(exc)})

        # 3. Fallback seguro e resiliente (mantém a pergunta original sem quebrar o fluxo)
        safe_set_attribute(span, "planner.strategy", "default_fallback")
        return QueryPlan(
            intent="Consulta Geral TeleTech",
            clarified_query=question,
            entities=[],
            keywords=[w for w in question.split() if len(w) > 3],
        )


    async def answer_query(
        self,
        question: str,
        history: Optional[list[ChatMessage]] = None,
        tenant: Optional[str] = "teletech",
        custom_filter: Optional[dict[str, Any]] = None,
        top_k: int = 4,
    ) -> ChatResponse:
        """Fluxo completo: clarifica a intenção via QueryPlanner e executa o RAGService."""
        with self.tracer.start_as_current_span("answer_query") as span:
            request_id = str(uuid.uuid4())
            safe_set_attribute(span, "request_id", request_id)
            safe_set_attribute(span, "tenant", tenant)
            try:
                logger.info(f"[request_id={request_id}] Iniciando answer_query (tenant='{tenant}', question='{question}')")
                span.add_event("Iniciando planejamento de resposta")
                query_plan = await self.plan(question=question, history=history)
                logger.info(f"[request_id={request_id}] intent='{query_plan.intent}' | clarified_query='{query_plan.clarified_query}'")
                safe_add_event(span, "Resposta planejamento", {"request_id": request_id, "clarified_query": query_plan.clarified_query})
                response = await rag_service.answer_query(
                    query=query_plan.clarified_query,
                    history=history,
                    tenant=tenant,
                    custom_filter=custom_filter,
                    top_k=top_k,
                )

                logger.info(f"[request_id={request_id}] finalizando answer_query com sucesso")
                response.query_plan = query_plan
                safe_set_attribute(span, "total_latency_ms", response.latency_ms)
                return response
            except Exception as exc:
                logger.error("error in answer", exc_info=exc)
                record_exception(span, exc)
                raise


    async def stream_query(
        self,
        question: str,
        history: Optional[list[ChatMessage]] = None,
        tenant: Optional[str] = "teletech",
        custom_filter: Optional[dict[str, Any]] = None,
        top_k: int = 4,
    ) -> tuple[QueryPlan, AsyncGenerator[str, None]]:
        """Fluxo de streaming: gera o plano e retorna o gerador de tokens do RAGService."""
        request_id = str(uuid.uuid4())
        logger.info(f"[request_id={request_id}] Iniciando stream_query (tenant='{tenant}', question='{question}')")
        query_plan = await self.plan(question=question, history=history)
        logger.info(f"[request_id={request_id}] intent='{query_plan.intent}' | clarified_query='{query_plan.clarified_query}'")
        token_stream = rag_service.stream_query(
            query=query_plan.clarified_query,
            history=history,
            tenant=tenant,
            custom_filter=custom_filter,
            top_k=top_k,
        )
        return query_plan, token_stream


query_planner = QueryPlanner()
