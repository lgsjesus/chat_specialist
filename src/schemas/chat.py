from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: str = Field(description="Papel do autor da mensagem ('user', 'assistant', 'system')")
    content: str = Field(description="Conteúdo da mensagem")


class QueryPlan(BaseModel):
    intent: str = Field(description="Intenção principal identificada do usuário (ex: cancelamento, contratação, suporte técnico)")
    clarified_query: str = Field(description="Pergunta reescrita e clarificada para busca vetorial na base de conhecimento")
    entities: list[str] = Field(default_factory=list, description="Entidades e produtos identificados (ex: Fibra 500 Mega, Fatura)")
    keywords: list[str] = Field(default_factory=list, description="Palavras-chave semânticas relevantes para recuperação")


class ChatRequest(BaseModel):
    question: str = Field(description="Pergunta do usuário")
    filters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Filtros customizados de metadados opcionais (ex: {'product': 'teletech_plans', 'plan': 'all'})",
    )
    history: Optional[list[ChatMessage]] = Field(
        default=None,
        description="Histórico recente da conversa para resolução de contexto e anáforas",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Suporte a alias 'query' -> 'question'
            if "query" in data and "question" not in data:
                data["question"] = data["query"]
            # Suporte a alias 'filter' -> 'filters'
            if "filter" in data and "filters" not in data:
                data["filters"] = data["filter"]
        return data


class SearchRequest(BaseModel):
    question: str = Field(description="Pergunta ou termo para busca por similaridade vetorial")
    filters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Filtros customizados de metadados opcionais",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "query" in data and "question" not in data:
                data["question"] = data["query"]
            if "filter" in data and "filters" not in data:
                data["filters"] = data["filter"]
        return data


class RetrievedChunk(BaseModel):
    content: str
    metadata: dict[str, Any]
    score: Optional[float] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[RetrievedChunk]
    latency_ms: float
    query_plan: Optional[QueryPlan] = None


class SearchResponse(BaseModel):
    question: str
    results: list[RetrievedChunk]
    total: int

