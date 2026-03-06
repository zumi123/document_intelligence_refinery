"""Unit tests for ChunkValidator: deliberately break each rule and assert validator blocks emission."""
import pytest

from src.models import LDU, ChunkType
from src.agents.chunker import ChunkValidator


def _ldu(**kwargs) -> LDU:
    defaults = {
        "content": "Sample text",
        "chunk_type": ChunkType.PARAGRAPH,
        "page_refs": [1],
        "parent_section": "Document",
        "token_count": 10,
        "content_hash": "abc123",
        "document_id": "doc1",
        "reading_order_index": 0,
        "cross_refs": [],
    }
    defaults.update(kwargs)
    return LDU(**defaults)


def test_rule1_valid_table_passes():
    """Valid table with header + rows passes rule 1."""
    ldus = [
        _ldu(content="Col1 | Col2\nval1 | val2", chunk_type=ChunkType.TABLE, parent_section="Document"),
    ]
    valid, violations = ChunkValidator.validate(ldus)
    assert valid, violations


def test_rule1_breaks_when_table_split_from_header():
    """Table with 'header' in content but only 1 line fails rule 1."""
    ldus = [
        _ldu(content="header row only", chunk_type=ChunkType.TABLE, parent_section="Document"),
    ]
    valid, violations = ChunkValidator.validate(ldus)
    assert not valid
    assert any("rule1" in v for v in violations)


def test_rule4_breaks_when_parent_section_missing():
    """Non-header chunk without parent_section fails rule 4."""
    ldus = [
        _ldu(content="Some paragraph", parent_section=None),
    ]
    valid, violations = ChunkValidator.validate(ldus)
    assert not valid
    assert any("rule4" in v for v in violations)


def test_rule4_breaks_when_parent_section_empty():
    """Non-header chunk with empty parent_section fails rule 4."""
    ldus = [
        _ldu(content="Some paragraph", parent_section=""),
    ]
    valid, violations = ChunkValidator.validate(ldus)
    assert not valid
    assert any("rule4" in v for v in violations)


def test_rule5_breaks_when_cross_ref_not_resolved():
    """Chunk with 'see Table 3' but empty cross_refs fails rule 5."""
    ldus = [
        _ldu(content="As shown in see Table 3 above.", cross_refs=[]),
    ]
    valid, violations = ChunkValidator.validate(ldus)
    assert not valid
    assert any("rule5" in v for v in violations)


def test_rule5_passes_when_cross_ref_resolved():
    """Chunk with 'see Table 3' and cross_refs populated passes rule 5."""
    ldus = [
        _ldu(content="As shown in see Table 3 above.", cross_refs=["Table 3"]),
    ]
    valid, violations = ChunkValidator.validate(ldus)
    assert valid, violations


def test_rule3_breaks_when_numbered_list_split():
    """Numbered list exceeding max_tokens fails rule 3."""
    from src.agents.chunker import _load_chunking_config
    max_tok = _load_chunking_config().get("max_tokens_per_ldu", 512)
    long_list = "1. First item\n" * (max_tok // 5)
    ldus = [
        _ldu(content=long_list, chunk_type=ChunkType.LIST, token_count=max_tok + 100, parent_section="Document"),
    ]
    valid, violations = ChunkValidator.validate(ldus)
    assert not valid
    assert any("rule3" in v for v in violations)


def test_all_rules_pass_with_valid_ldus():
    """Fully valid LDUs pass all rules."""
    ldus = [
        _ldu(content="Col1 | Col2\nv1 | v2", chunk_type=ChunkType.TABLE, parent_section="Document"),
        _ldu(content="See Table 1 for details.", cross_refs=["Table 1"], parent_section="Document"),
    ]
    valid, violations = ChunkValidator.validate(ldus)
    assert valid, violations
