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
from draftedi.spec.protocol import ElementSpec, TransactionSetSpec, SegmentSpec


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


class RefSpecProvider(MinimalProvider):
    """Provider whose 850 spec has one REF segment with a numeric REF03."""

    def get_transaction_set(self, version: str, ts_id: str) -> Optional[TransactionSetSpec]:
        elements: list[ElementSpec] = [
            ElementSpec(
                element_id=f"E{seq}",
                element_name=None,
                data_type=data_type,
                min_length=1,
                max_length=30,
                requirement="O",
                sequence=seq,
                repetition_count=1,
            )
            for seq, data_type in [(1, "AN"), (2, "AN"), (3, "N0")]
        ]
        ref = SegmentSpec(
            segment_id="REF",
            segment_name=None,
            requirement="O",
            max_use=0,
            loop_id=None,
            loop_level=0,
            loop_repeat=0,
            sequence=1,
            area="HEADING",
            elements=elements,
            relational_conditions=[],
        )
        return TransactionSetSpec(
            transaction_set_id="850",
            transaction_set_name=None,
            functional_group_id="PO",
            segments=[ref],
        )


class TestValidateEdiRepetitions:
    def test_repeated_element_keeps_its_position(self) -> None:
        """REF02 repetitions must not shift REF03 to a later position."""
        txn = "ST*850*0001~REF*PO*A^B*12~SE*3*0001~"
        edi = SampleX12.build_interchange(groups=[SampleX12.build_group(transactions=[txn])])
        result = validate_edi(edi, spec_provider=RefSpecProvider())
        assert result.errors == []
        assert result.is_valid is True
