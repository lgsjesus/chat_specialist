import time
from typing import Any, AsyncGenerator, Optional
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_postgres import PGVector

from src.infra.ai_factory import get_chat_model, get_collection_name, get_embeddings
from src.infra.config import settings
from src.infra.database import database
from src.schemas.chat import ChatMessage, ChatResponse, RetrievedChunk
from src.utils.telemetry import (
    LLMTelemetryCallback,
    record_exception,
    safe_add_event,
    safe_set_attribute,
    setup_telemetry,
)

tracer = setup_telemetry(__name__)

SYSTEM_PROMPT = """Você é o Especialista Virtual da TeleTech Brasil, um assistente corporativo de suporte e consultoria de telecomunicações.
Sua missão é fornecer respostas precisas, claras e amigáveis sobre os produtos, planos, coberturas, faturas, regras de suporte e políticas da TeleTech.

Diretrizes Obrigatórias:
1. Responda ESTRITAMENTE com base no contexto fornecido abaixo. NÃO invente informações, planos, valores ou regras que não estejam documentadas.
2. Se a informação solicitada não estiver contida no contexto, informe de forma cordial e transparente que o tópico não consta na base de conhecimento oficial da TeleTech Brasil.
3. Sempre que pertinente, mencione o nome do documento, plano ou seção de onde a informação foi extraída para dar transparência ao cliente.
4. Mantenha tom profissional, cordial, focado na resolução e na clareza.

Contexto Recuperado da Base de Conhecimento:
{context}
"""


