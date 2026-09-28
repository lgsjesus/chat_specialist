from typing import Any, Optional
from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    content: str = Field(description="Raw Markdown document content")
    metadata: dict[str, Any] = Field(description="Metadata required: title, tenant, product, plan, doc_type, version, status, visibility")


class IngestSummaryResponse(BaseModel):
    status: str
    message: str
    total_files: int
    total_chunks: int
    details: Optional[list[dict[str, Any]]] = None
