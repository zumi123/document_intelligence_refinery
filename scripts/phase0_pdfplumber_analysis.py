#!/usr/bin/env python3
"""
Phase 0: Character density, bbox distribution, and whitespace analysis.
Uses pdfplumber if available, else PyMuPDF (fitz). Run: python scripts/phase0_pdfplumber_analysis.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def _analyze_with_pdfplumber(pdf_path: Path) -> dict:
    import pdfplumber
    out = {"path": str(pdf_path.name), "pages": [], "summary": {}}
    total_chars, total_area, total_image_area = 0, 0.0, 0.0
    page_count = 0
    char_counts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_count += 1
            page_area = page.width * page.height
            text = page.extract_text() or ""
            n_chars = len(text.replace(" ", "").replace("\n", ""))
            char_counts.append(n_chars)
            total_chars += n_chars
            total_area += page_area
            img_area = 0.0
            for img in page.images:
                x0, top = img.get("x0", 0) or 0, img.get("top", 0) or 0
                x1, bottom = img.get("x1", 0) or 0, img.get("bottom", 0) or 0
                img_area += (x1 - x0) * (bottom - top)
            total_image_area += img_area
            out["pages"].append({
                "page": i + 1, "char_count": n_chars,
                "char_density_per_pt2": round(n_chars / page_area, 6) if page_area else 0,
                "image_area_ratio": round(img_area / page_area, 4) if page_area else 0,
                "page_area_pt2": round(page_area, 1),
            })
    if page_count > 0:
        out["summary"] = {
            "num_pages": page_count, "total_chars": total_chars,
            "chars_per_page_avg": round(total_chars / page_count, 1),
            "char_density_avg": round(total_chars / total_area, 6) if total_area else 0,
            "total_image_area_ratio": round(total_image_area / total_area, 4) if total_area else 0,
            "min_chars_page": min(char_counts), "max_chars_page": max(char_counts),
        }
    return out


def _analyze_with_fitz(pdf_path: Path) -> dict:
    import fitz
    out = {"path": str(pdf_path.name), "pages": [], "summary": {}}
    total_chars, total_area, total_image_area = 0, 0.0, 0.0
    page_count = 0
    char_counts = []
    doc = fitz.open(pdf_path)
    try:
        for i in range(len(doc)):
            page = doc[i]
            page_count += 1
            rect = page.rect
            page_area = rect.width * rect.height
            text = page.get_text()
            n_chars = len(text.replace(" ", "").replace("\n", ""))
            char_counts.append(n_chars)
            total_chars += n_chars
            total_area += page_area
            img_area = 0.0
            for img in page.get_image_info():
                bbox = img.get("bbox")
                if bbox:
                    img_area += (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            total_image_area += img_area
            out["pages"].append({
                "page": i + 1, "char_count": n_chars,
                "char_density_per_pt2": round(n_chars / page_area, 6) if page_area else 0,
                "image_area_ratio": round(img_area / page_area, 4) if page_area else 0,
                "page_area_pt2": round(page_area, 1),
            })
    finally:
        doc.close()
    if page_count > 0:
        out["summary"] = {
            "num_pages": page_count, "total_chars": total_chars,
            "chars_per_page_avg": round(total_chars / page_count, 1),
            "char_density_avg": round(total_chars / total_area, 6) if total_area else 0,
            "total_image_area_ratio": round(total_image_area / total_area, 4) if total_area else 0,
            "min_chars_page": min(char_counts), "max_chars_page": max(char_counts),
        }
    return out


def analyze_pdf(pdf_path: Path) -> dict:
    try:
        import pdfplumber
        return _analyze_with_pdfplumber(pdf_path)
    except ImportError:
        pass
    try:
        import fitz
        return _analyze_with_fitz(pdf_path)
    except ImportError:
        raise ImportError("Install pdfplumber or pymupdf: pip install pdfplumber")


def main():
    data_dir = project_root / "data"
    if not data_dir.is_dir():
        print("Data directory not found:", data_dir)
        return

    samples = [
        "CBE ANNUAL REPORT 2023-24.pdf",
        "Audit Report - 2023.pdf",
        "fta_performance_survey_final_report_2022.pdf",
        "tax_expenditure_ethiopia_2021_22.pdf",
    ]

    print("Phase 0: Character density / bbox / image-area analysis (pdfplumber or PyMuPDF)")
    print("=" * 60)
    results = []
    for name in samples:
        path = data_dir / name
        if not path.exists():
            print("Skip (not found):", name)
            continue
        print("\n---", name, "---")
        try:
            r = analyze_pdf(path)
            results.append(r)
            s = r["summary"]
            print(f"  Pages: {s.get('num_pages')}, Chars/page (avg): {s.get('chars_per_page_avg')}, "
                  f"Char density: {s.get('char_density_avg')}, Image ratio: {s.get('total_image_area_ratio')}")
            print(f"  Min/max chars per page: {s.get('min_chars_page')} / {s.get('max_chars_page')}")
        except Exception as e:
            print("  Error:", e)
            results.append({"path": name, "error": str(e)})

    out_file = project_root / "scripts" / "phase0_pdfplumber_results.txt"
    with open(out_file, "w") as f:
        f.write("Phase 0 analysis (for DOMAIN_NOTES.md)\n\n")
        for r in results:
            if "error" in r:
                f.write(f"{r['path']}: ERROR {r['error']}\n\n")
                continue
            f.write(f"File: {r['path']}\n  {r['summary']}\n\n")
    print("\nResults written to:", out_file)
    return results


if __name__ == "__main__":
    main()
