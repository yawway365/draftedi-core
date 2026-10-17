"""Tests for JSONSkeletonSpecProvider.

_SAMPLE_850 follows the §6.2 skeleton JSON format. Temp directories are used
for isolation; no persistent skeleton files are required.
JSONSkeletonSpecProvider satisfies X12SpecProvider via structural subtyping;
no Protocol import is needed in tests to verify duck-typing compliance.
"""

from __future__ import annotations

import json
from pathlib import Path

from draftedi.spec.json_skeleton_provider import JSONSkeletonSpecProvider


# ---------------------------------------------------------------------------
# Sample skeleton JSON matching §6.2 format
# ---------------------------------------------------------------------------


_SAMPLE_850: dict = {
    "_meta": {
        "format": "draftedi-skeleton-spec",
        "format_version": "1.0",
        "x12_version": "005010",
        "transaction_set_id": "850",
        "functional_group_id": "PO",
        "generated_at": "2026-02-24T00:00:00Z",
        "data_source": "user-supplied",
        "includes_codes": False,
    },
    "segments": {
        "BEG": {
            "seq": 10,
            "area": "HEADING",
            "req": "M",
            "max_use": 1,
            "loop": None,
            "loop_level": 0,
            "loop_repeat": 1,
            "elements": [
                {
                    "pos": 1,
                    "element_id": "353",
                    "req": "M",
                    "type": "ID",
                    "min": 2,
                    "max": 2,
                    "repeat": 1,
                    "codes": [],
                },
                {
                    "pos": 2,
                    "element_id": "92",
                    "req": "M",
                    "type": "ID",
                    "min": 2,
                    "max": 2,
                    "repeat": 1,
                    "codes": ["NE", "SA"],
                },
            ],
            "relational_conditions": [],
        },
        "PO1": {
            "seq": 50,
            "area": "DETAIL",
            "req": "M",
            "max_use": 100000,
            "loop": "PO1",
            "loop_level": 1,
            "loop_repeat": 100000,
            "elements": [
                {
                    "pos": 2,
                    "element_id": "330",
                    "req": "M",
                    "type": "R",
                    "min": 1,
                    "max": 15,
                    "repeat": 1,
                    "codes": [],
                },
            ],
            "relational_conditions": [
                {"type": "P", "positions": [5, 6]},
            ],
        },
    },
}


def _write_spec(specs_dir: Path, version: str, ts_id: str, content: dict) -> None:
    path = specs_dir / f"{version}-{ts_id}.json"
    path.write_text(json.dumps(content), encoding="utf-8")


# ---------------------------------------------------------------------------
# TestJSONSkeletonSpecProvider
# ---------------------------------------------------------------------------


