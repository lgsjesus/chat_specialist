import json
import logging
from typing import Any, AsyncGenerator, Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.infra.ai_factory import get_chat_model
from src.schemas.chat import ChatMessage, ChatResponse, QueryPlan
from src.services.rag_service import rag_service

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
        history_msgs = self._format_history(history)

        # 1. Tentativa via structured output (Pydantic nativo)
        if self.structured_chain:
            try:
                plan_result: QueryPlan = await self.structured_chain.ainvoke({
                    "question": question,
                    "history": history_msgs,
                })
                if isinstance(plan_result, QueryPlan):
                    return plan_result
            except Exception as exc:
                logger.warning("Erro ao executar structured_chain (%s). Tentando parser JSON manual.", exc)

        # 2. Fallback: chamada raw e parser de JSON
        try:
            raw_response = await self.raw_chain.ainvoke({
                "question": question,
                "history": history_msgs,
            })
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
            return QueryPlan(
                intent=parsed.get("intent", "Consulta de informações TeleTech"),
                clarified_query=parsed.get("clarified_query", question),
                entities=parsed.get("entities", []),
                keywords=parsed.get("keywords", []),
            )
        except Exception as exc:
            logger.error("Falha no parser de intenção do QueryPlanner (%s). Utilizando fallback padrão.", exc)

        # 3. Fallback seguro e resiliente (mantém a pergunta original sem quebrar o fluxo)
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
        query_plan = await self.plan(question=question, history=history)

        response = await rag_service.answer_query(
            query=query_plan.clarified_query,
            history=history,
            tenant=tenant,
            custom_filter=custom_filter,
            top_k=top_k,
        )

        response.query_plan = query_plan
        return response

    async def stream_query(
        self,
        question: str,
        history: Optional[list[ChatMessage]] = None,
        tenant: Optional[str] = "teletech",
        custom_filter: Optional[dict[str, Any]] = None,
        top_k: int = 4,
    ) -> tuple[QueryPlan, AsyncGenerator[str, None]]:
        """Fluxo de streaming: gera o plano e retorna o gerador de tokens do RAGService."""
        query_plan = await self.plan(question=question, history=history)
        token_stream = rag_service.stream_query(
            query=query_plan.clarified_query,
            history=history,
            tenant=tenant,
            custom_filter=custom_filter,
            top_k=top_k,
        )
        return query_plan, token_stream


query_planner = QueryPlanner()
