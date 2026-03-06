"""LDU — Logical Document Unit (Stage 3 chunking output)."""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class ChunkType(str, Enum):
    PARAGRAPH = "paragraph"
    TABLE = "table"
    FIGURE = "figure"
    LIST = "list"
    SECTION_HEADER = "section_header"
    OTHER = "other"


class BBox(BaseModel):
    x0: float = 0.0
    top: float = 0.0
    x1: float = 0.0
    bottom: float = 0.0


class LDU(BaseModel):
    """RAG-ready chunk with provenance and structural context."""

    content: str = Field(..., description="Chunk text content")
    chunk_type: ChunkType = Field(ChunkType.PARAGRAPH)
    page_refs: list[int] = Field(default_factory=list, description="1-based page numbers this chunk spans")
    bounding_box: Optional[BBox] = Field(None)
    parent_section: Optional[str] = Field(None, description="Section title this chunk belongs to")
    token_count: int = Field(0, ge=0)
    content_hash: str = Field("", description="Hash for provenance verification (e.g. spatial/content hash)")
    document_id: str = Field("", description="Source document id")
    reading_order_index: int = Field(0)
    cross_refs: list[str] = Field(default_factory=list, description="Resolved cross-references (e.g. 'Table 3', 'Section 4.2')")
