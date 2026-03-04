"""Strategy C: Vision-augmented extraction (VLM) with hard budget cap and early stopping."""
from pathlib import Path
from typing import Optional

from src.models import ExtractedDocument, TextBlock, TableBlock, FigureBlock
from src.models.extracted import BBox
from src.strategies.base import BaseExtractor, ExtractionResult


def _load_vision_config() -> dict:
    import yaml
    path = Path(__file__).resolve().parent.parent.parent / "rubric" / "extraction_rules.yaml"
    if not path.exists():
        return {"max_usd_per_document": 2.0, "max_pages_per_document": 100, "cost_per_page_usd": 0.02}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("vision", {})


class VisionExtractor(BaseExtractor):
    """
    VLM-based extraction for scanned/handwritten documents.
    Enforces a hard budget cap with early stopping; handles per-page/API failures.
    """

    def __init__(
        self,
        cost_per_page_usd: Optional[float] = None,
        max_usd_per_document: Optional[float] = None,
        max_pages_per_document: Optional[int] = None,
    ):
        cfg = _load_vision_config()
        self.cost_per_page_usd = cost_per_page_usd if cost_per_page_usd is not None else cfg.get("cost_per_page_usd", 0.02)
        self.max_usd_per_document = max_usd_per_document if max_usd_per_document is not None else cfg.get("max_usd_per_document", 2.0)
        self.max_pages_per_document = max_pages_per_document if max_pages_per_document is not None else cfg.get("max_pages_per_document", 0) or 0
        self._page_failures: list[int] = []
        self._budget_exceeded: bool = False

    @property
    def name(self) -> str:
        return "vision"

    def extract(self, pdf_path: Path, document_id: str) -> ExtractionResult:
        pdf_path = Path(pdf_path)
        text_blocks: list[TextBlock] = []
        tables: list[TableBlock] = []
        figures: list[FigureBlock] = []
        spent_usd = 0.0
        self._page_failures = []
        self._budget_exceeded = False
        num_pages = 0

        try:
            import fitz
            doc = fitz.open(pdf_path)
            num_pages = len(doc)
        except Exception:
            doc = None

        if num_pages == 0 or doc is None:
            if doc is not None:
                doc.close()
            return self._make_result(
                document_id, text_blocks, tables, figures, 0, spent_usd, confidence=0.0, error="could not open PDF"
            )

        try:
            # Apply page cap from config (early stopping limit)
            pages_to_process = num_pages
            if self.max_pages_per_document > 0:
                pages_to_process = min(num_pages, self.max_pages_per_document)

            for page_idx in range(pages_to_process):
                page_num = page_idx + 1
                cost_this_page = self.cost_per_page_usd
                if spent_usd + cost_this_page > self.max_usd_per_document:
                    self._budget_exceeded = True
                    break
                try:
                    page = doc[page_idx]
                    rect = page.rect
                    page_bbox = BBox.from_rect(rect.x0, rect.y0, rect.x1, rect.y1)
                    block = TextBlock(
                        text="[VLM extraction stub: implement OpenRouter call]",
                        page=page_num,
                        bbox=page_bbox,
                        reading_order_index=page_idx,
                    )
                    text_blocks.append(block)
                    spent_usd += cost_this_page
                except Exception:
                    self._page_failures.append(page_num)
        finally:
            doc.close()

        num_processed = len(text_blocks)
        confidence = 0.8 if num_processed > 0 else 0.0
        if self._page_failures:
            confidence = max(0.0, confidence - 0.1 * len(self._page_failures))
        if self._budget_exceeded:
            confidence = min(confidence, 0.7)

        return self._make_result(
            document_id,
            text_blocks,
            tables,
            figures,
            num_pages,
            spent_usd,
            confidence=confidence,
        )

    def _make_result(
        self,
        document_id: str,
        text_blocks: list,
        tables: list,
        figures: list,
        num_pages: int,
        cost_estimate_usd: float,
        confidence: float = 0.8,
        error: Optional[str] = None,
    ) -> ExtractionResult:
        if not text_blocks and not error:
            text_blocks = [TextBlock(text="[No content extracted]", page=1, reading_order_index=0)]
        extracted = ExtractedDocument(
            document_id=document_id,
            text_blocks=text_blocks,
            tables=tables,
            figures=figures,
            num_pages=num_pages or 1,
            strategy_used=self.name,
            confidence_score=confidence,
        )
        return ExtractionResult(
            extracted=extracted,
            confidence_score=confidence,
            cost_estimate_usd=round(cost_estimate_usd, 4),
            strategy_name=self.name,
        )
