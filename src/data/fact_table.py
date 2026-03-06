"""
FactTable extractor with SQLite backend for numerical documents.
Extracts key-value facts (e.g. revenue: $4.2B, date: Q3 2024) for structured querying.
"""
import re
import sqlite3
from pathlib import Path
from typing import Optional

from src.models import LDU, ChunkType
from src.models.extracted import TableBlock


def _extract_numeric_facts(content: str) -> list[tuple[str, str, str]]:
    """Heuristic: extract (key, value, unit) from table-like text."""
    facts = []
    lines = content.strip().split("\n")
    for line in lines:
        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                key = re.sub(r"[^\w\s]", "", parts[0]).strip()[:64]
                val = parts[1].strip()
                if key and val and (re.search(r"[\d,\.\$%]", val) or len(val) < 50):
                    facts.append((key, val, ""))
        elif ":" in line or "\t" in line:
            sep = ":" if ":" in line else "\t"
            parts = line.split(sep, 1)
            if len(parts) == 2:
                key = re.sub(r"[^\w\s]", "", parts[0]).strip()[:64]
                val = parts[1].strip()
                if key and val:
                    facts.append((key, val, ""))
    return facts


class FactTableExtractor:
    """Extract key-value facts from LDUs and store in SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else Path(".refinery/facts.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    document_id TEXT,
                    fact_key TEXT,
                    fact_value TEXT,
                    unit TEXT,
                    page_ref INTEGER,
                    content_hash TEXT,
                    PRIMARY KEY (document_id, fact_key, fact_value)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_doc ON facts(document_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(fact_key)")

    def ingest(self, document_id: str, ldus: list[LDU]) -> int:
        """Extract facts from LDUs and insert into SQLite. Returns count inserted."""
        count = 0
        with sqlite3.connect(self.db_path) as conn:
            for ldu in ldus:
                if ldu.chunk_type != ChunkType.TABLE and ldu.chunk_type.value != "paragraph":
                    continue
                facts = _extract_numeric_facts(ldu.content)
                page = ldu.page_refs[0] if ldu.page_refs else 0
                for key, val, unit in facts:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO facts (document_id, fact_key, fact_value, unit, page_ref, content_hash) VALUES (?,?,?,?,?,?)",
                            (document_id, key, val, unit, page, ldu.content_hash),
                        )
                        if conn.total_changes:
                            count += 1
                    except Exception:
                        pass
        return count

    def extract_from_tables(
        self,
        tables: list[TableBlock],
        document_id: str,
        document_name: str = "",
    ) -> int:
        """Extract key-value facts from TableBlocks (headers + rows) and insert into SQLite."""
        count = 0
        with sqlite3.connect(self.db_path) as conn:
            for t in tables:
                headers = t.headers or []
                for row in t.rows or []:
                    for i, h in enumerate(headers):
                        if i < len(row):
                            key = re.sub(r"[^\w\s]", "", str(h)).strip()[:64]
                            val = str(row[i]).strip()
                            if key and val and (re.search(r"[\d,\.\$%]", val) or len(val) < 100):
                                try:
                                    conn.execute(
                                        "INSERT OR IGNORE INTO facts (document_id, fact_key, fact_value, unit, page_ref, content_hash) VALUES (?,?,?,?,?,?)",
                                        (document_id, key, val, "", t.page, ""),
                                    )
                                    count += 1
                                except Exception:
                                    pass
        return count

    def query(self, sql: str, params: tuple = ()) -> tuple[list[dict], Optional[str]]:
        """Run SQL query over facts table. Returns (rows as list of dict, document_id for provenance)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            doc_ref = rows[0].get("document_id") if rows and "document_id" in (rows[0] or {}) else None
            if not doc_ref:
                cur2 = conn.execute("SELECT document_id FROM facts LIMIT 1")
                r = cur2.fetchone()
                doc_ref = r[0] if r else None
            return rows, doc_ref
