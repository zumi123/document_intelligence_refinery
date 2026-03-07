#!/usr/bin/env python3
"""
Export concrete source-vs-extracted examples for the Extraction Quality Analysis report.
Run from project root: python scripts/export_quality_examples.py

Writes to report/examples/:
  - source_fast_text_sample.txt   (Strategy A: raw text from one page containing a table)
  - extracted_table_sample.txt    (Strategy B: first table as plain text, headers + rows)
  - extracted_table_sample.json   (Strategy B: same table as JSON for evidence)
  - extracted_table_sample.tex   (Strategy B: LaTeX tabular snippet to paste into report)

Optional: add a screenshot of the source PDF table to report/examples/source_screenshot.png
and reference it in the report for full side-by-side visual evidence.
"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

def main():
    from src.agents.triage import triage_document
    from src.strategies.fast_text import FastTextExtractor
    from src.strategies.layout import LayoutExtractor

    data_dir = project_root / "data"
    out_dir = project_root / "report" / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Prefer a document that has tables and is native digital (Strategy B will run)
    candidates = [
        "CBE ANNUAL REPORT 2023-24.pdf",
        "tax_expenditure_ethiopia_2021_22.pdf",
        "fta_performance_survey_final_report_2022.pdf",
    ]
    pdf_path = None
    for name in candidates:
        p = data_dir / name
        if p.exists():
            pdf_path = p
            break
    if not pdf_path:
        print("No PDF found in data/; create report/examples/ with placeholder content.")
        _write_placeholders(out_dir)
        return

    doc_id = pdf_path.stem
    profile = triage_document(pdf_path)

    # Strategy A: raw text from first few pages (often contains table-like lines)
    fast = FastTextExtractor()
    result_a = fast.extract(pdf_path, profile.document_id)
    source_lines = []
    for blk in (result_a.extracted.text_blocks or [])[:3]:  # first 3 pages
        t = (blk.text or "").strip()
        if t:
            source_lines.append(f"--- Page {blk.page} ---")
            source_lines.append(t[:4000])  # cap per page
            source_lines.append("")
    source_text = "\n".join(source_lines)[:8000]
    (out_dir / "source_fast_text_sample.txt").write_text(source_text, encoding="utf-8")

    # Strategy B: first table as structured output
    try:
        layout = LayoutExtractor()
        result_b = layout.extract(pdf_path, profile.document_id)
        tables = result_b.extracted.tables or []
    except Exception as e:
        tables = []
        (out_dir / "extraction_error.txt").write_text(str(e), encoding="utf-8")

    if not tables:
        _write_placeholders(out_dir)
        print("No tables extracted by Strategy B; wrote placeholder files.")
        return

    t0 = tables[0]
    headers = t0.headers or []
    rows = t0.rows or []

    # Plain text
    lines = ["Document: " + doc_id, "Page: " + str(t0.page), ""]
    lines.append("Headers: " + " | ".join(str(h) for h in headers))
    lines.append("")
    for i, row in enumerate(rows[:15]):
        lines.append("Row " + str(i + 1) + ": " + " | ".join(str(c) for c in row))
    (out_dir / "extracted_table_sample.txt").write_text("\n".join(lines), encoding="utf-8")

    # JSON
    obj = {
        "document_id": doc_id,
        "page": t0.page,
        "headers": headers,
        "rows": rows[:15],
        "row_count": len(rows),
    }
    (out_dir / "extracted_table_sample.json").write_text(
        json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # LaTeX tabular (escape special chars for LaTeX)
    def esc(s):
        return str(s).replace("&", "\\&").replace("_", "\\_").replace("%", "\\%").replace("$", "\\$")

    cols = "l" * len(headers) if headers else "l"
    tex_lines = [
        "\\begin{tabular}{" + cols + "}",
        "\\toprule",
        " & ".join(esc(h) for h in headers) + " \\\\",
        "\\midrule",
    ]
    for row in rows[:8]:
        tex_lines.append(" & ".join(esc(c) for c in row[: len(headers)]) + " \\\\")
    tex_lines.append("\\bottomrule")
    tex_lines.append("\\end{tabular}")
    (out_dir / "extracted_table_sample.tex").write_text("\n".join(tex_lines), encoding="utf-8")

    print("Wrote report/examples/source_fast_text_sample.txt")
    print("Wrote report/examples/extracted_table_sample.txt|.json|.tex")
    print("Optional: add a screenshot of the source PDF table as report/examples/source_screenshot.png")


def _write_placeholders(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "source_fast_text_sample.txt").write_text(
        "(Run scripts/export_quality_examples.py with a PDF in data/ to generate.)\n", encoding="utf-8"
    )
    (out_dir / "extracted_table_sample.txt").write_text(
        "(Run scripts/export_quality_examples.py with a PDF in data/ to generate.)\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
