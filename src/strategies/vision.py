"""Strategy C: Vision-augmented extraction (VLM). Stub with cost estimate."""
from pathlib import Path

from src.models import ExtractedDocument, TextBlock
from src.strategies.base import BaseExtractor, ExtractionResult


class VisionExtractor(BaseExtractor):
    """VLM-based extraction for scanned/handwritten; budget-aware."""

    def __init__(self, cost_per_page_usd: float = 0.02):
        self.cost_per_page_usd = cost_per_page_usd

    @property
    def name(self) -> str:
        return "vision"

    def extract(self, pdf_path: Path, document_id: str) -> ExtractionResult:
        # Stub: in production would call OpenRouter (Gemini Flash / GPT-4o-mini) with page images
        num_pages = 0
        try:
            import fitz
            doc = fitz.open(pdf_path)
            num_pages = len(doc)
            doc.close()
        except Exception:
            pass
        if num_pages == 0:
            num_pages = 1
        cost = num_pages * self.cost_per_page_usd
        extracted = ExtractedDocument(
            document_id=document_id,
            text_blocks=[TextBlock(text="[VLM extraction stub: implement OpenRouter call]", page=1, reading_order_index=0)],
            tables=[],
            figures=[],
            num_pages=num_pages,
            strategy_used=self.name,
            confidence_score=0.8,
        )
        return ExtractionResult(
            extracted=extracted,
            confidence_score=0.8,
            cost_estimate_usd=round(cost, 4),
            strategy_name=self.name,
        )
