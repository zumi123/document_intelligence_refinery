"""Unit tests for extraction confidence scoring and router."""
import json
import tempfile
from pathlib import Path

import pytest

from src.models import DocumentProfile, OriginType, LayoutComplexity, EstimatedExtractionCost, DomainHint
from src.agents.triage import triage_document
from src.agents.extractor import ExtractionRouter
from src.strategies import FastTextExtractor, ExtractionResult


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def test_fast_text_extractor_returns_extraction_result():
    """FastTextExtractor.extract returns ExtractionResult with confidence in [0, 1]."""
    path = DATA_DIR / "CBE ANNUAL REPORT 2023-24.pdf"
    if not path.exists():
        pytest.skip("CBE ANNUAL REPORT 2023-24.pdf not found")
    ext = FastTextExtractor()
    result = ext.extract(path, document_id="test-doc")
    assert isinstance(result, ExtractionResult)
    assert 0 <= result.confidence_score <= 1
    assert result.extracted.document_id == "test-doc"
    assert result.extracted.strategy_used == "fast_text"
    assert result.cost_estimate_usd == 0.0
    assert len(result.extracted.text_blocks) > 0


def test_fast_text_confidence_low_for_scanned_like_document():
    """When chars/page is very low, fast text confidence should be low."""
    path = DATA_DIR / "Audit Report - 2023.pdf"
    if not path.exists():
        pytest.skip("Audit Report - 2023.pdf not found")
    ext = FastTextExtractor()
    result = ext.extract(path, document_id="test-audit")
    assert result.confidence_score < 0.7


def test_router_chooses_vision_for_scanned_profile():
    """ExtractionRouter must select vision strategy for scanned_image profile."""
    path = DATA_DIR / "Audit Report - 2023.pdf"
    if not path.exists():
        pytest.skip("Audit Report - 2023.pdf not found")
    profile = triage_document(path, document_id="router-test")
    assert profile.origin_type == OriginType.SCANNED_IMAGE
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        ledger = f.name
    try:
        router = ExtractionRouter(ledger_path=Path(ledger))
        result = router.extract(path, profile)
        assert result.strategy_name == "vision"
        assert Path(ledger).read_text().strip()
        line = json.loads(Path(ledger).read_text().strip().split("\n")[0])
        assert line["strategy_used"] == "vision"
    finally:
        Path(ledger).unlink(missing_ok=True)


def test_router_logs_ledger_entry():
    """ExtractionRouter must append one JSONL entry per extract() call."""
    path = DATA_DIR / "Consumer Price Index July 2025.pdf"
    if not path.exists():
        path = DATA_DIR / "tax_expenditure_ethiopia_2021_22.pdf"
    if not path.exists():
        pytest.skip("No PDF found in data/")
    profile = triage_document(path, document_id="ledger-test")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        ledger = f.name
    try:
        router = ExtractionRouter(ledger_path=Path(ledger))
        router.extract(path, profile)
        content = Path(ledger).read_text().strip()
        assert content
        entry = json.loads(content.split("\n")[0])
        assert "document_id" in entry
        assert "strategy_used" in entry
        assert "confidence_score" in entry
        assert "cost_estimate_usd" in entry
    finally:
        Path(ledger).unlink(missing_ok=True)
