"""
PageIndex Builder (Stage 4).
Builds hierarchical navigation tree over documents with section summaries.
"""
import json
from pathlib import Path
from typing import Optional

from src.models import ExtractedDocument, PageIndex, PageIndexSection, LDU


def _detect_sections_from_ldus(ldus: list[LDU]) -> list[PageIndexSection]:
    """Build section tree from LDUs using parent_section and page_refs."""
    seen: dict[str, PageIndexSection] = {}
    for ldu in ldus:
        sec = ldu.parent_section or "Document"
        if sec not in seen:
            pages = ldu.page_refs or [1]
            seen[sec] = PageIndexSection(
                title=sec[:100],
                page_start=min(pages),
                page_end=max(pages),
                child_sections=[],
                key_entities=[],
                summary="",
                data_types_present=_data_types(ldu),
            )
        else:
            p = seen[sec]
            all_pages = (p.page_start, p.page_end) + tuple(ldu.page_refs or [1])
            p.page_start = min(all_pages)
            p.page_end = max(all_pages)
    return list(seen.values())


def _data_types(ldu: LDU) -> list[str]:
    from src.models import ChunkType
    if ldu.chunk_type.value == "table":
        return ["tables"]
    if ldu.chunk_type.value == "figure":
        return ["figures"]
    return []


def build_page_index(
    document_id: str,
    ldus: list[LDU],
    extracted: Optional[ExtractedDocument] = None,
    summary_fn=None,
) -> PageIndex:
    """
    Build PageIndex tree from LDUs.
    summary_fn(ldus_for_section) -> str for LLM-generated summaries; if None, use heuristic.
    """
    sections = _detect_sections_from_ldus(ldus)
    if summary_fn and sections:
        for s in sections:
            section_ldus = [u for u in ldus if u.parent_section == s.title]
            s.summary = summary_fn(section_ldus) or s.summary
    else:
        for s in sections:
            s.summary = f"Section '{s.title}' (pages {s.page_start}-{s.page_end})"
    return PageIndex(document_id=document_id, sections=sections)


def save_page_index(index: PageIndex, output_dir: Path) -> Path:
    """Save PageIndex to JSON in .refinery/pageindex/."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{index.document_id}.json"
    with open(path, "w") as f:
        json.dump(index.model_dump(mode="json"), f, indent=2)
    return path


def load_page_index(document_id: str, index_dir: Path) -> Optional[PageIndex]:
    """Load PageIndex from JSON."""
    path = Path(index_dir) / f"{document_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    return PageIndex.model_validate(data)
