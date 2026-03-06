#!/usr/bin/env python3
"""
Audit-mode entry point: verify a free-text claim against the refinery corpus.
Returns verified/not_found decision with citations for compliance workflows.

Usage:
  python scripts/audit_claim.py "The report states revenue was $4.2B in Q3"
  python scripts/audit_claim.py "Auditor issued unqualified opinion" --doc-id abc123
"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/audit_claim.py \"<claim>\" [--doc-id DOCUMENT_ID]")
        sys.exit(1)
    claim = sys.argv[1]
    doc_id = None
    if "--doc-id" in sys.argv:
        i = sys.argv.index("--doc-id")
        if i + 1 < len(sys.argv):
            doc_id = sys.argv[i + 1]

    from src.data.audit import audit_mode
    from src.data.vector_store import VectorStore
    from src.data.fact_table import FactTableExtractor

    vs = VectorStore(project_root / ".refinery" / "chromadb")
    ft = FactTableExtractor(project_root / ".refinery" / "facts.db")
    result = audit_mode(claim, vector_store=vs, fact_table=ft, document_id=doc_id)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
