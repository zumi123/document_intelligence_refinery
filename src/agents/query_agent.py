"""Query Interface Agent (Stage 5). Three tools: pageindex_navigate, semantic_search, structured_query."""
import json
from pathlib import Path
from typing import Optional

from src.models import LDU, PageIndex, PageIndexSection, ProvenanceChain, ProvenanceCitation
from src.models.provenance import BBox


class QueryAgent:
    """Agent with pageindex_navigate, semantic_search, structured_query. All answers carry ProvenanceChain."""

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
        """Combine tools to answer. Tries pageindex first, then semantic search."""
        prov = ProvenanceChain(citations=[])
        answer_parts = []
        if document_id:
            sections, p1 = self.pageindex_navigate(document_id, question)
            if sections:
                answer_parts.append(f"Relevant sections: {', '.join(s.title for s in sections)}")
                prov.citations.extend(p1.citations)
        ldus, p2 = self.semantic_search(question, document_id=document_id, top_k=3)
        if ldus:
            answer_parts.append("\n".join((u.content or "")[:300] for u in ldus[:2]))
            prov.citations.extend(p2.citations)
        if not answer_parts:
            return "No relevant content found.", ProvenanceChain(citations=[])
        return "\n\n".join(answer_parts), prov
