#!/usr/bin/env python3
"""
Phase 0: Run Docling on the same four sample PDFs and collect output quality metrics.
Output: scripts/phase0_docling_results.txt for filling DOMAIN_NOTES §2.2.

IDE freezing: Docling is memory/CPU heavy. Run in an EXTERNAL terminal (not inside Cursor),
or use: python scripts/phase0_docling_analysis.py --light  (processes first 5 pages per doc only).
"""
import gc
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
data_dir = project_root / "data"
samples = [
    "CBE ANNUAL REPORT 2023-24.pdf",
    "Audit Report - 2023.pdf",
    "fta_performance_survey_final_report_2022.pdf",
    "tax_expenditure_ethiopia_2021_22.pdf",
]
LIGHT_MODE_PAGES = 5


def make_first_n_pages_pdf(source_path: Path, n: int) -> Path:
    """Write a temporary PDF containing only the first n pages; return path to temp file."""
    try:
        import fitz
        doc = fitz.open(source_path)
        try:
            if len(doc) <= n:
                return source_path
            out = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            out.close()
            small = fitz.open()
            small.insert_pdf(doc, from_page=0, to_page=n - 1)
            small.save(out.name)
            small.close()
            return Path(out.name)
        finally:
            doc.close()
    except ImportError:
        return source_path
    except Exception:
        return source_path


def analyze_with_docling(pdf_path: Path) -> dict:
    from docling.document_converter import DocumentConverter

    result = {
        "path": pdf_path.name,
        "success": False,
        "pages": None,
        "tables_count": 0,
        "markdown_length": 0,
        "has_tables_in_md": False,
        "sample": "",
        "error": None,
    }
    try:
        converter = DocumentConverter()
        conv_result = converter.convert(str(pdf_path))
        doc = conv_result.document
        md = doc.export_to_markdown()
        result["success"] = True
        result["markdown_length"] = len(md)
        result["sample"] = (md[:1200].replace("\n", " ")[:800] + "...") if len(md) > 800 else md[:500]
        result["has_tables_in_md"] = "|" in md or "---" in md
        result["pages"] = len(doc.pages) if hasattr(doc, "pages") and doc.pages else None
        if hasattr(doc, "tables") and doc.tables:
            result["tables_count"] = len(doc.tables)
        else:
            result["tables_count"] = max(0, md.count("|") // 4) if "|" in md else 0
    except Exception as e:
        result["error"] = str(e)
    return result


def main():
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        print("Docling not installed. Run: pip install docling")
        return

    lines = ["Phase 0 Docling output quality (for DOMAIN_NOTES §2.2)", "=" * 60, ""]
    light = "--light" in sys.argv or "-l" in sys.argv
    if light:
        lines.append(f"(Light mode: first {LIGHT_MODE_PAGES} pages per document only)\n")
        print(f"Light mode: first {LIGHT_MODE_PAGES} pages per doc only")
    for name in samples:
        path = data_dir / name
        if not path.exists():
            lines.append(f"{name}: FILE NOT FOUND\n")
            continue
        to_convert = path
        temp_pdf = None
        if light:
            temp_pdf = make_first_n_pages_pdf(path, LIGHT_MODE_PAGES)
            if temp_pdf != path:
                to_convert = temp_pdf
        print(f"Processing {name}...")
        try:
            r = analyze_with_docling(to_convert)
            if temp_pdf and temp_pdf != path:
                r["path"] = name
            if temp_pdf and temp_pdf != path and temp_pdf.exists():
                try:
                    temp_pdf.unlink()
                except OSError:
                    pass
            if r["error"]:
                lines.append(f"File: {r['path']}\n  Error: {r['error']}\n")
                print(f"  Error: {r['error']}")
                continue
            lines.append(f"File: {r['path']}")
            lines.append(f"  Success: {r['success']}, Pages: {r['pages']}, Markdown length: {r['markdown_length']}")
            lines.append(f"  Tables (detected/inferred): {r['tables_count']}, Has table syntax in MD: {r['has_tables_in_md']}")
            lines.append(f"  Sample: {r['sample'][:400]}...")
            lines.append("")
            print(f"  Pages: {r['pages']}, MD len: {r['markdown_length']}, tables: {r['tables_count']}")
        finally:
            gc.collect()
    out_file = project_root / "scripts" / "phase0_docling_results.txt"
    with open(out_file, "w") as f:
        f.write("\n".join(lines))
    print("\nResults written to:", out_file)


if __name__ == "__main__":
    main()
