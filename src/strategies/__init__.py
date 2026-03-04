"""Extraction strategies (Strategy A/B/C) with shared interface."""
from src.strategies.base import ExtractionResult, BaseExtractor
from src.strategies.fast_text import FastTextExtractor
from src.strategies.layout import LayoutExtractor
from src.strategies.vision import VisionExtractor

__all__ = [
    "ExtractionResult",
    "BaseExtractor",
    "FastTextExtractor",
    "LayoutExtractor",
    "VisionExtractor",
]
