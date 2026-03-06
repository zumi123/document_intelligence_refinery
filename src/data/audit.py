"""Audit Mode: Verify a claim against source citations or flag as unverifiable."""
from typing import Optional

from src.models import ProvenanceChain, ProvenanceCitation, LDU
from src.models.provenance import BBox


def verify_claim(
    claim: str,
    ldus: list[LDU],
    document_name: str = "",
) -> tuple[str, ProvenanceChain]:
    """
    Search LDUs for evidence supporting the claim.
    Returns (status, provenance_chain) where status is "verified" or "unverifiable".
    """
    claim_lower = claim.lower().strip()
    citations: list[ProvenanceCitation] = []
    for ldu in ldus:
        content_lower = (ldu.content or "").lower()
        if not content_lower:
            continue
        if claim_lower in content_lower or _overlap_score(claim_lower, content_lower) > 0.5:
            doc_name = document_name or ldu.document_id
            page = ldu.page_refs[0] if ldu.page_refs else 1
            bbox = None
            if ldu.bounding_box:
                bbox = BBox(
                    x0=ldu.bounding_box.x0,
                    top=ldu.bounding_box.top,
                    x1=ldu.bounding_box.x1,
                    bottom=ldu.bounding_box.bottom,
                )
            snippet = (ldu.content or "")[:200] + "..." if len(ldu.content or "") > 200 else (ldu.content or "")
            citations.append(
                ProvenanceCitation(
                    document_name=doc_name,
                    page_number=page,
                    bbox=bbox,
                    content_hash=ldu.content_hash,
                    content_snippet=snippet,
                )
            )
    status = "verified" if citations else "unverifiable"
    return status, ProvenanceChain(citations=citations)


def _overlap_score(a: str, b: str) -> float:
    """Simple word overlap; returns fraction of claim words found in content."""
    a_words = set(w for w in a.split() if len(w) > 2)
    b_words = set(w for w in b.split() if len(w) > 2)
    if not a_words:
        return 0.0
    return len(a_words & b_words) / len(a_words)
