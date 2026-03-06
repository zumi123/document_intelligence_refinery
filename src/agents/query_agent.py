"""Query Interface Agent (Stage 5). Three tools with routing: navigational, factual, numeric."""
import json
import re
from pathlib import Path
from typing import Optional

from src.models import LDU, PageIndex, PageIndexSection, ProvenanceChain, ProvenanceCitation
from src.models.provenance import BBox


def _question_type(question: str) -> str:
    """Route: navigational (where is X?), factual (what is X?), numeric (how much, total, sum)."""
    q = question.lower().strip()
    nav_patterns = [r"where\s+(?:is|are|can i find)", r"which\s+section", r"locate", r"find\s+(?:the\s+)?(?:section|chapter)"]
    num_patterns = [r"how\s+much", r"total\s+(?:revenue|assets|expenditure)", r"sum\s+of", r"\d+\s*%", r"what\s+(?:was|is)\s+the\s+(?:total|revenue|amount)"]
    for p in nav_patterns:
        if re.search(p, q):
            return "navigational"
    for p in num_patterns:
        if re.search(p, q):
            return "numeric"
    return "factual"


class QueryAgent:
    """Agent with routing: pageindex for navigational, semantic_search for factual, structured_query for numeric."""

    def __init__(
        self,
        pageindex_dir: Optional[Path] = None,
        vector_store=None,
        fact_table=None,
    ):
        self.pageindex_dir = pageindex_dir or Path(__file__).resolve().parent.parent.parent / ".refinery" / "pageindex"
        self.vector_store = vector_store
        self.fact_table = fact_table

    def pageindex_navigate(self, document_id: str, topic: str) -> tuple[list[PageIndexSection], ProvenanceChain]:
        """Traverse PageIndex tree to find sections relevant to topic."""
        path = self.pageindex_dir / f"{document_id}.json"
        if not path.exists():
            return [], ProvenanceChain(citations=[])
        try:
            with open(path) as f:
                data = json.load(f)
            pi = PageIndex(**data)
        except Exception:
            return [], ProvenanceChain(citations=[])
        topic_lower = topic.lower()
        matches: list[PageIndexSection] = []

        def search(section: PageIndexSection) -> None:
            if topic_lower in (section.title or "").lower() or topic_lower in (section.summary or "").lower():
                matches.append(section)
            for child in section.child_sections or []:
                search(child)

        for s in pi.sections:
            search(s)
        citations = [
            ProvenanceCitation(
                document_name=pi.document_id,
                page_number=m.page_start,
                content_snippet=(m.summary or m.title or "")[:150],
            )
            for m in matches[:3]
        ]
        return matches[:5], ProvenanceChain(citations=citations)

    def semantic_search(
        self, query: str, document_id: Optional[str] = None, top_k: int = 5
    ) -> tuple[list[LDU], ProvenanceChain]:
        """Vector similarity search over LDUs."""
        if self.vector_store is None:
            return [], ProvenanceChain(citations=[])
        results = self.vector_store.search(query, document_id=document_id, top_k=top_k)
        citations = []
        for r in results:
            ldu = r.get("ldu")
            if ldu and isinstance(ldu, LDU):
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
        ldus = [r.get("ldu") for r in results if r.get("ldu") and isinstance(r.get("ldu"), LDU)]
        return ldus, ProvenanceChain(citations=citations)

    def structured_query(self, sql: str) -> tuple[list[dict], ProvenanceChain]:
        """Run SQL over FactTable."""
        if self.fact_table is None:
            return [], ProvenanceChain(citations=[])
        rows, doc_ref = self.fact_table.query(sql)
        citations = []
        if doc_ref:
            citations.append(
                ProvenanceCitation(document_name=doc_ref, page_number=1, content_snippet="Structured fact table")
            )
        return rows, ProvenanceChain(citations=citations)

    def answer(self, question: str, document_id: Optional[str] = None) -> tuple[str, ProvenanceChain]:
        """Route by question type: navigational -> pageindex, factual -> semantic_search, numeric -> structured_query.
        Synthesize answer with cited pages and sections."""
        qtype = _question_type(question)
        prov = ProvenanceChain(citations=[])
        parts = []

        if qtype == "navigational" and document_id:
            sections, p1 = self.pageindex_navigate(document_id, question)
            if sections:
                prov.citations.extend(p1.citations)
                for s in sections[:3]:
                    parts.append(f"**{s.title}** (pages {s.page_start}-{s.page_end}): {s.summary or 'See document.'}")
            if parts:
                return "\n\n".join(parts), prov

        if qtype == "numeric" and self.fact_table:
            try:
                sql = "SELECT fact_key, fact_value FROM facts"
                if document_id:
                    sql = f"SELECT fact_key, fact_value FROM facts WHERE document_id = '{document_id}'"
                rows, p2 = self.structured_query(sql)
                prov.citations.extend(p2.citations)
                if rows:
                    lines = [f"- {r.get('fact_key', '')}: {r.get('fact_value', '')}" for r in rows[:10]]
                    return "From the fact table:\n" + "\n".join(lines), prov
            except Exception:
                pass

        ldus, p2 = self.semantic_search(question, document_id=document_id, top_k=3)
        prov.citations.extend(p2.citations)
        if ldus:
            for u in ldus[:2]:
                page = u.page_refs[0] if u.page_refs else 1
                section = getattr(u, "parent_section", None) or "Document"
                snippet = (u.content or "")[:250]
                parts.append(f"According to **page {page}** ({section}):\n{snippet}")
            return "\n\n".join(parts), prov

        return "No relevant content found.", prov
