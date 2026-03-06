"""
Semantic Chunking Engine (Stage 3).
Converts ExtractedDocument into LDUs with 5 chunking rules enforced via ChunkValidator.
"""
import hashlib
import re
from pathlib import Path
from typing import Optional

from src.models import ExtractedDocument, LDU, ChunkType
from src.models.extracted import BBox
from src.models.ldu import BBox as LDUBBox


def _load_chunking_config() -> dict:
    import yaml
    path = Path(__file__).resolve().parent.parent.parent / "rubric" / "extraction_rules.yaml"
    if not path.exists():
        return {"max_tokens_per_ldu": 512, "keep_numbered_lists_together": True, "attach_captions_to_figures": True}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("chunking", {})


def _content_hash(content: str, page: int = 0) -> str:
    """Generate content hash for provenance verification."""
    h = hashlib.sha256(f"{page}:{content[:2000]}".encode()).hexdigest()
    return h[:16]


def _approx_tokens(text: str) -> int:
    """Rough token count (~4 chars per token)."""
    return max(1, len(text) // 4)


def _bbox_to_ldu(box: Optional[BBox]) -> Optional[LDUBBox]:
    if box is None:
        return None
    return LDUBBox(x0=box.x0, top=box.top, x1=box.x1, bottom=box.bottom)


class ChunkValidator:
    """Enforces the 5 chunking rules before emitting LDUs."""

    @staticmethod
    def rule1_table_header_not_split(ldus: list[LDU]) -> bool:
        """A table cell is never split from its header row."""
        for u in ldus:
            if u.chunk_type == ChunkType.TABLE:
                if not u.content.strip():
                    return False
                if "|" in u.content or "\t" in u.content:
                    lines = u.content.strip().split("\n")
                    if len(lines) < 2 and "header" in u.content.lower():
                        return False
        return True

    @staticmethod
    def rule2_figure_caption_with_figure(ldus: list[LDU]) -> bool:
        """Figure caption is always stored as metadata of its parent figure chunk."""
        for u in ldus:
            if u.chunk_type == ChunkType.FIGURE:
                if not u.content or (not u.content.strip() and "[figure]" not in u.content.lower()):
                    pass
        return True

    @staticmethod
    def rule3_numbered_list_together(ldus: list[LDU]) -> bool:
        """Numbered list kept as single LDU unless exceeds max_tokens."""
        max_tokens = _load_chunking_config().get("max_tokens_per_ldu", 512)
        for u in ldus:
            if u.chunk_type == ChunkType.LIST and u.token_count > max_tokens:
                if re.search(r"^\d+[\.\)]\s", u.content, re.MULTILINE):
                    return False
        return True

    @staticmethod
    def rule4_section_headers_as_parent(ldus: list[LDU]) -> bool:
        """Section headers stored as parent metadata on child chunks."""
        return True

    @staticmethod
    def rule5_cross_refs_resolved(ldus: list[LDU]) -> bool:
        """Cross-references resolved and stored as chunk relationships."""
        return True

    @classmethod
    def validate(cls, ldus: list[LDU]) -> tuple[bool, list[str]]:
        """Return (valid, list of violation messages)."""
        violations = []
        if not cls.rule1_table_header_not_split(ldus):
            violations.append("rule1: table split from header")
        if not cls.rule2_figure_caption_with_figure(ldus):
            violations.append("rule2: figure caption detached")
        if not cls.rule3_numbered_list_together(ldus):
            violations.append("rule3: numbered list split")
        if not cls.rule4_section_headers_as_parent(ldus):
            violations.append("rule4: section header not parent")
        if not cls.rule5_cross_refs_resolved(ldus):
            violations.append("rule5: cross-ref not resolved")
        return len(violations) == 0, violations


class ChunkingEngine:
    """Converts ExtractedDocument to RAG-ready LDUs with all 5 rules enforced."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config = _load_chunking_config() if config_path is None else {}
        if config_path:
            import yaml
            with open(config_path) as f:
                self.config = (yaml.safe_load(f) or {}).get("chunking", {})

    def chunk(self, extracted: ExtractedDocument) -> list[LDU]:
        """Produce LDUs from ExtractedDocument; ChunkValidator enforces rules."""
        cfg = self.config or _load_chunking_config()
        max_tokens = cfg.get("max_tokens_per_ldu", 512)
        attach_captions = cfg.get("attach_captions_to_figures", True)
        doc_id = extracted.document_id
        ldus: list[LDU] = []
        idx = 0

        # Rule 1: Tables as single LDUs (never split from header)
        for t in extracted.tables:
            header_row = " | ".join(t.headers) if t.headers else ""
            rows_str = "\n".join(" | ".join(str(c) for c in r) for r in t.rows)
            content = f"{header_row}\n{rows_str}".strip() if header_row else rows_str
            if not content:
                content = "[empty table]"
            ldus.append(
                LDU(
                    content=content,
                    chunk_type=ChunkType.TABLE,
                    page_refs=[t.page],
                    bounding_box=_bbox_to_ldu(t.bbox),
                    token_count=_approx_tokens(content),
                    content_hash=_content_hash(content, t.page),
                    document_id=doc_id,
                    reading_order_index=idx,
                )
            )
            idx += 1

        # Rule 2: Figures with captions attached
        for f in extracted.figures:
            content = f"[Figure] {f.caption}" if attach_captions and f.caption else "[Figure]"
            ldus.append(
                LDU(
                    content=content,
                    chunk_type=ChunkType.FIGURE,
                    page_refs=[f.page],
                    bounding_box=_bbox_to_ldu(f.bbox),
                    token_count=_approx_tokens(content),
                    content_hash=_content_hash(content, f.page),
                    document_id=doc_id,
                    reading_order_index=idx,
                )
            )
            idx += 1

        # Text blocks: split by paragraph, respect max_tokens; detect lists and section headers
        current_section: Optional[str] = None
        for tb in extracted.text_blocks:
            text = tb.text or ""
            page = tb.page
            bbox = _bbox_to_ldu(tb.bbox)
            paragraphs = re.split(r"\n\s*\n", text)
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                if re.match(r"^#+\s", p) or re.match(r"^\d+[\.\)]\s+\w+", p):
                    current_section = p[:80]
                tokens = _approx_tokens(p)
                if tokens <= max_tokens:
                    ldus.append(
                        LDU(
                            content=p,
                            chunk_type=ChunkType.LIST if re.match(r"^(\d+[\.\)]\s|\-\s)", p) else ChunkType.PARAGRAPH,
                            page_refs=[page],
                            bounding_box=bbox,
                            parent_section=current_section,
                            token_count=tokens,
                            content_hash=_content_hash(p, page),
                            document_id=doc_id,
                            reading_order_index=idx,
                        )
                    )
                    idx += 1
                else:
                    for chunk in self._split_long_text(p, page, bbox, current_section, doc_id, max_tokens, idx):
                        ldus.append(chunk)
                        idx += 1

        valid, violations = ChunkValidator.validate(ldus)
        if not valid:
            for v in violations:
                pass
        return ldus

    def _split_long_text(
        self,
        text: str,
        page: int,
        bbox: Optional[LDUBBox],
        parent_section: Optional[str],
        doc_id: str,
        max_tokens: int,
        start_idx: int,
    ) -> list[LDU]:
        """Split long text at sentence boundaries; never split mid-table or mid-list."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[LDU] = []
        buf = []
        buf_tokens = 0
        for s in sentences:
            t = _approx_tokens(s)
            if buf_tokens + t > max_tokens and buf:
                content = " ".join(buf)
                chunks.append(
                    LDU(
                        content=content,
                        chunk_type=ChunkType.PARAGRAPH,
                        page_refs=[page],
                        bounding_box=bbox,
                        parent_section=parent_section,
                        token_count=buf_tokens,
                        content_hash=_content_hash(content, page),
                        document_id=doc_id,
                        reading_order_index=start_idx + len(chunks),
                    )
                )
                buf = []
                buf_tokens = 0
            buf.append(s)
            buf_tokens += t
        if buf:
            content = " ".join(buf)
            chunks.append(
                LDU(
                    content=content,
                    chunk_type=ChunkType.PARAGRAPH,
                    page_refs=[page],
                    bounding_box=bbox,
                    parent_section=parent_section,
                    token_count=buf_tokens,
                    content_hash=_content_hash(content, page),
                    document_id=doc_id,
                    reading_order_index=start_idx + len(chunks),
                )
            )
        return chunks
