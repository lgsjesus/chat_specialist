import uuid
from pathlib import Path
from typing import Any, Optional
import frontmatter
from langchain_core.documents import Document
from langchain_postgres import PGVector
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from src.infra.ai_factory import get_collection_name, get_embeddings
from src.infra.config import settings
from src.infra.database import database

REQUIRED_METADATA = [
    "title",
    "tenant",
    "product",
    "plan",
    "doc_type",
    "version",
    "status",
    "visibility",
]

# Mapa de aliases: chaves usadas nos frontmatters dos documentos → chaves internas.
# Permite que os documentos usem nomes alternativos sem quebrar a validação.
METADATA_ALIASES: dict[str, str] = {
    "document_type": "doc_type",  # frontmatter usa document_type
    "audience": "visibility",  # frontmatter usa audience
}

CONTEXT_HEADER_FIELDS = [
    ("Document title", "title"),
    ("Document type", "doc_type"),
    ("Product", "product"),
    ("Plan", "plan"),
    ("Version", "version"),
    ("Section", "section"),
]

HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


class DocumentIngestor:
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

    def normalize_metadata(self, metadata: dict) -> dict:
        """Aplica aliases de metadados para harmonizar nomes de campos dos documentos
        com os nomes internos esperados pelo sistema (ver METADATA_ALIASES)."""
        normalized = dict(metadata)
        for alias, canonical in METADATA_ALIASES.items():
            if alias in normalized and canonical not in normalized:
                normalized[canonical] = normalized.pop(alias)
        return normalized

    def validate_metadata(self, metadata: dict):
        missing = [m for m in REQUIRED_METADATA if m not in metadata]
        if missing:
            raise ValueError(f"Missing required metadata fields: {missing}")

    def add_context_headers(
        self, chunk_text: str, document_metadata: dict, chunk_metadata: dict
    ) -> str:
        header_lines = []
        for label, key in CONTEXT_HEADER_FIELDS:
            # Map section headers appropriately. h1 -> section, h2 -> subsection, etc.
            if key == "section":
                val = (
                    chunk_metadata.get("h1")
                    or chunk_metadata.get("h2")
                    or chunk_metadata.get("h3")
                )
            else:
                val = chunk_metadata.get(key, document_metadata.get(key))
            if val:
                header_lines.append(f"{label}: {val}")

        if header_lines:
            header_prefix = "\n".join(header_lines) + "\n\n"
            return header_prefix + chunk_text
        return chunk_text

    async def ingest_document(self, content: str, metadata: dict[str, Any]):
        metadata = self.normalize_metadata(metadata)
        self.validate_metadata(metadata)

        # 1. Split down to headers
        md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False
        )
        md_chunks = md_splitter.split_text(content)

        # 2. Divide iteratively
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, chunk_overlap=150, separators=["\n\n", "\n", " ", ""]
        )

        final_documents = []

        for md_chunk in md_chunks:
            # Further split chunk if it exceeds size
            sub_chunks = text_splitter.split_text(md_chunk.page_content)

            for sub_chunk_text in sub_chunks:
                chunk_id = str(uuid.uuid4())

                # Metadata combining source MD data + chunk-specific headers
                combined_metadata = {**metadata, **md_chunk.metadata}
                combined_metadata["chunk_id"] = chunk_id

                # Append context header fields to content to be embedded
                enhanced_text = self.add_context_headers(
                    chunk_text=sub_chunk_text,
                    document_metadata=metadata,
                    chunk_metadata=md_chunk.metadata,
                )

                doc = Document(page_content=enhanced_text, metadata=combined_metadata)
                final_documents.append(doc)

        # Asynchronously add the processed and enriched documents to Postgres pgvector
        await self.vector_store.aadd_documents(final_documents)
        print(f"Ingested {len(final_documents)} chunks.")
        return len(final_documents)

    async def ingest_directory(self, directory_path: Path | str) -> dict[str, Any]:
        """Lê todos os arquivos Markdown com frontmatter de um diretório e os indexa."""
        path = Path(directory_path)
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Diretório não encontrado: {directory_path}")

        files = sorted(list(path.glob("*.md")))
        results = []
        total_chunks = 0

        for file_path in files:
            post = frontmatter.load(file_path)
            content = post.content
            metadata = post.metadata
            chunks_count = await self.ingest_document(content=content, metadata=metadata)
            total_chunks += chunks_count
            results.append({
                "file": file_path.name,
                "title": metadata.get("title", file_path.stem),
                "chunks": chunks_count,
            })

        return {
            "total_files": len(files),
            "total_chunks": total_chunks,
            "details": results,
        }

