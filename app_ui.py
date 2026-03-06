#!/usr/bin/env python3
"""
Document Intelligence Refinery — Web UI (Streamlit).
Run from project root: streamlit run app_ui.py
Or in Colab: run pip install streamlit && streamlit run app_ui.py --server.headless true
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is on path when run as streamlit run app_ui.py
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

REFINERY = PROJECT_ROOT / ".refinery"
PROFILES_DIR = REFINERY / "profiles"
PAGEINDEX_DIR = REFINERY / "pageindex"
CHROMADB_DIR = REFINERY / "chromadb"
FACTS_DB = REFINERY / "facts.db"


def _get_document_ids() -> list[str]:
    """List document IDs from PageIndex (preferred) or profiles."""
    doc_ids = []
    if PAGEINDEX_DIR.exists():
        for f in PAGEINDEX_DIR.glob("*.json"):
            doc_ids.append(f.stem)
    if not doc_ids and PROFILES_DIR.exists():
        for f in PROFILES_DIR.glob("*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    doc_ids.append(data.get("document_id", f.stem))
            except Exception:
                doc_ids.append(f.stem)
    return sorted(set(doc_ids))


@st.cache_resource
def _load_services():
    """Load VectorStore, FactTable, QueryAgent once. Returns None if artifacts missing."""
    if not CHROMADB_DIR.exists() or not FACTS_DB.exists():
        return None
    try:
        from src.data.vector_store import VectorStore
        from src.data.fact_table import FactTableExtractor
        from src.agents.query_agent import QueryAgent

        vs = VectorStore(persist_dir=CHROMADB_DIR)
        ft = FactTableExtractor(db_path=FACTS_DB)
        qa = QueryAgent(
            pageindex_dir=PAGEINDEX_DIR,
            vector_store=vs,
            fact_table=ft,
        )
        return {"vector_store": vs, "fact_table": ft, "query_agent": qa}
    except Exception:
        return None


def _render_ask(services: dict) -> None:
    st.subheader("Ask a question")
    doc_ids = _get_document_ids()
    doc_option = ["(All documents)"] + doc_ids
    selected = st.selectbox("Document (optional)", doc_option, key="ask_doc")
    document_id = None if selected == "(All documents)" else selected
    question = st.text_area("Question", placeholder="e.g. What was the total revenue? Where is the audit opinion?")
    if st.button("Get answer", key="ask_btn"):
        if not question.strip():
            st.warning("Enter a question.")
            return
        answer, prov = services["query_agent"].answer(question.strip(), document_id=document_id)
        st.markdown("**Answer**")
        st.markdown(answer)
        if prov.citations:
            st.markdown("**Citations**")
            for i, c in enumerate(prov.citations, 1):
                snip = (c.content_snippet or "")[:200]
                st.caption(f"{i}. {c.document_name} — p.{c.page_number}: {snip}...")


def _render_audit(services: dict) -> None:
    st.subheader("Audit a claim")
    from src.data.audit import audit_mode

    doc_ids = _get_document_ids()
    doc_option = ["(All documents)"] + doc_ids
    selected = st.selectbox("Document (optional)", doc_option, key="audit_doc")
    document_id = None if selected == "(All documents)" else selected
    claim = st.text_area("Claim to verify", placeholder="e.g. The report states revenue was $4.2B in Q3")
    if st.button("Verify claim", key="audit_btn"):
        if not claim.strip():
            st.warning("Enter a claim.")
            return
        result = audit_mode(
            claim=claim.strip(),
            vector_store=services["vector_store"],
            fact_table=services["fact_table"],
            document_id=document_id,
        )
        st.markdown(f"**Decision:** {result.decision}")
        st.markdown(f"**Rationale:** {result.rationale}")
        st.markdown(f"**Evidence summary:** {result.evidence_summary}")
        if result.citations:
            st.markdown("**Citations**")
            for i, c in enumerate(result.citations, 1):
                snip = (c.content_snippet or "")[:200]
                st.caption(f"{i}. {c.document_name} — p.{c.page_number}: {snip}...")


def _render_status() -> None:
    st.subheader("Pipeline status")
    profiles_ok = PROFILES_DIR.exists() and any(PROFILES_DIR.glob("*.json"))
    pageindex_ok = PAGEINDEX_DIR.exists() and any(PAGEINDEX_DIR.glob("*.json"))
    chroma_ok = CHROMADB_DIR.exists()
    facts_ok = FACTS_DB.exists()
    st.markdown(f"- **Profiles:** {'✓' if profiles_ok else '✗'} `.refinery/profiles/`")
    st.markdown(f"- **PageIndex:** {'✓' if pageindex_ok else '✗'} `.refinery/pageindex/`")
    st.markdown(f"- **ChromaDB (LDUs):** {'✓' if chroma_ok else '✗'} `.refinery/chromadb/`")
    st.markdown(f"- **Fact table:** {'✓' if facts_ok else '✗'} `.refinery/facts.db`")
    if not (chroma_ok and facts_ok):
        st.info("Run **interim** then **final** artifacts to enable Q&A and Audit: `python scripts/run_interim_artifacts.py` then `python scripts/run_final_artifacts.py`")
    doc_ids = _get_document_ids()
    if doc_ids:
        st.markdown(f"**Indexed documents:** {len(doc_ids)} — {', '.join(doc_ids[:5])}{'…' if len(doc_ids) > 5 else ''}")


def main() -> None:
    st.set_page_config(page_title="Document Intelligence Refinery", page_icon="📄", layout="centered")
    st.title("Document Intelligence Refinery")
    st.caption("Ask questions and verify claims over your indexed documents.")

    services = _load_services()
    tab1, tab2, tab3 = st.tabs(["Ask a question", "Audit claim", "Status"])

    with tab1:
        if services:
            _render_ask(services)
        else:
            st.warning("Pipeline not ready. Run `run_interim_artifacts.py` then `run_final_artifacts.py` and refresh.")
            _render_status()

    with tab2:
        if services:
            _render_audit(services)
        else:
            st.warning("Pipeline not ready. Run final artifacts first.")
            _render_status()

    with tab3:
        _render_status()


if __name__ == "__main__":
    main()
