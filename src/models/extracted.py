"""ExtractedDocument — normalized output of all extraction strategies (Stage 2)."""
from pydantic import BaseModel, Field
from typing import Optional


class BBox(BaseModel):
    """Bounding box in page coordinates (e.g. points)."""
    x0: float = 0.0
    top: float = 0.0
    x1: float = 0.0
    bottom: float = 0.0

    @classmethod
    def from_rect(cls, x0: float, top: float, x1: float, bottom: float) -> "BBox":
        """Build from four coordinates (e.g. page.rect or union of chars)."""
        return cls(x0=float(x0), top=float(top), x1=float(x1), bottom=float(bottom))

    @classmethod
    def from_sequence(cls, seq) -> Optional["BBox"]:
        """Build from [x0, top, x1, bottom] or (x0, top, x1, bottom)."""
        if seq is None:
            return None
        try:
            s = list(seq)
            if len(s) < 4:
                return None
            return cls(x0=float(s[0]), top=float(s[1]), x1=float(s[2]), bottom=float(s[3]))
        except (TypeError, ValueError):
            return None


class TextBlock(BaseModel):
    """A text region with optional bounding box and page reference."""
    text: str = Field(..., description="Extracted text content")
    page: int = Field(1, ge=1, description="1-based page number")
    bbox: Optional[BBox] = Field(None, description="Bounding box on page")
    reading_order_index: int = Field(0, description="Order in reading flow")


class TableBlock(BaseModel):
    """Structured table: headers + rows."""
    headers: list[str] = Field(default_factory=list, description="Column headers")
    rows: list[list[str]] = Field(default_factory=list, description="Table rows (cell values)")
    page: int = Field(1, ge=1)
    bbox: Optional[BBox] = None
    reading_order_index: int = 0


class FigureBlock(BaseModel):
    """Figure with optional caption."""
    caption: Optional[str] = Field(None, description="Figure caption text")
    page: int = Field(1, ge=1)
    bbox: Optional[BBox] = None
    reading_order_index: int = 0


class ExtractedDocument(BaseModel):
    """Unified representation all three extraction strategies must produce."""

    document_id: str = Field(..., description="Source document identifier")
    text_blocks: list[TextBlock] = Field(default_factory=list, description="Text blocks with bbox and reading order")
    tables: list[TableBlock] = Field(default_factory=list, description="Structured tables (headers + rows)")
    figures: list[FigureBlock] = Field(default_factory=list, description="Figures with captions")
    num_pages: int = Field(0, ge=0)
    strategy_used: str = Field("", description="Strategy A / B / C that produced this output")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
