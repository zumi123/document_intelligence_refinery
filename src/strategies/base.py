"""Shared interface for extraction strategies."""
from abc import ABC, abstractmethod
from pathlib import Path
from pydantic import BaseModel, Field

from src.models import ExtractedDocument


class ExtractionResult(BaseModel):
    """Result of one extraction run: document + confidence + cost estimate."""
    extracted: ExtractedDocument = Field(...)
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    cost_estimate_usd: float = Field(0.0, ge=0.0)
    strategy_name: str = Field("")


class BaseExtractor(ABC):
    """Abstract base for Strategy A (Fast Text), B (Layout), C (Vision)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy identifier: 'fast_text', 'layout', or 'vision'."""
        ...

    @abstractmethod
    def extract(self, pdf_path: Path, document_id: str) -> ExtractionResult:
        """Run extraction; return ExtractedDocument plus confidence and cost estimate."""
        ...
