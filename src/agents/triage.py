"""
Triage Agent (Stage 1): Classifies documents for extraction strategy selection.
Produces DocumentProfile with origin_type, layout_complexity, domain_hint, estimated_extraction_cost.
"""
import hashlib
from pathlib import Path
from typing import Optional

from src.models import (
    DocumentProfile,
    OriginType,
    LayoutComplexity,
    EstimatedExtractionCost,
)


def _load_rules(rules_path: Optional[Path] = None) -> dict:
    import yaml
    path = rules_path or Path(__file__).resolve().parent.parent.parent / "rubric" / "extraction_rules.yaml"
    if not path.exists():
        return {"thresholds": {"min_chars_per_page": 100, "max_image_area_ratio": 0.5}}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _analyze_pdf(path: Path) -> dict:
    """Extract per-page stats using pdfplumber or PyMuPDF."""
    try:
        import pdfplumber
        total_chars = 0
        total_area = 0.0
        total_image_area = 0.0
        n_pages = 0
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                n_pages += 1
                w, h = page.width, page.height
                area = w * h
                total_area += area
                text = page.extract_text() or ""
                total_chars += len(text.replace(" ", "").replace("\n", ""))
                img_area = 0.0
                for img in page.images:
                    x0 = img.get("x0", 0) or 0
                    top = img.get("top", 0) or 0
                    x1 = img.get("x1", 0) or 0
                    bottom = img.get("bottom", 0) or 0
                    img_area += (x1 - x0) * (bottom - top)
                total_image_area += img_area
        return {
            "num_pages": n_pages,
            "total_chars": total_chars,
            "chars_per_page_avg": total_chars / n_pages if n_pages else 0,
            "image_area_ratio": total_image_area / total_area if total_area else 0,
        }
    except ImportError:
        try:
            import fitz
            doc = fitz.open(path)
            total_chars = 0
            total_area = 0.0
            total_image_area = 0.0
            n_pages = len(doc)
            for i in range(n_pages):
                page = doc[i]
                rect = page.rect
                area = rect.width * rect.height
                total_area += area
                total_chars += len((page.get_text() or "").replace(" ", "").replace("\n", ""))
                for img in page.get_image_info():
                    bbox = img.get("bbox")
                    if bbox:
                        total_image_area += (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            doc.close()
            return {
                "num_pages": n_pages,
                "total_chars": total_chars,
                "chars_per_page_avg": total_chars / n_pages if n_pages else 0,
                "image_area_ratio": total_image_area / total_area if total_area else 0,
            }
        except Exception:
            return {"num_pages": 0, "total_chars": 0, "chars_per_page_avg": 0, "image_area_ratio": 0}


def _domain_hint_from_text(text_sample: str, rules: dict) -> str:
    """Keyword-based domain classifier. Any key in domain_keywords is valid (config-only onboarding)."""
    keywords = rules.get("domain_keywords") or {}
    text_lower = (text_sample or "").lower()[:5000]
    best_key = "general"
    best_score = 0
    for domain, words in keywords.items():
        if not isinstance(words, list):
            continue
        score = sum(1 for w in words if w and w.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_key = domain
    return best_key


def triage_document(
    pdf_path: Path,
    document_id: Optional[str] = None,
    rules_path: Optional[Path] = None,
) -> DocumentProfile:
    """
    Classify a document and return a DocumentProfile.
    Uses character density and image ratio for origin_type; heuristics for layout_complexity.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    rules = _load_rules(rules_path)
    th = rules.get("thresholds") or {}
    min_chars = th.get("min_chars_per_page", 100)
    max_img = th.get("max_image_area_ratio", 0.5)

    stats = _analyze_pdf(path)
    num_pages = stats["num_pages"]
    chars_avg = stats["chars_per_page_avg"]
    img_ratio = stats["image_area_ratio"]

    # Origin type
    if num_pages == 0:
        origin_type = OriginType.MIXED
    elif chars_avg < min_chars and img_ratio > max_img:
        origin_type = OriginType.SCANNED_IMAGE
    elif chars_avg >= min_chars and img_ratio <= max_img:
        origin_type = OriginType.NATIVE_DIGITAL
    else:
        origin_type = OriginType.MIXED

    # Layout complexity: from config only (no magic numbers)
    layout_conf = rules.get("layout_heuristics") or {}
    fig_ratio_min = layout_conf.get("figure_heavy_image_ratio_min", 0.3)
    table_chars_min = layout_conf.get("table_heavy_chars_per_page_min", 1000)
    table_pages_min = layout_conf.get("table_heavy_num_pages_min", 20)

    if origin_type == OriginType.SCANNED_IMAGE:
        layout_complexity = LayoutComplexity.MIXED
    elif img_ratio > fig_ratio_min:
        layout_complexity = LayoutComplexity.FIGURE_HEAVY
    elif chars_avg >= table_chars_min and num_pages >= table_pages_min:
        layout_complexity = LayoutComplexity.TABLE_HEAVY
    elif chars_avg >= min_chars:
        layout_complexity = LayoutComplexity.SINGLE_COLUMN
    else:
        layout_complexity = LayoutComplexity.MIXED

    # Domain hint: sample first pages
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            sample = " ".join(
                (p.extract_text() or "") for p in list(pdf.pages)[:5]
            )
    except Exception:
        try:
            import fitz
            doc = fitz.open(path)
            sample = " ".join(doc[i].get_text() or "" for i in range(min(5, len(doc))))
            doc.close()
        except Exception:
            sample = ""
    domain_hint = _domain_hint_from_text(sample, rules)

    # Estimated extraction cost (strategy tier)
    if origin_type == OriginType.SCANNED_IMAGE:
        estimated_cost = EstimatedExtractionCost.NEEDS_VISION_MODEL
    elif layout_complexity in (
        LayoutComplexity.MULTI_COLUMN,
        LayoutComplexity.TABLE_HEAVY,
        LayoutComplexity.FIGURE_HEAVY,
        LayoutComplexity.MIXED,
    ):
        estimated_cost = EstimatedExtractionCost.NEEDS_LAYOUT_MODEL
    else:
        estimated_cost = EstimatedExtractionCost.FAST_TEXT_SUFFICIENT

    doc_id = document_id or hashlib.sha256(path.read_bytes()[:8192]).hexdigest()[:16]

    return DocumentProfile(
        document_id=doc_id,
        origin_type=origin_type,
        layout_complexity=layout_complexity,
        language_code="en",
        language_confidence=0.9,
        domain_hint=domain_hint,
        estimated_extraction_cost=estimated_cost,
        num_pages=num_pages,
        chars_per_page_avg=round(chars_avg, 1),
        image_area_ratio_avg=round(img_ratio, 4),
    )
