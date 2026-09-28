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
        results = await self.vector_store.asimilarity_search_with_score(
            query=query,
            k=top_k,
            filter=filter_dict,
        )
        chunks: list[RetrievedChunk] = []
        for doc, score in results:
            chunks.append(
                RetrievedChunk(
                    content=doc.page_content,
                    metadata=doc.metadata,
                    score=round(float(score), 4),
                )
            )
        return chunks

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
        answer = await self.chain.ainvoke({
            "context": context_str,
            "question": query,
            "history": history_msgs,
        })

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

        async for token in self.chain.astream({
            "context": context_str,
            "question": query,
            "history": history_msgs,
        }):
            yield token


rag_service = RAGService()