class TestJSONSkeletonSpecProvider:
    def test_get_transaction_set_returns_spec(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        spec = provider.get_transaction_set("005010", "850")
        assert spec is not None
        assert spec["transaction_set_id"] == "850"
        assert spec["functional_group_id"] == "PO"
        assert spec["transaction_set_name"] is None

    def test_get_transaction_set_returns_segments(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        spec = provider.get_transaction_set("005010", "850")
        assert spec is not None
        assert len(spec["segments"]) == 2
        seg_ids = {s["segment_id"] for s in spec["segments"]}
        assert "BEG" in seg_ids
        assert "PO1" in seg_ids

    def test_segment_name_is_none(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        spec = provider.get_transaction_set("005010", "850")
        assert spec is not None
        for seg in spec["segments"]:
            assert seg["segment_name"] is None

    def test_get_transaction_set_missing_file_returns_none(self, tmp_path: Path) -> None:
        provider = JSONSkeletonSpecProvider(tmp_path)
        result = provider.get_transaction_set("005010", "850")
        assert result is None

    def test_get_element_codes_empty_when_no_codes(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        provider.get_transaction_set("005010", "850")
        codes = provider.get_element_codes("005010", "353")
        assert codes == []

    def test_get_element_codes_returns_populated_codes(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        provider.get_transaction_set("005010", "850")
        codes = provider.get_element_codes("005010", "92")
        assert "NE" in codes
        assert "SA" in codes

    def test_get_available_versions_from_filenames(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        _write_spec(tmp_path, "004010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        versions = provider.get_available_versions()
        assert "005010" in versions
        assert "004010" in versions
        assert versions == sorted(versions)

    def test_get_segment_spec_finds_segment(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        seg = provider.get_segment_spec("005010", "BEG")
        assert seg is not None
        assert seg["segment_id"] == "BEG"
        assert seg["requirement"] == "M"

    def test_get_segment_spec_missing_returns_none(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        seg = provider.get_segment_spec("005010", "NOSEG")
        assert seg is None

    def test_caching_loads_file_once(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        provider.get_transaction_set("005010", "850")
        provider.get_transaction_set("005010", "850")
        assert len(provider._cache) == 1

    def test_specs_dir_expands_home(self, tmp_path: Path, monkeypatch) -> None:
        """The documented "~/.draftedi/specs/" form resolves under the home directory."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        specs = tmp_path / ".draftedi" / "specs"
        specs.mkdir(parents=True)
        _write_spec(specs, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider("~/.draftedi/specs/")
        assert provider.get_transaction_set("005010", "850") is not None
        assert provider.get_available_versions() == ["005010"]

    def test_importable_from_draftedi_spec(self) -> None:
        from draftedi.spec import JSONSkeletonSpecProvider as JSP

        assert JSP is not None


# ---------------------------------------------------------------------------
# TestPathTraversal — version/ts_id come from GS08/ST01 in untrusted documents
# ---------------------------------------------------------------------------


class TestPathTraversal:
    @staticmethod
    def _layout(tmp_path: Path) -> Path:
        """specs/ holds a valid skeleton; a decoy x-850.json sits one level up."""
        specs = tmp_path / "specs"
        specs.mkdir()
        _write_spec(specs, "005010", "850", _SAMPLE_850)
        _write_spec(tmp_path, "x", "850", _SAMPLE_850)
        return specs

    def test_rejected_versions_return_none(self, tmp_path: Path) -> None:
        specs = self._layout(tmp_path)
        provider = JSONSkeletonSpecProvider(specs)
        for version in [
            "../x",
            "..\\x",
            str(tmp_path / "x"),
            "005010/../../x",
            "005010\x00",
            "005010\n",
            "",
            "0050100000000",  # 13 chars: GS08 is at most 12
            None,
        ]:
            assert provider.get_transaction_set(version, "850") is None, version  # type: ignore[arg-type]
            assert provider.get_segment_spec(version, "BEG") is None, version  # type: ignore[arg-type]
        assert provider._cache == {}

    def test_rejected_ts_ids_return_none(self, tmp_path: Path) -> None:
        specs = self._layout(tmp_path)
        (specs / "005010-85.json").write_text(json.dumps(_SAMPLE_850), encoding="utf-8")
        provider = JSONSkeletonSpecProvider(specs)
        for ts_id in ["../850", "850/..", "85", "8500", "8.0", "850\x00", None]:
            assert provider.get_transaction_set("005010", ts_id) is None, ts_id  # type: ignore[arg-type]
        assert provider._cache == {}

    def test_valid_identifiers_still_load(self, tmp_path: Path) -> None:
        specs = self._layout(tmp_path)
        _write_spec(specs, "005010X222A1", "837", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(specs)
        assert provider.get_transaction_set("005010", "850") is not None
        assert provider.get_transaction_set("005010X222A1", "837") is not None

    def test_spec_path_stays_inside_specs_dir(self, tmp_path: Path) -> None:
        """Defence in depth: the path check holds even if the identifier check were bypassed."""
        specs = self._layout(tmp_path)
        provider = JSONSkeletonSpecProvider(specs)
        assert provider._spec_path("../x-850") is None
        assert provider._spec_path(str(tmp_path / "x-850")) is None
        assert provider._spec_path("005010-850") == (specs / "005010-850.json").absolute()

    def test_directory_named_like_spec_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "005010-850.json").mkdir()
        provider = JSONSkeletonSpecProvider(tmp_path)
        assert provider.get_transaction_set("005010", "850") is None

    def test_get_segment_spec_uses_cache(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        provider.get_transaction_set("005010", "850")
        (tmp_path / "005010-850.json").unlink()
        seg = provider.get_segment_spec("005010", "BEG")
        assert seg is not None
        assert seg["requirement"] == "M"

    def test_get_segment_spec_scans_uncached_files(self, tmp_path: Path) -> None:
        _write_spec(tmp_path, "005010", "850", _SAMPLE_850)
        provider = JSONSkeletonSpecProvider(tmp_path)
        seg = provider.get_segment_spec("005010", "PO1")
        assert seg is not None
        assert seg["loop_id"] == "PO1"
        assert "005010-850" in provider._cache
