"""Strategy B: Layout-aware extraction using Docling."""
from pathlib import Path

from src.models import ExtractedDocument, TextBlock, TableBlock, FigureBlock
from src.strategies.base import BaseExtractor, ExtractionResult


class LayoutExtractor(BaseExtractor):
    """Docling-based extraction; tables and structure preserved."""

    @property
    def name(self) -> str:
        return "layout"

    def extract(self, pdf_path: Path, document_id: str) -> ExtractionResult:
        text_blocks: list[TextBlock] = []
        tables: list[TableBlock] = []
        figures: list[FigureBlock] = []
        num_pages = 0
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(str(pdf_path))
            doc = result.document
            md = doc.export_to_markdown()
            num_pages = len(doc.pages) if hasattr(doc, "pages") and doc.pages else 0
            # Single text block from full markdown for now; can be split by section later
            text_blocks.append(
                TextBlock(text=md[:50000], page=1, bbox=None, reading_order_index=0)
            )
            if hasattr(doc, "tables") and doc.tables:
                for t in doc.tables:
                    headers = getattr(t, "headers", []) or []
                    rows = getattr(t, "rows", []) or []
                    tables.append(
                        TableBlock(headers=list(headers), rows=list(rows), page=1, reading_order_index=len(tables))
                    )
            confidence = 0.85 if num_pages else 0.0
        except ImportError:
            confidence = 0.0
        except Exception:
            confidence = 0.3
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
            cost_estimate_usd=0.0,
            strategy_name=self.name,
        )
