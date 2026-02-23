from __future__ import annotations

"""M-001 infrastructure validation tests."""

import pytest
from pathlib import Path

from factories import SampleX12
from helpers import (
    to_bytes,
    make_segment,
    make_element,
    make_spec_segment,
    make_spec_element,
)


class TestSampleX12:
    def test_build_interchange_starts_with_isa(self):
        result = SampleX12.build_interchange()
        assert result.startswith("ISA")

    def test_build_interchange_ends_with_iea(self):
        result = SampleX12.build_interchange()
        assert result.endswith("IEA~") or result.endswith("IEA*1*000000001~")

    def test_build_interchange_minimum_length(self):
        result = SampleX12.build_interchange()
        assert len(result) >= 106


class TestHelpers:
    def test_to_bytes_returns_bytes(self):
        result = to_bytes("ISA*00~")
        assert isinstance(result, bytes)

    def test_make_segment_has_required_keys(self):
        result = make_segment("ST", 1)
        assert "segment_id" in result
        assert "elements" in result

    def test_make_element_has_value_text_key(self):
        result = make_element(1, "TEST")
        assert "value_text" in result

    def test_make_spec_segment_has_segment_id_key(self):
        result = make_spec_segment("ST")
        assert "segment_id" in result

    def test_make_spec_element_has_element_id_key(self):
        result = make_spec_element(1)
        assert "element_id" in result


class TestFixtureFiles:
    def test_sample_850_loads_non_empty_bytes(self, sample_850):
        assert isinstance(sample_850, bytes)
        assert len(sample_850) > 0
