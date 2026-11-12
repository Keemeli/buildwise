"""Shared project paths and the canonical component categories.

Resolve paths from this module rather than from the depth of a worker file.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
NORMALISED_DIR = PROJECT_ROOT / "data" / "normalised"
HTML_DIR = RAW_DIR / "html"
CATEGORIES = ("gpu", "cpu", "motherboard", "memory", "storage", "psu", "case")
