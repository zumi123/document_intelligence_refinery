"""
Audit Mode: Explicit entry point for claim verification.
Accepts a free-text claim, searches facts/LDUs, returns verified/not-found decision with citations.
Suitable for compliance and formal review workflows.
"""
import re
from typing import Optional, Any

from pydantic import BaseModel, Field

from src.models import ProvenanceChain, ProvenanceCitation, LDU
from src.models.provenance import BBox


class AuditResult(BaseModel):
    """Structured audit result for compliance workflows."""

    claim: str = Field(..., description="The claim that was verified")
    decision: str = Field(..., description="verified | not_found")
    citations: list[ProvenanceCitation] = Field(default_factory=list)
    rationale: str = Field("", description="Brief explanation of the decision")
    evidence_summary: str = Field("", description="Summary of evidence found (or lack thereof)")
    provenance_chain: ProvenanceChain = Field(default_factory=ProvenanceChain)


def audit_mode(
    claim: str,
    vector_store: Optional[Any] = None,
    fact_table: Optional[Any] = None,
    document_id: Optional[str] = None,
) -> AuditResult:
    """
    Explicit audit-mode entry point for claim verification.
    Searches relevant facts and LDUs, returns verified/not-found decision with citations.
    Suitable for compliance and formal review workflows.
    """
    claim = (claim or "").strip()
    citations: list[ProvenanceCitation] = []
    evidence_parts: list[str] = []

    # Search vector store (LDUs)
    if vector_store and claim:
        try:
            results = vector_store.search(claim, document_id=document_id, top_k=5)
            for r in results:
                ldu = r.get("ldu")
                if ldu and isinstance(ldu, LDU):
                    content_lower = (ldu.content or "").lower()
                    claim_lower = claim.lower()
                    if claim_lower in content_lower or _overlap_score(claim_lower, content_lower) > 0.3:
                        bbox = None
                        if ldu.bounding_box:
                            bbox = BBox(
                                x0=ldu.bounding_box.x0,
                                top=ldu.bounding_box.top,
                                x1=ldu.bounding_box.x1,
                                bottom=ldu.bounding_box.bottom,
                            )
                        citations.append(
                            ProvenanceCitation(
                                document_name=ldu.document_id,
                                page_number=ldu.page_refs[0] if ldu.page_refs else 1,
                                bbox=bbox,
                                content_hash=ldu.content_hash,
                                content_snippet=(ldu.content or "")[:200],
                            )
                        )
                        evidence_parts.append(f"LDU (p.{ldu.page_refs[0] if ldu.page_refs else 1}): {(ldu.content or '')[:100]}...")
        except Exception:
            pass

    # Search fact table for key-value matches
    if fact_table and claim:
        try:
            keys = _extract_fact_keys(claim)
            for key in keys[:5]:
                rows, doc_ref = fact_table.query(
                    "SELECT document_id, fact_key, fact_value, page_ref FROM facts WHERE fact_key LIKE ? LIMIT 5",
                    (f"%{key}%",),
                )
                for row in rows:
                    citations.append(
                        ProvenanceCitation(
                            document_name=row.get("document_id", doc_ref or ""),
                            page_number=row.get("page_ref") or 1,
                            content_snippet=f"{row.get('fact_key', '')}: {row.get('fact_value', '')}",
                        )
                    )
                    evidence_parts.append(f"Fact: {row.get('fact_key')}={row.get('fact_value')}")
        except Exception:
            pass

    decision = "verified" if citations else "not_found"
    rationale = (
        f"Found {len(citations)} supporting citation(s) in LDUs and fact table."
        if citations
        else "No supporting evidence found in LDUs or fact table."
    )
    evidence_summary = "; ".join(evidence_parts[:3]) if evidence_parts else "None"

    return AuditResult(
        claim=claim,
        decision=decision,
        citations=citations,
        rationale=rationale,
        evidence_summary=evidence_summary,
        provenance_chain=ProvenanceChain(citations=citations),
    )


def _extract_fact_keys(claim: str) -> list[str]:
    """Extract potential fact keys from claim (e.g. revenue, expenditure, total)."""
    stop = {"the", "was", "were", "is", "are", "in", "for", "to", "of", "a", "an", "and", "or"}
    words = re.findall(r"[a-zA-Z_]+", claim)
    return [w for w in words if len(w) > 2 and w.lower() not in stop][:10]


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
