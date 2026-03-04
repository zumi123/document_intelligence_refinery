"""
ExtractionRouter: Selects extraction strategy from DocumentProfile with confidence-gated escalation.
Logs to extraction_ledger.jsonl.
"""
import json
from pathlib import Path
from typing import Optional

from src.models import DocumentProfile, ExtractedDocument, OriginType, LayoutComplexity, EstimatedExtractionCost
from src.strategies import FastTextExtractor, LayoutExtractor, VisionExtractor, ExtractionResult


def _load_thresholds() -> dict:
    import yaml
    path = Path(__file__).resolve().parent.parent.parent / "rubric" / "extraction_rules.yaml"
    if not path.exists():
        return {"fast_text_min_confidence": 0.7, "layout_min_confidence": 0.7}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("thresholds", {})


class ExtractionRouter:
    """Routes to Strategy A/B/C based on profile; escalates on low confidence."""

    def __init__(
        self,
        ledger_path: Optional[Path] = None,
        fast_text: Optional[FastTextExtractor] = None,
        layout: Optional[LayoutExtractor] = None,
        vision: Optional[VisionExtractor] = None,
    ):
        self.ledger_path = ledger_path or Path(__file__).resolve().parent.parent.parent / ".refinery" / "extraction_ledger.jsonl"
        self.fast_text = fast_text or FastTextExtractor()
        self.layout = layout or LayoutExtractor()
        self.vision = vision or VisionExtractor()
        self.th = _load_thresholds()
        self.min_fast = self.th.get("fast_text_min_confidence", 0.7)
        self.min_layout = self.th.get("layout_min_confidence", 0.7)

    def _choose_initial_strategy(self, profile: DocumentProfile) -> str:
        """Return 'fast_text', 'layout', or 'vision' from profile."""
        if profile.origin_type == OriginType.SCANNED_IMAGE:
            return "vision"
        if profile.origin_type in (OriginType.MIXED, OriginType.FORM_FILLABLE):
            return "layout"
        if profile.estimated_extraction_cost == EstimatedExtractionCost.NEEDS_VISION_MODEL:
            return "vision"
        if profile.estimated_extraction_cost == EstimatedExtractionCost.NEEDS_LAYOUT_MODEL:
            return "layout"
        if profile.layout_complexity in (
            LayoutComplexity.MULTI_COLUMN,
            LayoutComplexity.TABLE_HEAVY,
            LayoutComplexity.FIGURE_HEAVY,
            LayoutComplexity.MIXED,
        ):
            return "layout"
        return "fast_text"

    def _log_ledger(self, entry: dict) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def extract(self, pdf_path: Path, profile: DocumentProfile) -> ExtractionResult:
        """
        Run extraction with escalation: try initial strategy; if confidence below threshold,
        escalate to layout then vision.
        """
        pdf_path = Path(pdf_path)
        doc_id = profile.document_id
        initial = self._choose_initial_strategy(profile)
        result: Optional[ExtractionResult] = None
        strategy_used = initial
        escalated = False

        if initial == "fast_text":
            result = self.fast_text.extract(pdf_path, doc_id)
            if result.confidence_score < self.min_fast:
                escalated = True
                strategy_used = "layout"
                result = self.layout.extract(pdf_path, doc_id)
                if result.confidence_score < self.min_layout:
                    escalated = True
                    strategy_used = "vision"
                    result = self.vision.extract(pdf_path, doc_id)
        elif initial == "layout":
            result = self.layout.extract(pdf_path, doc_id)
            if result.confidence_score < self.min_layout:
                escalated = True
                strategy_used = "vision"
                result = self.vision.extract(pdf_path, doc_id)
        else:
            result = self.vision.extract(pdf_path, doc_id)

        if result is None:
            result = self.vision.extract(pdf_path, doc_id)
            strategy_used = "vision"

        result.extracted.strategy_used = strategy_used
        result.extracted.confidence_score = result.confidence_score
        result.strategy_name = strategy_used

        self._log_ledger({
            "document_id": doc_id,
            "pdf_path": str(pdf_path),
            "strategy_used": strategy_used,
            "confidence_score": result.confidence_score,
            "cost_estimate_usd": result.cost_estimate_usd,
            "escalated": escalated,
            "num_pages": result.extracted.num_pages,
        })
        return result
