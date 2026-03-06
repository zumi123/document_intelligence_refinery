## Document Intelligence Refinery (TRP1 Week 3)

Multi-stage **Document Intelligence Refinery** pipeline: Triage → Extraction (A/B/C) → Chunking → PageIndex → Query Agent with provenance.

### Setup

```bash
cd document_intelligence
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Optional (for Docling/Strategy B and Phase 0 scripts):

```bash
pip install docling pymupdf pyyaml
```

### Run (interim deliverables)

**1. Triage a single document**

```bash
python -c "
from pathlib import Path
from src.agents.triage import triage_document
p = Path('data/CBE ANNUAL REPORT 2023-24.pdf')
profile = triage_document(p)
print(profile.model_dump_json(indent=2))
"
```

**2. Generate 12 profiles + extraction ledger (min 3 per class)**

```bash
python scripts/run_interim_artifacts.py
```

Writes:

- `.refinery/profiles/{doc_id}.json` — DocumentProfile for each document
- `.refinery/extraction_ledger.jsonl` — strategy_used, confidence_score, cost_estimate per run

**3. Phase 0 analysis (character density, Docling comparison)**

```bash
python scripts/phase0_pdfplumber_analysis.py
python scripts/phase0_docling_analysis.py --light   # optional; use --light on low RAM
```

**4. Full pipeline (final): PageIndex, ChromaDB, FactTable, 12 Q&A examples**

```bash
python scripts/run_final_artifacts.py
```

Requires `run_interim_artifacts.py` (or equivalent) to have run first. Writes:

- `.refinery/pageindex/{doc_id}.json` — PageIndex trees
- `.refinery/chromadb/` — Vector store (LDUs)
- `.refinery/facts.db` — SQLite fact table
- `.refinery/qa_examples/qa_examples.json` — 12 Q&A with ProvenanceChain

### Project layout

| Path | Description |
|------|-------------|
| `src/models/` | Pydantic schemas: `DocumentProfile`, `ExtractedDocument`, `LDU`, `PageIndex`, `ProvenanceChain` |
| `src/agents/triage.py` | Triage Agent (origin_type, layout_complexity, domain_hint) |
| `src/agents/extractor.py` | ExtractionRouter with confidence-gated escalation |
| `src/agents/chunker.py` | ChunkingEngine + ChunkValidator (5 rules) |
| `src/agents/indexer.py` | PageIndex tree builder |
| `src/agents/query_agent.py` | Query Agent: pageindex_navigate, semantic_search, structured_query |
| `src/strategies/` | `FastTextExtractor`, `LayoutExtractor`, `VisionExtractor` |
| `src/data/` | FactTable (SQLite), VectorStore (ChromaDB), Audit Mode |
| `rubric/extraction_rules.yaml` | Thresholds, chunking, **VLM budget caps**, **layout heuristics**, **domain_keywords** (edit only to onboard new domains) |
| `data/` | PDF corpus; see `data/CORPUS_MANIFEST.md` |
| `.refinery/profiles/` | DocumentProfile JSON outputs |
| `.refinery/pageindex/` | PageIndex trees (JSON) |
| `.refinery/extraction_ledger.jsonl` | Extraction run log |
| `.refinery/qa_examples/` | 12 Q&A with ProvenanceChain |
| `DOMAIN_NOTES.md` | Phase 0 + Cost Analysis + Extraction Quality + Lessons Learned |

### Audit mode (claim verification)

Explicit entry point for compliance and formal review workflows:

```bash
python scripts/audit_claim.py "The report states revenue was $4.2B in Q3"
python scripts/audit_claim.py "Auditor issued unqualified opinion" --doc-id <document_id>
```

Returns a structured result: `decision` (verified/not_found), `citations`, `rationale`, `evidence_summary`. Requires `run_final_artifacts.py` to have populated the vector store and fact table.

### Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests cover Triage Agent classification (origin_type, layout_complexity) and extraction confidence scoring (FastTextExtractor confidence, ExtractionRouter strategy selection and ledger).
