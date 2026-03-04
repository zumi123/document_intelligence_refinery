"""DocumentProfile — output of the Triage Agent (Stage 1)."""
from enum import Enum
from pydantic import BaseModel, Field


class OriginType(str, Enum):
    NATIVE_DIGITAL = "native_digital"
    SCANNED_IMAGE = "scanned_image"
    MIXED = "mixed"
    FORM_FILLABLE = "form_fillable"


class LayoutComplexity(str, Enum):
    SINGLE_COLUMN = "single_column"
    MULTI_COLUMN = "multi_column"
    TABLE_HEAVY = "table_heavy"
    FIGURE_HEAVY = "figure_heavy"
    MIXED = "mixed"


class DomainHint(str, Enum):
    FINANCIAL = "financial"
    LEGAL = "legal"
    TECHNICAL = "technical"
    MEDICAL = "medical"
    GENERAL = "general"


class EstimatedExtractionCost(str, Enum):
    FAST_TEXT_SUFFICIENT = "fast_text_sufficient"
    NEEDS_LAYOUT_MODEL = "needs_layout_model"
    NEEDS_VISION_MODEL = "needs_vision_model"


class DocumentProfile(BaseModel):
    """Classification produced by the Triage Agent; governs extraction strategy selection."""

    document_id: str = Field(..., description="Unique document identifier (e.g. filename hash or path)")
    origin_type: OriginType = Field(..., description="Digital vs scanned vs mixed")
    layout_complexity: LayoutComplexity = Field(..., description="Single/multi-column, table/figure heavy")
    language_code: str = Field(default="en", description="Detected language code (e.g. ISO 639-1)")
    language_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Language detection confidence")
    domain_hint: DomainHint = Field(default=DomainHint.GENERAL, description="Domain for extraction prompt strategy")
    estimated_extraction_cost: EstimatedExtractionCost = Field(
        ..., description="Derived from strategy: A / B / C"
    )
    num_pages: int = Field(default=0, ge=0, description="Number of pages in document")
    chars_per_page_avg: float = Field(default=0.0, ge=0.0, description="Average characters per page (from triage)")
    image_area_ratio_avg: float = Field(default=0.0, ge=0.0, le=1.0, description="Average fraction of page covered by images")
