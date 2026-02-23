"""Shared test fixtures for draftedi."""

from __future__ import annotations
from pathlib import Path
import pytest


@pytest.fixture
def sample_edi_path():
    """Path to the static test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_850(sample_edi_path):
    """Raw bytes of a sample 850 Purchase Order."""
    return (sample_edi_path / "sample_850.edi").read_bytes()


@pytest.fixture
def sample_997(sample_edi_path):
    """Raw bytes of a sample 997 Functional Acknowledgment."""
    return (sample_edi_path / "sample_997.edi").read_bytes()
