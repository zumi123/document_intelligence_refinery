"""Unit tests for Triage Agent classification."""
import pytest
from pathlib import Path

from src.agents.triage import triage_document
from src.models import OriginType, LayoutComplexity, EstimatedExtractionCost, DomainHint


# Use project root to find data/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def test_triage_scanned_document_classified_as_scanned():
    """A document with very low chars/page and high image ratio should be classified as scanned_image."""
    audit = DATA_DIR / "Audit Report - 2023.pdf"
    if not audit.exists():
        pytest.skip("Audit Report - 2023.pdf not found in data/")
    profile = triage_document(audit, document_id="test-audit")
    assert profile.origin_type == OriginType.SCANNED_IMAGE
    assert profile.estimated_extraction_cost == EstimatedExtractionCost.NEEDS_VISION_MODEL
    assert profile.chars_per_page_avg < 50
    assert profile.image_area_ratio_avg > 0.5


def test_triage_native_digital_gets_native_or_mixed():
    """A document with high chars/page and low image ratio should be native_digital."""
    cbe = DATA_DIR / "CBE ANNUAL REPORT 2023-24.pdf"
    if not cbe.exists():
        pytest.skip("CBE ANNUAL REPORT 2023-24.pdf not found in data/")
    profile = triage_document(cbe, document_id="test-cbe")
    assert profile.origin_type in (OriginType.NATIVE_DIGITAL, OriginType.MIXED)
    assert profile.chars_per_page_avg > 100
    assert profile.num_pages > 0
    assert profile.estimated_extraction_cost in (
        EstimatedExtractionCost.FAST_TEXT_SUFFICIENT,
        EstimatedExtractionCost.NEEDS_LAYOUT_MODEL,
    )


def test_triage_profile_has_required_fields():
    """DocumentProfile must have all classification dimensions."""
    # Use a small PDF if available; otherwise skip
    for name in ["Consumer Price Index July 2025.pdf", "CBE ANNUAL REPORT 2023-24.pdf"]:
        path = DATA_DIR / name
        if path.exists():
            profile = triage_document(path, document_id="test-fields")
            assert profile.document_id == "test-fields"
            assert profile.origin_type is not None
            assert profile.layout_complexity is not None
            assert profile.domain_hint is not None
            assert profile.estimated_extraction_cost is not None
            assert profile.num_pages >= 0
            assert 0 <= profile.image_area_ratio_avg <= 1.0
            return
    pytest.skip("No PDF found in data/")


def test_triage_nonexistent_path_raises():
    """Triage on nonexistent path must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        triage_document(PROJECT_ROOT / "nonexistent.pdf")