class RAGService:
    def __init__(self, collection_name: Optional[str] = None):
        self.embeddings = get_embeddings()
        self.collection_name = collection_name or get_collection_name()
        self.vector_store = PGVector(
            embeddings=self.embeddings,
            collection_name=self.collection_name,
            connection=database.engine,
            use_jsonb=True,
            async_mode=True,
        )
        self.llm = get_chat_model()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ])
        # LCEL Chain: Prompt | ChatModel (Gemini/OpenAI) | StrOutputParser
        self.chain = self.prompt | self.llm | StrOutputParser()

    async def search(
        self,
        query: str,
        top_k: int = 4,
        filter_dict: Optional[dict[str, Any]] = None,
    ) -> list[RetrievedChunk]:
        """Recupera os trechos mais relevantes do PGVector com métricas de distância/similaridade."""
        with tracer.start_as_current_span("rag.search") as span:
            safe_set_attribute(span, "rag.collection", self.collection_name)
            safe_set_attribute(span, "rag.top_k", top_k)
            safe_set_attribute(span, "rag.filter", filter_dict)
            safe_set_attribute(span, "rag.query", query)
            t0 = time.perf_counter()
            try:
                # 1. Embedding da consulta (span próprio para isolar latência do provedor)
                with tracer.start_as_current_span("rag.embed_query") as emb_span:
                    safe_set_attribute(
                        emb_span,
                        "embedding.model",
                        getattr(self.embeddings, "model", None),
                    )
                    t_emb = time.perf_counter()
                    vector = await self.embeddings.aembed_query(query)
                    emb_ms = round((time.perf_counter() - t_emb) * 1000.0, 2)
                    safe_set_attribute(emb_span, "embedding.dimensions", len(vector))
                    safe_set_attribute(emb_span, "embedding.latency_ms", emb_ms)

                # 2. Consulta vetorial no pgvector
                with tracer.start_as_current_span("rag.vector_query") as vq_span:
                    t_q = time.perf_counter()
                    results = await self.vector_store.asimilarity_search_with_score_by_vector(
                        embedding=vector,
                        k=top_k,
                        filter=filter_dict,
                    )
                    q_ms = round((time.perf_counter() - t_q) * 1000.0, 2)
                    safe_set_attribute(vq_span, "vector_query.latency_ms", q_ms)
                    safe_set_attribute(vq_span, "vector_query.results", len(results))

                chunks: list[RetrievedChunk] = []
                for rank, (doc, score) in enumerate(results, 1):
                    chunk = RetrievedChunk(
                        content=doc.page_content,
                        metadata=doc.metadata,
                        score=round(float(score), 4),
                    )
                    chunks.append(chunk)
                    # Evento por chunk (score = distância do pgvector: menor = mais similar)
                    safe_add_event(span, "rag.chunk_retrieved", {
                        "rank": rank,
                        "score": chunk.score,
                        "title": doc.metadata.get("title"),
                        "doc_type": doc.metadata.get("doc_type"),
                        "section": doc.metadata.get("h1") or doc.metadata.get("h2") or doc.metadata.get("section"),
                        "content_chars": len(doc.page_content),
                    })

                total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                safe_set_attribute(span, "rag.results_count", len(chunks))
                if chunks:
                    scores = [c.score for c in chunks]
                    safe_set_attribute(span, "rag.score.best", min(scores))
                    safe_set_attribute(span, "rag.score.worst", max(scores))
                    safe_set_attribute(span, "rag.score.avg", round(sum(scores) / len(scores), 4))
                else:
                    span.add_event("rag.no_results")
                safe_set_attribute(span, "rag.embedding_latency_ms", emb_ms)
                safe_set_attribute(span, "rag.vector_query_latency_ms", q_ms)
                safe_set_attribute(span, "rag.latency_ms", total_ms)
                return chunks
            except Exception as exc:
                record_exception(span, exc)
                raise

    def _format_context(self, chunks: list[RetrievedChunk]) -> str:
        """Formata os chunks recuperados com delimitadores claros e metadados contextuais."""
        if not chunks:
            return "Nenhum documento relevante encontrado na base de dados."

        formatted_parts = []
        for i, chunk in enumerate(chunks, 1):
            title = chunk.metadata.get("title", "Documento Oficial")
            doc_type = chunk.metadata.get("doc_type", "Geral")
            section = chunk.metadata.get("h1") or chunk.metadata.get("h2") or chunk.metadata.get("section", "Geral")
            part = f"--- [Fonte {i}: {title} | Tipo: {doc_type} | Seção: {section}] ---\n{chunk.content}\n"
            formatted_parts.append(part)

        return "\n".join(formatted_parts)

    def _format_history(self, history: list[ChatMessage]) -> list[HumanMessage | AIMessage]:
        """Converte mensagens do schema Pydantic para classes de mensagem do LangChain."""
        formatted = []
        for msg in history:
            if msg.role.lower() == "user":
                formatted.append(HumanMessage(content=msg.content))
            elif msg.role.lower() in ("assistant", "system"):
                formatted.append(AIMessage(content=msg.content))
        return formatted

    def _build_filter(self, tenant: Optional[str], custom_filter: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Monta o filtro de metadados garantindo isolamento por tenant se configurado."""
        filters = {}
        if tenant:
            filters["tenant"] = tenant
        if custom_filter:
            filters.update(custom_filter)
        return filters if filters else None

    async def answer_query(
        self,
        query: str,
        history: Optional[list[ChatMessage]] = None,
        tenant: Optional[str] = "teletech",
        custom_filter: Optional[dict[str, Any]] = None,
        top_k: int = 4,
    ) -> ChatResponse:
        """Executa o pipeline RAG completo (Recuperação + Prompt LCEL + Geração LLM) de forma assíncrona."""
        start_time = time.perf_counter()

        filters = self._build_filter(tenant, custom_filter)
        chunks = await self.search(query=query, top_k=top_k, filter_dict=filters)
        context_str = self._format_context(chunks)
        history_msgs = self._format_history(history or [])

        # Execução da cadeia LCEL
        with tracer.start_as_current_span("rag.generate") as gen_span:
            safe_set_attribute(gen_span, "rag.context_chunks", len(chunks))
            safe_set_attribute(gen_span, "rag.context_chars", len(context_str))
            try:
                answer = await self.chain.ainvoke(
                    {
                        "context": context_str,
                        "question": query,
                        "history": history_msgs,
                    },
                    config={"callbacks": [LLMTelemetryCallback("rag.generate")]},
                )
            except Exception as exc:
                record_exception(gen_span, exc)
                raise
            safe_set_attribute(gen_span, "rag.answer_chars", len(answer))

        latency = (time.perf_counter() - start_time) * 1000.0

        return ChatResponse(
            answer=answer,
            sources=chunks,
            latency_ms=round(latency, 2),
        )

    async def stream_query(
        self,
        query: str,
        history: Optional[list[ChatMessage]] = None,
        tenant: Optional[str] = "teletech",
        custom_filter: Optional[dict[str, Any]] = None,
        top_k: int = 4,
    ) -> AsyncGenerator[str, None]:
        """Executa o pipeline RAG em modo streaming gerando tokens progressivos."""
        filters = self._build_filter(tenant, custom_filter)
        chunks = await self.search(query=query, top_k=top_k, filter_dict=filters)
        context_str = self._format_context(chunks)
        history_msgs = self._format_history(history or [])

        # Span manual (sem anexar ao contexto): context managers não são seguros através de `yield`
        gen_span = tracer.start_span("rag.generate_stream")
        safe_set_attribute(gen_span, "rag.context_chunks", len(chunks))
        safe_set_attribute(gen_span, "rag.context_chars", len(context_str))
        n_tokens = 0
        try:
            async for token in self.chain.astream(
                {
                    "context": context_str,
                    "question": query,
                    "history": history_msgs,
                },
                config={"callbacks": [LLMTelemetryCallback("rag.generate_stream", parent=gen_span)]},
            ):
                n_tokens += 1
                yield token
        except Exception as exc:
            record_exception(gen_span, exc)
            raise
        finally:
            safe_set_attribute(gen_span, "rag.stream_chunks", n_tokens)
            gen_span.end()



rag_service = RAGService()
