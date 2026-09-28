from pathlib import Path
from fastapi import APIRouter, HTTPException, status

from src.schemas.ingestion import DocumentIngestRequest, IngestSummaryResponse
from src.services.ingestion import DocumentIngestor

router = APIRouter(prefix="/ingest", tags=["Ingestion"])
ingestor = DocumentIngestor()

KNOWLEDGE_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge_docs"


@router.post("/knowledge-docs", response_model=IngestSummaryResponse, status_code=status.HTTP_200_OK)
async def ingest_knowledge_docs():
    """Lê automaticamente todos os documentos da pasta knowledge_docs/ e executa a ingestão vetorial no PostgreSQL."""
    try:
        if not KNOWLEDGE_DOCS_DIR.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Diretório de documentos não encontrado em: {KNOWLEDGE_DOCS_DIR}",
            )

        summary = await ingestor.ingest_directory(KNOWLEDGE_DOCS_DIR)
        return IngestSummaryResponse(
            status="success",
            message=f"Ingestão concluída com sucesso. {summary['total_files']} arquivos processados.",
            total_files=summary["total_files"],
            total_chunks=summary["total_chunks"],
            details=summary["details"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro durante a ingestão do diretório: {str(exc)}",
        )


@router.post("/document", status_code=status.HTTP_201_CREATED)
async def ingest_single_document(request: DocumentIngestRequest):
    """Ingere um documento individual em formato Markdown com seus respectivos metadados."""
    try:
        chunks_count = await ingestor.ingest_document(
            content=request.content, metadata=request.metadata
        )
        return {
            "status": "success",
            "message": "Documento indexado com sucesso.",
            "chunks_created": chunks_count,
        }
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Erro de validação de metadados: {str(ve)}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao ingerir documento: {str(exc)}",
        )
