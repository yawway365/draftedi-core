"""Tests for validate_edi() public API.

Covers: spec-absent path (is_valid=None), spec-present path, parse failure
(is_valid=False), and top-level __all__ export presence. (ref: DL-003, DL-006)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from factories import SampleX12
from draftedi import validate_edi, ValidationResult
from draftedi.spec.protocol import TransactionSetSpec, SegmentSpec


# ---------------------------------------------------------------------------
# Minimal EDI fixture
# ---------------------------------------------------------------------------


def _minimal_edi() -> str:
    return SampleX12.build_interchange()


class MinimalProvider:
    def get_transaction_set(self, version: str, ts_id: str) -> Optional[TransactionSetSpec]:
        return None

    def get_element_codes(self, version: str, element_id: str) -> list[str]:
        return []

    def get_segment_spec(self, version: str, segment_id: str) -> Optional[SegmentSpec]:
        return None

    def get_available_versions(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# TestValidateEdi
# ---------------------------------------------------------------------------


class TestValidateEdi:
    def test_no_spec_returns_is_valid_none(self) -> None:
        result = validate_edi(_minimal_edi())
        assert result.is_valid is None

    def test_no_spec_has_warnings(self) -> None:
        result = validate_edi(_minimal_edi())
        assert len(result.warnings) > 0

    def test_no_spec_no_raise(self) -> None:
        result = validate_edi(_minimal_edi())
        assert isinstance(result, ValidationResult)

    def test_with_spec_provider_returns_result(self) -> None:
        result = validate_edi(_minimal_edi(), spec_provider=MinimalProvider())
        assert isinstance(result, ValidationResult)
        assert result.is_valid is None
        assert any("No spec" in w for w in result.warnings)

    def test_invalid_edi_returns_is_valid_false(self) -> None:
        result = validate_edi("NOT_VALID_EDI_AT_ALL")
        assert result.is_valid is False

    def test_invalid_edi_has_error(self) -> None:
        result = validate_edi("NOT_VALID_EDI_AT_ALL")
        assert len(result.errors) > 0 or result.is_valid is False

    def test_imports_from_top_level(self) -> None:
        from draftedi import validate_edi, X12Validator, ValidationResult, ValidationError

        assert validate_edi
        assert X12Validator
        assert ValidationResult
        assert ValidationError

    def test_all_exports_in_dunder_all(self) -> None:
        import draftedi

        assert "validate_edi" in draftedi.__all__
        assert "X12Validator" in draftedi.__all__
        assert "ValidationResult" in draftedi.__all__
        assert "ValidationError" in draftedi.__all__

    def test_validate_edi_with_json_skeleton_provider(self, tmp_path: Path) -> None:
        from draftedi.spec.json_skeleton_provider import JSONSkeletonSpecProvider

        spec_data = {
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
            "segments": {},
        }
        spec_file = tmp_path / "005010-850.json"
        spec_file.write_text(json.dumps(spec_data), encoding="utf-8")
        provider = JSONSkeletonSpecProvider(tmp_path)
        result = validate_edi(_minimal_edi(), spec_provider=provider)
        assert isinstance(result, ValidationResult)

    def test_does_not_break_parse_edi_file(self) -> None:
        from draftedi import parse_edi_file

        edi = _minimal_edi()
        parsed = parse_edi_file(edi.encode())
        assert parsed is not None
        assert len(parsed["interchanges"]) > 0


# ---------------------------------------------------------------------------
# 1.3.1 fixes: envelope control numbers/counts, severity routing, never-raises
# ---------------------------------------------------------------------------

_ISA = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
    "*260222*1200*^*00501*000000001*0*P*:~"
)

_PO_BODY = [
    "BEG*00*NE*PO-1**20260222",
    "PO1*1*10*EA*2.5**BP*A",
    "PO1*2*5*EA*1.5**BP*B",
    "CTT*2",
]


def _edi(
    body: Optional[list[str]] = None,
    se01: Optional[str] = None,
    se02: str = "0001",
    ge01: str = "1",
    ge02: str = "1",
    iea01: str = "1",
    iea02: str = "000000001",
    version: str = "005010",
) -> str:
    """One interchange/group/850 whose trailers are correct unless overridden."""
    body = _PO_BODY if body is None else body
    se01 = str(len(body) + 2) if se01 is None else se01
    return (
        _ISA
        + f"GS*PO*S*R*20260222*1200*1*X*{version}~"
        + "ST*850*0001~"
        + "".join(f"{s}~" for s in body)
        + f"SE*{se01}*{se02}~GE*{ge01}*{ge02}~IEA*{iea01}*{iea02}~"
    )


def _skeleton(segments: dict) -> dict:
    return {
        "_meta": {"transaction_set_id": "850", "functional_group_id": "PO"},
        "segments": segments,
    }


def _skel_seg(req: str, max_use: int, loop: Optional[str] = None, elements: tuple = ()) -> dict:
    return {
        "seq": 0,
        "area": "HEADING",
        "req": req,
        "max_use": max_use,
        "loop": loop,
        "loop_level": 1 if loop else 0,
        "loop_repeat": 100000 if loop else 1,
        "elements": list(elements),
        "relational_conditions": [],
    }


def _skel_el(pos: int, element_id: str, req: str = "O", typ: str = "AN") -> dict:
    return {
        "pos": pos,
        "element_id": element_id,
        "req": req,
        "type": typ,
        "min": 1,
        "max": 30,
        "repeat": 1,
        "codes": [],
    }


_SKELETON_850 = _skeleton(
    {
        "BEG": _skel_seg(
            "M",
            1,
            elements=(
                _skel_el(1, "353", "M", "ID"),
                _skel_el(2, "92", "M", "ID"),
                _skel_el(5, "373", "M", "DT"),
            ),
        ),
        # Real X12 850: PO1 max use is 1 per iteration; the loop repeats.
        "PO1": _skel_seg("M", 1, loop="PO1"),
        "CTT": _skel_seg("O", 1),
    }
)


def _provider(tmp_path: Path, content: object = None, raw: Optional[str] = None):
    from draftedi.spec.json_skeleton_provider import JSONSkeletonSpecProvider

    spec_file = tmp_path / "005010-850.json"
    spec_file.write_text(
        raw if raw is not None else json.dumps(content or _SKELETON_850), encoding="utf-8"
    )
    return JSONSkeletonSpecProvider(tmp_path)


class _RaisingProvider(MinimalProvider):
    def get_transaction_set(self, version: str, ts_id: str) -> Optional[TransactionSetSpec]:
        raise RuntimeError("backend down")


class TestValidateEdiEnvelope:
    def test_valid_document_with_spec(self, tmp_path: Path) -> None:
        """Two PO1 loop iterations are valid (audit item 1, end to end)."""
        result = validate_edi(_edi(), spec_provider=_provider(tmp_path))
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.spec_provider == "JSONSkeletonSpecProvider"

    def test_valid_document_without_spec_has_no_errors(self) -> None:
        result = validate_edi(_edi())
        assert result.is_valid is None
        assert result.errors == []

    def test_envelope_errors_without_spec_land_in_errors(self) -> None:
        """Audit item 5: envelope findings are errors, not warnings."""
        result = validate_edi(_edi(se01="99"))
        assert result.is_valid is None
        assert [(e.segment_id, e.element_pos, e.error_type) for e in result.errors] == [
            ("SE", 1, "ENVELOPE_ERROR")
        ]
        assert not any("SE01" in w for w in result.warnings)
        assert any("No spec_provider supplied" in w for w in result.warnings)

    def test_envelope_errors_when_provider_has_no_spec(self) -> None:
        """Audit item 4: envelope checks run even when no spec matches."""
        result = validate_edi(_edi(se02="0002"), spec_provider=MinimalProvider())
        assert result.is_valid is None
        assert [e.message for e in result.errors] == [
            "SE02 control number '0002' does not match ST02 '0001'"
        ]
        assert any("No spec found" in w for w in result.warnings)

    def test_each_trailer_mismatch_reported(self, tmp_path: Path) -> None:
        provider = _provider(tmp_path)
        cases = {
            "SE01 reports 7 segments but actual count is 6": {"se01": "7"},
            "SE02 control number '0002' does not match ST02 '0001'": {"se02": "0002"},
            "GE01 reports 2 transaction sets but actual count is 1": {"ge01": "2"},
            "GE02 control number '2' does not match GS06 '1'": {"ge02": "2"},
            "IEA01 reports 2 functional groups but actual count is 1": {"iea01": "2"},
            "IEA02 control number '000000002' does not match ISA13 '000000001'": {
                "iea02": "000000002"
            },
        }
        for message, overrides in cases.items():
            result = validate_edi(_edi(**overrides), spec_provider=provider)
            assert result.is_valid is False, message
            assert [(e.error_type, e.message) for e in result.errors] == [
                ("ENVELOPE_ERROR", message)
            ]

    def test_group_control_number_compared_by_value(self) -> None:
        """GS06/GE02 are numeric (N0): '1' and '000000001' agree."""
        assert validate_edi(_edi(ge02="000000001")).errors == []

    def test_missing_trailers_reported(self) -> None:
        text = _edi().split("SE*")[0]
        result = validate_edi(text)
        assert [e.message for e in result.errors] == [
            "IEA segment is missing for ISA13 '000000001'",
            "GE segment is missing for GS06 '1'",
            "SE segment is missing for ST02 '0001'",
        ]

    def test_only_first_interchange_trailers_used(self) -> None:
        second = _edi(ge02="7", iea02="000000009")
        assert validate_edi(_edi() + second).errors == []

    def test_iea_of_second_interchange_not_taken_for_first(self) -> None:
        first = _edi().replace("IEA*1*000000001~", "")
        result = validate_edi(first + _edi())
        assert [e.message for e in result.errors] == [
            "IEA segment is missing for ISA13 '000000001'"
        ]

    def test_ge_of_second_group_not_taken_for_first(self) -> None:
        text = _edi().replace("GE*1*1~", "GS*PO*S*R*20260222*1200*2*X*005010~GE*0*2~")
        result = validate_edi(text)
        assert "GE segment is missing for GS06 '1'" in [e.message for e in result.errors]

    def test_no_groups_still_checks_interchange(self) -> None:
        result = validate_edi(_ISA + "IEA*1*000000001~")
        assert result.is_valid is None
        assert [e.message for e in result.errors] == [
            "IEA01 reports 1 functional groups but actual count is 0"
        ]
        assert "No functional groups found. Structural checks only." in result.warnings

    def test_no_transactions_still_checks_group(self) -> None:
        text = _ISA + "GS*PO*S*R*20260222*1200*1*X*005010~GE*1*1~IEA*1*000000001~"
        result = validate_edi(text)
        assert result.is_valid is None
        assert [e.message for e in result.errors] == [
            "GE01 reports 1 transaction sets but actual count is 0"
        ]
        assert "No transactions found. Structural checks only." in result.warnings


class TestValidateEdiElements:
    def test_missing_mandatory_element(self, tmp_path: Path) -> None:
        """Audit item 2: BEG02 omitted is reported."""
        body = ["BEG*00"] + _PO_BODY[1:]
        result = validate_edi(_edi(body), spec_provider=_provider(tmp_path))
        assert result.is_valid is False
        assert [(e.segment_id, e.element_pos, e.error_type) for e in result.errors] == [
            ("BEG", 2, "MISSING_MANDATORY"),
            ("BEG", 5, "MISSING_MANDATORY"),
        ]

    def test_repetition_does_not_shift_element_positions(self, tmp_path: Path) -> None:
        """element_pos comes from the parser, not from counting repetitions."""
        body = ["BEG*00^01*NE*PO-1**20260222"] + _PO_BODY[1:]
        result = validate_edi(_edi(body), spec_provider=_provider(tmp_path))
        assert result.is_valid is True, result.errors

    def test_non_ascii_date_is_type_error(self, tmp_path: Path) -> None:
        """A '²' date is a TYPE_ERROR finding, not a SPEC_ERROR from a ValueError."""
        body = ["BEG*00*NE*PO-1**\u00b2\u00b2\u00b2\u00b20101"] + _PO_BODY[1:]
        result = validate_edi(_edi(body), spec_provider=_provider(tmp_path))
        assert result.is_valid is False
        assert [(e.segment_id, e.element_pos, e.error_type) for e in result.errors] == [
            ("BEG", 5, "TYPE_ERROR")
        ]

    def test_max_use_exceeded_is_error(self, tmp_path: Path) -> None:
        body = _PO_BODY + ["CTT*2"]
        result = validate_edi(_edi(body), spec_provider=_provider(tmp_path))
        assert result.is_valid is False
        assert result.warnings == []
        assert [(e.error_type, e.message) for e in result.errors] == [
            ("MAX_USE_EXCEEDED", "Segment CTT appears 2 time(s) but max use is 1")
        ]


class TestValidateEdiNeverRaises:
    def test_bytes_input_matches_str_input(self, tmp_path: Path) -> None:
        provider = _provider(tmp_path)
        from_bytes = validate_edi(_edi().encode(), spec_provider=provider)
        assert from_bytes == validate_edi(_edi(), spec_provider=provider)
        assert from_bytes.is_valid is True

    def test_bytes_decoded_like_parse_edi_file(self) -> None:
        """Invalid UTF-8 is replaced, not rejected, exactly as parse_edi_file does."""
        raw = _edi(_PO_BODY[:1] + ["PO1*1*10*EA*2.5**BP*\xff"] + _PO_BODY[2:]).encode("latin-1")
        result = validate_edi(raw)
        assert result.errors == []

    def test_non_text_input_is_parse_error(self) -> None:
        result = validate_edi(None)  # type: ignore[arg-type]
        assert result.is_valid is False
        assert [e.error_type for e in result.errors] == ["PARSE_ERROR"]

    def test_malformed_skeleton_is_spec_error(self, tmp_path: Path) -> None:
        result = validate_edi(_edi(), spec_provider=_provider(tmp_path, raw="{not json"))
        assert result.is_valid is None
        assert [e.error_type for e in result.errors] == ["SPEC_ERROR"]
        assert result.errors[0].message.startswith(
            "Spec provider JSONSkeletonSpecProvider failed: JSONDecodeError:"
        )
        assert result.spec_provider == "JSONSkeletonSpecProvider"

    def test_skeleton_missing_keys_is_spec_error(self, tmp_path: Path) -> None:
        result = validate_edi(_edi(), spec_provider=_provider(tmp_path, {"segments": {}}))
        assert [e.error_type for e in result.errors] == ["SPEC_ERROR"]

    def test_raising_provider_keeps_envelope_findings(self) -> None:
        result = validate_edi(_edi(se01="99"), spec_provider=_RaisingProvider())
        assert result.is_valid is None
        assert [e.error_type for e in result.errors] == ["ENVELOPE_ERROR", "SPEC_ERROR"]
        assert result.errors[1].message == (
            "Spec provider _RaisingProvider failed: RuntimeError: backend down"
        )

    def test_gs08_path_traversal_finds_no_spec(self, tmp_path: Path) -> None:
        """Audit item 6: GS08 '../x' must not load a skeleton outside specs_dir."""
        from draftedi.spec.json_skeleton_provider import JSONSkeletonSpecProvider

        specs = tmp_path / "specs"
        specs.mkdir()
        (tmp_path / "x-850.json").write_text(json.dumps(_SKELETON_850), encoding="utf-8")
        result = validate_edi(_edi(version="../x"), spec_provider=JSONSkeletonSpecProvider(specs))
        assert result.is_valid is None
        assert any("No spec found for version='../x'" in w for w in result.warnings)
