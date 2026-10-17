"""M-001 infrastructure validation tests."""

from __future__ import annotations

import pytest

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

    # malformed_isa, missing_gs and truncated_file are deliberately broken.
    @pytest.mark.parametrize(
        "name",
        [
            "sample_850.edi",
            "sample_997.edi",
            "sample_850_004010.edi",
            "sample_997_004010.edi",
        ],
    )
    def test_envelope_counts_and_control_numbers_match(self, sample_edi_path, name):
        """SE01/GE01/IEA01 counts and trailer control numbers match their headers."""
        text = (sample_edi_path / name).read_text()
        element_sep, segment_term = text[3], text[105]
        control = {}
        groups = transactions = segments = 0
        seen = set()
        for raw in text.split(segment_term):
            if not raw.strip():
                continue
            parts = raw.strip().split(element_sep)
            seg_id = parts[0]
            segments += 1
            if seg_id == "ISA":
                control["ISA"], groups = parts[13], 0
            elif seg_id == "GS":
                control["GS"], transactions = parts[6], 0
                groups += 1
            elif seg_id == "ST":
                control["ST"], segments = parts[2], 1
                transactions += 1
            elif seg_id == "SE":
                assert (int(parts[1]), parts[2]) == (segments, control["ST"])
            elif seg_id == "GE":
                assert (int(parts[1]), parts[2]) == (transactions, control["GS"])
            elif seg_id == "IEA":
                assert (int(parts[1]), parts[2]) == (groups, control["ISA"])
            seen.add(seg_id)
        assert {"SE", "GE", "IEA"} <= seen


class TestPackaging:
    def test_version_matches_installed_metadata(self):
        from importlib.metadata import version

        import draftedi

        assert draftedi.__version__ == version("draftedi")

    def test_ships_py_typed_marker(self):
        from pathlib import Path

        import draftedi

        assert (Path(draftedi.__file__).parent / "py.typed").is_file()
