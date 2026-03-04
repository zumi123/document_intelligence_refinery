"""Strategy A: Fast Text extraction using pdfplumber or PyMuPDF."""
from pathlib import Path

from src.models import ExtractedDocument, TextBlock
from src.models.extracted import BBox
from src.strategies.base import BaseExtractor, ExtractionResult


def _load_thresholds():
    import yaml
    from pathlib import Path as P
    path = P(__file__).resolve().parent.parent.parent / "rubric" / "extraction_rules.yaml"
    if not path.exists():
        return {"min_chars_per_page": 100, "max_image_area_ratio": 0.5}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("thresholds", {})


class FastTextExtractor(BaseExtractor):
    """Low-cost text extraction; confidence-gated for escalation."""

    @property
    def name(self) -> str:
        return "fast_text"

    def extract(self, pdf_path: Path, document_id: str) -> ExtractionResult:
        th = _load_thresholds()
        min_chars = th.get("min_chars_per_page", 100)
        max_img = th.get("max_image_area_ratio", 0.5)
        text_blocks: list[TextBlock] = []
        total_chars = 0
        total_area = 0.0
        total_image_area = 0.0
        num_pages = 0
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                num_pages = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    area = page.width * page.height
                    total_area += area
                    text = page.extract_text() or ""
                    total_chars += len(text.replace(" ", "").replace("\n", ""))
                    img_area = sum(
                        (img.get("x1", 0) or 0 - img.get("x0", 0) or 0)
                        * (img.get("bottom", 0) or 0 - img.get("top", 0) or 0)
                        for img in page.images
                    )
                    total_image_area += img_area
                    text_blocks.append(
                        TextBlock(
                            text=text,
                            page=i + 1,
                            bbox=None,
                            reading_order_index=i,
                        )
                    )
        except ImportError:
            try:
                import fitz
                doc = fitz.open(pdf_path)
                num_pages = len(doc)
                for i in range(num_pages):
                    page = doc[i]
                    rect = page.rect
                    area = rect.width * rect.height
                    total_area += area
                    text = page.get_text()
                    total_chars += len(text.replace(" ", "").replace("\n", ""))
                    for img in page.get_image_info():
                        b = img.get("bbox")
                        if b:
                            total_image_area += (b[2] - b[0]) * (b[3] - b[1])
                    text_blocks.append(
                        TextBlock(text=text, page=i + 1, bbox=None, reading_order_index=i)
                    )
                doc.close()
            except Exception:
                pass
        chars_per_page = total_chars / num_pages if num_pages else 0
        img_ratio = total_image_area / total_area if total_area else 0
        # Confidence: high when chars sufficient and image ratio low
        confidence = 0.0
        if num_pages > 0:
            if chars_per_page >= min_chars and img_ratio <= max_img:
                confidence = 0.9
            elif chars_per_page >= min_chars * 0.5:
                confidence = 0.5
            else:
                confidence = 0.2
        extracted = ExtractedDocument(
            document_id=document_id,
            text_blocks=text_blocks,
            tables=[],
            figures=[],
            num_pages=num_pages,
            strategy_used=self.name,
            confidence_score=confidence,
        )
        return ExtractionResult(
            extracted=extracted,
            confidence_score=confidence,
            cost_estimate_usd=0.0,
            strategy_name=self.name,
        )
