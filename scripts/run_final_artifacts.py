#!/usr/bin/env python3
"""
Generate final artifacts: PageIndex for 12 docs, ingest LDUs to ChromaDB, 12 Q&A examples.
Run from project root: python scripts/run_final_artifacts.py
Requires: data/, .refinery/profiles/, extraction already run (or run run_interim_artifacts.py first).
"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

INTERIM_DOCS = [
    "CBE ANNUAL REPORT 2023-24.pdf",
    "CBE Annual Report 2018-19.pdf",
    "CBE Annual Report 2016-17.pdf",
    "Audit Report - 2023.pdf",
    "2018_Audited_Financial_Statement_Report.pdf",
    "2020_Audited_Financial_Statement_Report.pdf",
    "fta_performance_survey_final_report_2022.pdf",
    "20191010_Pharmaceutical-Manufacturing-Opportunites-in-Ethiopia_VF.pdf",
    "Security_Vulnerability_Disclosure_Standard_Procedure_1.pdf",
    "tax_expenditure_ethiopia_2021_22.pdf",
    "Consumer Price Index September 2025.pdf",
    "Consumer Price Index July 2025.pdf",
]

# 12 Q&A examples: 3 per class (A/B/C/D), with question + expected provenance
QA_EXAMPLES = [
    {"class": "A", "doc": "CBE ANNUAL REPORT 2023-24.pdf", "question": "What was the total revenue in the fiscal year?"},
    {"class": "A", "doc": "CBE Annual Report 2018-19.pdf", "question": "What is the bank's total assets?"},
    {"class": "A", "doc": "CBE Annual Report 2016-17.pdf", "question": "What are the key financial highlights?"},
    {"class": "B", "doc": "Audit Report - 2023.pdf", "question": "What is the auditor's opinion?"},
    {"class": "B", "doc": "2018_Audited_Financial_Statement_Report.pdf", "question": "What are the main audit findings?"},
    {"class": "B", "doc": "2020_Audited_Financial_Statement_Report.pdf", "question": "What is the scope of the audit?"},
    {"class": "C", "doc": "fta_performance_survey_final_report_2022.pdf", "question": "What are the key assessment findings?"},
    {"class": "C", "doc": "20191010_Pharmaceutical-Manufacturing-Opportunites-in-Ethiopia_VF.pdf", "question": "What opportunities are identified?"},
    {"class": "C", "doc": "Security_Vulnerability_Disclosure_Standard_Procedure_1.pdf", "question": "What is the vulnerability disclosure process?"},
    {"class": "D", "doc": "tax_expenditure_ethiopia_2021_22.pdf", "question": "What is the total tax expenditure?"},
    {"class": "D", "doc": "Consumer Price Index September 2025.pdf", "question": "What is the CPI inflation rate?"},
    {"class": "D", "doc": "Consumer Price Index July 2025.pdf", "question": "What are the main price indices?"},
]


def main():
    from src.agents.triage import triage_document
    from src.agents.extractor import ExtractionRouter
    from src.agents.chunker import ChunkingEngine
    from src.agents.indexer import build_page_index
    from src.data.vector_store import VectorStore
    from src.data.fact_table import FactTableExtractor
    from src.agents.query_agent import QueryAgent
    from src.data.audit import verify_claim

    data_dir = project_root / "data"
    profiles_dir = project_root / ".refinery" / "profiles"
    pageindex_dir = project_root / ".refinery" / "pageindex"
    qa_dir = project_root / ".refinery" / "qa_examples"
    ledger_path = project_root / ".refinery" / "extraction_ledger.jsonl"

    pageindex_dir.mkdir(parents=True, exist_ok=True)
    qa_dir.mkdir(parents=True, exist_ok=True)

    router = ExtractionRouter(ledger_path=ledger_path)
    chunker = ChunkingEngine()
    vector_store = VectorStore()
    fact_extractor = FactTableExtractor(project_root / ".refinery" / "facts.db")
    query_agent = QueryAgent(pageindex_dir=pageindex_dir, vector_store=vector_store, fact_table=fact_extractor)

    qa_results = []

    for name in INTERIM_DOCS:
        path = data_dir / name
        if not path.exists():
            print("Skip (not found):", name)
            continue
        print("Processing:", name)
        try:
            profile = triage_document(path)
            result = router.extract(path, profile)
            extracted = result.extracted
            ldus = chunker.chunk(extracted)
            pi = build_page_index(profile.document_id, ldus, extracted)
            pi_path = pageindex_dir / f"{profile.document_id}.json"
            with open(pi_path, "w") as f:
                json.dump(pi.model_dump(mode="json"), f, indent=2)
            vector_store.ingest(ldus, profile.document_id)
            fact_extractor.ingest(profile.document_id, ldus)
        except Exception as e:
            print("  Error:", e)

    for ex in QA_EXAMPLES:
        doc_name = ex["doc"]
        path = data_dir / doc_name
        if not path.exists():
            continue
        profile = triage_document(path)
        result = router.extract(path, profile)
        ldus = chunker.chunk(result.extracted)
        answer, prov = query_agent.answer(ex["question"], profile.document_id)
        status, audit_prov = verify_claim(ex["question"], ldus, doc_name)
        qa_results.append({
            "class": ex["class"],
            "document": doc_name,
            "question": ex["question"],
            "answer": answer[:500],
            "provenance_chain": prov.model_dump(mode="json"),
            "audit_status": status,
        })

    with open(qa_dir / "qa_examples.json", "w") as f:
        json.dump(qa_results, f, indent=2)
    print("\nPageIndex written to .refinery/pageindex/")
    print("Q&A examples written to .refinery/qa_examples/qa_examples.json")


if __name__ == "__main__":
    main()
