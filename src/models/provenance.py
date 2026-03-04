"""ProvenanceChain — citations for query answers (Stage 5)."""
from pydantic import BaseModel, Field
from typing import Optional


class BBox(BaseModel):
    x0: float = 0.0
    top: float = 0.0
    x1: float = 0.0
    bottom: float = 0.0


class ProvenanceCitation(BaseModel):
    """One source citation."""
    document_name: str = Field("")
    page_number: int = Field(1, ge=1)
    bbox: Optional[BBox] = None
    content_hash: str = Field("", description="For verification")
    content_snippet: Optional[str] = Field(None, description="Short excerpt from source")


class ProvenanceChain(BaseModel):
    """List of source citations attached to every query answer."""
    citations: list[ProvenanceCitation] = Field(default_factory=list)
