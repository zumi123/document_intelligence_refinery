"""Strategy B: Layout-aware extraction using Docling. Preserves table headers and figure captions."""
from pathlib import Path
from typing import Optional

from src.models import ExtractedDocument, TextBlock, TableBlock, FigureBlock
from src.models.extracted import BBox
from src.strategies.base import BaseExtractor, ExtractionResult


def _safe_headers_rows(obj):
    """Normalize table-like object to headers + rows; preserve headers rigorously."""
    headers = []
    rows = []
    if hasattr(obj, "headers") and obj.headers is not None:
        headers = list(obj.headers) if not isinstance(obj.headers, list) else obj.headers
    if hasattr(obj, "rows") and obj.rows is not None:
        raw = obj.rows if isinstance(obj.rows, list) else list(obj.rows)
        for r in raw:
            if isinstance(r, (list, tuple)):
                rows.append([str(c) for c in r])
            else:
                rows.append([str(r)])
    if hasattr(obj, "data") and not rows and not headers:
        data = obj.data
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, (list, tuple)):
                headers = [str(c) for c in first]
                for r in data[1:]:
                    rows.append([str(c) for c in r] if isinstance(r, (list, tuple)) else [str(r)])
    return headers, rows


def _safe_caption(obj) -> Optional[str]:
    """Extract figure caption; preserve for figure chunk metadata."""
    if hasattr(obj, "caption") and obj.caption:
        return str(obj.caption).strip()
    if hasattr(obj, "title") and obj.title:
        return str(obj.title).strip()
    return None


def _safe_bbox(obj) -> Optional[BBox]:
    """Extract bounding box from Docling element for spatial provenance."""
    if obj is None:
        return None
    if hasattr(obj, "bbox") and obj.bbox is not None:
        b = obj.bbox
        if hasattr(b, "__iter__") and len(list(b)) >= 4:
            return BBox.from_sequence(list(b))
        if hasattr(b, "l") and hasattr(b, "t"):
            return BBox(x0=getattr(b, "l", 0), top=getattr(b, "t", 0), x1=getattr(b, "r", 0), bottom=getattr(b, "b", 0))
    if hasattr(obj, "bounds") and obj.bounds:
        b = obj.bounds
        if hasattr(b, "__iter__"):
            return BBox.from_sequence(list(b))
    if hasattr(obj, "prov") and getattr(obj, "prov", None):
        p = obj.prov
        if hasattr(p, "bbox"):
            return _safe_bbox(p.bbox)
    return None


class LayoutExtractor(BaseExtractor):
    """
    Docling-based extraction. Table headers and figure captions are rigorously
    preserved in the normalized schema. Per-document and per-table/per-figure
    errors are caught so partial results can be returned.
    """

    @property
    def name(self) -> str:
        return "layout"

    def extract(self, pdf_path: Path, document_id: str) -> ExtractionResult:
        text_blocks: list[TextBlock] = []
        tables: list[TableBlock] = []
        figures: list[FigureBlock] = []
        num_pages = 0
        errors: list[str] = []
        confidence = 0.0

        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(str(pdf_path))
            doc = result.document
        except ImportError as e:
            errors.append(f"docling not installed: {e}")
            return self._result(document_id, text_blocks, tables, figures, 0, 0.0, errors)
        except Exception as e:
            errors.append(f"conversion failed: {e}")
            return self._result(document_id, text_blocks, tables, figures, 0, 0.3, errors)

        try:
            md = doc.export_to_markdown()
            num_pages = len(doc.pages) if hasattr(doc, "pages") and doc.pages else 0
            text_bbox = None
            if num_pages and hasattr(doc, "pages") and doc.pages:
                text_bbox = _safe_bbox(doc.pages[0])
            text_blocks.append(
                TextBlock(text=md[:50000], page=1, bbox=text_bbox, reading_order_index=0)
            )
        except Exception as e:
            errors.append(f"markdown export: {e}")

        if hasattr(doc, "tables") and doc.tables:
            for i, t in enumerate(doc.tables):
                try:
                    headers, rows = _safe_headers_rows(t)
                    tables.append(
                        TableBlock(
                            headers=headers,
                            rows=rows,
                            page=getattr(t, "page", 1) or 1,
                            bbox=_safe_bbox(t),
                            reading_order_index=len(tables),
                        )
                    )
                except Exception as e:
                    errors.append(f"table {i}: {e}")

        if getattr(doc, "figures", None):
            for i, fig in enumerate(doc.figures):
                try:
                    caption = _safe_caption(fig)
                    figures.append(
                        FigureBlock(
                            caption=caption,
                            page=getattr(fig, "page", 1) or 1,
                            bbox=_safe_bbox(fig),
                            reading_order_index=len(figures),
                        )
                    )
                except Exception as e:
                    errors.append(f"figure {i}: {e}")

        if num_pages > 0 and not errors:
            confidence = 0.85
        elif num_pages > 0:
            confidence = max(0.3, 0.85 - 0.1 * len(errors))
        return self._result(document_id, text_blocks, tables, figures, num_pages or 1, confidence, errors)

    def _result(
        self,
        document_id: str,
        text_blocks: list,
        tables: list,
        figures: list,
        num_pages: int,
        confidence: float,
        errors: list[str],
    ) -> ExtractionResult:
        extracted = ExtractedDocument(
            document_id=document_id,
            text_blocks=text_blocks,
            tables=tables,
            figures=figures,
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
