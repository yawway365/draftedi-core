"""Tests for X12Validator, ValidationResult, and ValidationError.

MinimalProvider implements X12SpecProvider via structural subtyping to verify
duck-typing compliance without importing the Protocol class. (ref: DL-004)
"""

from __future__ import annotations

from typing import Optional

from draftedi.validator.core import ValidationError, ValidationResult, X12Validator
from draftedi.spec.protocol import TransactionSetSpec, SegmentSpec, ElementSpec


# ---------------------------------------------------------------------------
# Minimal spec provider for testing
# ---------------------------------------------------------------------------


class MinimalProvider:
    """Structural subtype of X12SpecProvider returning None for all specs."""

    def get_transaction_set(self, version: str, ts_id: str) -> Optional[TransactionSetSpec]:
        return None

    def get_element_codes(self, version: str, element_id: str) -> list[str]:
        return []

    def get_segment_spec(self, version: str, segment_id: str) -> Optional[SegmentSpec]:
        return None

    def get_available_versions(self) -> list[str]:
        return []


def _make_element_spec(
    element_id: str,
    sequence: int,
    data_type: str = "AN",
    min_length: int = 1,
    max_length: int = 80,
    requirement: str = "O",
    repetition_count: int = 1,
) -> ElementSpec:
    return ElementSpec(
        element_id=element_id,
        element_name=None,
        data_type=data_type,
        min_length=min_length,
        max_length=max_length,
        requirement=requirement,
        sequence=sequence,
        repetition_count=repetition_count,
    )


def _make_segment_spec(
    segment_id: str,
    requirement: str = "O",
    max_use: int = 1,
    loop_id: Optional[str] = None,
    loop_level: int = 0,
    elements: Optional[list[ElementSpec]] = None,
) -> SegmentSpec:
    return SegmentSpec(
        segment_id=segment_id,
        segment_name=None,
        requirement=requirement,
        max_use=max_use,
        loop_id=loop_id,
        loop_level=loop_level,
        loop_repeat=1,
        sequence=0,
        area="HEADING",
        elements=elements or [],
        relational_conditions=[],
    )


def _make_transaction_set_spec(segments: list[SegmentSpec]) -> TransactionSetSpec:
    return TransactionSetSpec(
        transaction_set_id="850",
        transaction_set_name=None,
        functional_group_id="PO",
        segments=segments,
    )


# ---------------------------------------------------------------------------
# TestValidationErrorDataclass
# ---------------------------------------------------------------------------


class TestValidationErrorDataclass:
    def test_five_fields_present(self):
        err = ValidationError(
            segment_id="BEG",
            element_pos=1,
            error_type="MISSING_MANDATORY",
            value=None,
            message="Mandatory segment BEG is missing",
        )
        assert err.segment_id == "BEG"
        assert err.element_pos == 1
        assert err.error_type == "MISSING_MANDATORY"
        assert err.value is None
        assert err.message == "Mandatory segment BEG is missing"

    def test_optional_fields_accept_none(self):
        err = ValidationError(
            segment_id="SE",
            element_pos=None,
            error_type="TYPE_ERROR",
            value=None,
            message="test",
        )
        assert err.element_pos is None
        assert err.value is None


# ---------------------------------------------------------------------------
# TestValidationResultDataclass
# ---------------------------------------------------------------------------


class TestValidationResultDataclass:
    def test_is_valid_none_for_indeterminate(self):
        result = ValidationResult(is_valid=None)
        assert result.is_valid is None

    def test_defaults_empty_lists(self):
        result = ValidationResult(is_valid=True)
        assert result.errors == []
        assert result.warnings == []
        assert result.spec_provider is None

    def test_is_valid_true_false(self):
        assert ValidationResult(is_valid=True).is_valid is True
        assert ValidationResult(is_valid=False).is_valid is False


# ---------------------------------------------------------------------------
# TestX12Validator
# ---------------------------------------------------------------------------


class TestX12Validator:
    def test_spec_absent_returns_is_valid_none(self):
        validator = X12Validator(MinimalProvider())
        result = validator.validate_transaction(
            {"transaction_set_id": "850", "segments": [], "segment_count_reported": None},
            "005010",
        )
        assert result.is_valid is None
        assert len(result.warnings) > 0
        assert result.spec_provider == "MinimalProvider"

    def test_spec_absent_warning_contains_version_and_ts(self):
        validator = X12Validator(MinimalProvider())
        result = validator.validate_transaction(
            {"transaction_set_id": "850", "segments": [], "segment_count_reported": None},
            "005010",
        )
        assert any("005010" in w for w in result.warnings)
        assert any("850" in w for w in result.warnings)

    def test_valid_transaction_with_spec(self):
        class SpecProvider:
            def get_transaction_set(self, version: str, ts_id: str) -> Optional[TransactionSetSpec]:
                return _make_transaction_set_spec(
                    [
                        _make_segment_spec("BEG", requirement="M"),
                    ]
                )

            def get_element_codes(self, version: str, element_id: str) -> list[str]:
                return []

            def get_segment_spec(self, version: str, segment_id: str) -> Optional[SegmentSpec]:
                return None

            def get_available_versions(self) -> list[str]:
                return ["005010"]

        validator = X12Validator(SpecProvider())
        result = validator.validate_transaction(
            {
                "transaction_set_id": "850",
                "segment_count_reported": None,
                "segments": [
                    {"segment_id": "BEG", "elements": []},
                ],
            },
            "005010",
        )
        assert result.is_valid is True
        assert result.errors == []

    def test_missing_mandatory_segment_produces_error(self):
        class SpecProvider:
            def get_transaction_set(self, version: str, ts_id: str) -> Optional[TransactionSetSpec]:
                return _make_transaction_set_spec(
                    [
                        _make_segment_spec("BEG", requirement="M"),
                    ]
                )

            def get_element_codes(self, version: str, element_id: str) -> list[str]:
                return []

            def get_segment_spec(self, version: str, segment_id: str) -> Optional[SegmentSpec]:
                return None

            def get_available_versions(self) -> list[str]:
                return ["005010"]

        validator = X12Validator(SpecProvider())
        result = validator.validate_transaction(
            {
                "transaction_set_id": "850",
                "segment_count_reported": None,
                "segments": [],
            },
            "005010",
        )
        assert result.is_valid is False
        assert any(e.error_type == "MISSING_MANDATORY" for e in result.errors)

    def test_from_draftedi_validator_import(self):
        from draftedi.validator import X12Validator, ValidationResult, ValidationError

        assert X12Validator
        assert ValidationResult
        assert ValidationError
