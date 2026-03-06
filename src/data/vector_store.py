"""ChromaDB vector store for LDU ingestion and semantic search."""
from pathlib import Path
from typing import Optional

from src.models import LDU


class VectorStore:
    """Ingest LDUs and run semantic search. Uses ChromaDB."""

    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = persist_dir or Path(".refinery/chromadb")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collection = None

    def _ensure_client(self):
        if self._client is None:
            import chromadb
            from chromadb.config import Settings
            self._client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                "ldus",
                metadata={"description": "Document Intelligence LDUs"},
            )

    def ingest(self, ldus: list[LDU], document_id: str = "") -> int:
        """Add LDUs to the vector store. Returns count ingested."""
        self._ensure_client()
        if not ldus:
            return 0
        ids = []
        documents = []
        metadatas = []
        for i, ldu in enumerate(ldus):
            doc_id = ldu.document_id or document_id
            ids.append(f"{doc_id}_{i}_{ldu.reading_order_index}")
            documents.append(ldu.content or "")
            metadatas.append({
                "document_id": doc_id,
                "page": ldu.page_refs[0] if ldu.page_refs else 0,
                "chunk_type": ldu.chunk_type.value if hasattr(ldu.chunk_type, "value") else str(ldu.chunk_type),
            })
        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)
        return len(ids)

    def search(
        self,
        query: str,
        document_id: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Return list of {ldu, score} dicts. Reconstructs LDU from stored metadata."""
        self._ensure_client()
        where = {"document_id": document_id} if document_id else None
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out = []
        if not results or not results["ids"] or not results["ids"][0]:
            return out
        for i, doc_id in enumerate(results["ids"][0]):
            doc = results["documents"][0][i] if results["documents"] else ""
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            dist = results["distances"][0][i] if results.get("distances") else 0
            score = 1.0 / (1.0 + dist) if dist else 1.0
            from src.models import ChunkType
            ldu = LDU(
                content=doc,
                chunk_type=ChunkType(meta.get("chunk_type", "paragraph")),
                page_refs=[meta.get("page", 1)],
                document_id=meta.get("document_id", ""),
                content_hash="",
            )
            out.append({"ldu": ldu, "score": score})
        return out
