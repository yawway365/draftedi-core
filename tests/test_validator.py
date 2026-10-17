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


# ---------------------------------------------------------------------------
# Spec-driven providers and parsed transactions for the 1.3.1 fixes
# ---------------------------------------------------------------------------


class _SpecProvider:
    """Structural subtype of X12SpecProvider serving one fixed spec and code list."""

    def __init__(
        self, segments: list[SegmentSpec], codes: Optional[dict[str, list[str]]] = None
    ) -> None:
        self._spec = _make_transaction_set_spec(segments)
        self._codes = codes or {}

    def get_transaction_set(self, version: str, ts_id: str) -> Optional[TransactionSetSpec]:
        return self._spec

    def get_element_codes(self, version: str, element_id: str) -> list[str]:
        return self._codes.get(element_id, [])

    def get_segment_spec(self, version: str, segment_id: str) -> Optional[SegmentSpec]:
        return None

    def get_available_versions(self) -> list[str]:
        return ["005010"]


def _seg(segment_id: str, *values: str) -> dict:
    return {
        "segment_id": segment_id,
        "elements": [{"element_pos": i, "value_text": v} for i, v in enumerate(values, start=1)],
    }


def _tx(*segments: dict) -> dict:
    return {"transaction_set_id": "850", "segment_count_reported": None, "segments": list(segments)}


def _po1_loop_spec() -> list[SegmentSpec]:
    # Real X12 850: PO1 max use is 1 per iteration; the PO1 loop repeats.
    return [
        _make_segment_spec("BEG", requirement="M"),
        _make_segment_spec("PO1", requirement="M", max_use=1, loop_id="PO1", loop_level=1),
        _make_segment_spec("PID", max_use=1, loop_id="PO1", loop_level=1),
        _make_segment_spec("CTT", max_use=1),
    ]


class TestX12ValidatorMaxUsePerIteration:
    def test_two_po1_iterations_valid(self):
        result = X12Validator(_SpecProvider(_po1_loop_spec())).validate_transaction(
            _tx(_seg("BEG"), _seg("PO1"), _seg("PID"), _seg("PO1"), _seg("PID"), _seg("CTT")),
            "005010",
        )
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_excess_within_iteration_is_error(self):
        """Max-use issues are errors (X12 997 AK3 code 5) and make is_valid False."""
        result = X12Validator(_SpecProvider(_po1_loop_spec())).validate_transaction(
            _tx(_seg("BEG"), _seg("PO1"), _seg("PID"), _seg("PID")), "005010"
        )
        assert result.is_valid is False
        assert result.warnings == []
        assert [(e.segment_id, e.error_type, e.message) for e in result.errors] == [
            (
                "PID",
                "MAX_USE_EXCEEDED",
                "Segment PID appears 2 time(s) but max use is 1 in loop PO1",
            )
        ]


class TestX12ValidatorEnvelope:
    def test_envelope_checked_without_spec(self):
        """A missing spec no longer skips the envelope check (audit item 4)."""
        result = X12Validator(MinimalProvider()).validate_transaction(
            {"transaction_set_id": "850", "segment_count_reported": 9, "segments": []},
            "005010",
        )
        assert result.is_valid is None
        assert [e.error_type for e in result.errors] == ["ENVELOPE_ERROR"]
        assert result.errors[0].message == "SE01 reports 9 segments but actual count is 2"
        assert any("No spec" in w for w in result.warnings)

    def test_parser_transaction_control_number_checked(self):
        """A Transaction from parse_edi_file() has its SE02 checked against ST02."""
        from draftedi import parse_edi_file
        from factories import SampleX12

        text = SampleX12.build_interchange().replace("SE*5*0001", "SE*5*0002")
        parsed = parse_edi_file(text.encode())
        tx = parsed["interchanges"][0]["groups"][0]["transactions"][0]
        result = X12Validator(_SpecProvider([])).validate_transaction(dict(tx), "005010")
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].segment_id == "SE"
        assert result.errors[0].element_pos == 2
        assert result.errors[0].error_type == "ENVELOPE_ERROR"


class TestX12ValidatorMandatoryElements:
    @staticmethod
    def _provider() -> _SpecProvider:
        return _SpecProvider(
            [
                _make_segment_spec(
                    "BEG",
                    elements=[
                        _make_element_spec("353", 1, requirement="M"),
                        _make_element_spec("92", 2, requirement="M"),
                        _make_element_spec("324", 3, requirement="O"),
                    ],
                )
            ]
        )

    def test_trailing_mandatory_element_omitted(self):
        result = X12Validator(self._provider()).validate_transaction(
            _tx(_seg("BEG", "00")), "005010"
        )
        assert result.is_valid is False
        assert len(result.errors) == 1
        err = result.errors[0]
        assert (err.segment_id, err.element_pos, err.error_type) == ("BEG", 2, "MISSING_MANDATORY")
        assert err.value is None
        assert err.message == "Mandatory element BEG02 (92) is missing"

    def test_empty_mandatory_element(self):
        result = X12Validator(self._provider()).validate_transaction(
            _tx(_seg("BEG", "", "NE", "PO-1")), "005010"
        )
        assert [(e.element_pos, e.error_type) for e in result.errors] == [(1, "MISSING_MANDATORY")]

    def test_optional_element_may_be_omitted(self):
        result = X12Validator(self._provider()).validate_transaction(
            _tx(_seg("BEG", "00", "NE")), "005010"
        )
        assert result.is_valid is True

    def test_composite_with_components_is_present(self):
        """Composites have value_text None; any non-empty component counts as present."""
        composite = {
            "element_pos": 2,
            "value_text": None,
            "is_composite": 1,
            "components": [{"component_pos": 1, "value_text": "NE"}],
        }
        seg = {"segment_id": "BEG", "elements": [{"element_pos": 1, "value_text": "00"}, composite]}
        result = X12Validator(self._provider()).validate_transaction(_tx(seg), "005010")
        assert result.is_valid is True

    def test_repeated_element_present_in_any_repetition(self):
        seg = {
            "segment_id": "BEG",
            "elements": [
                {"element_pos": 1, "value_text": "00"},
                {"element_pos": 2, "value_text": "NE"},
                {"element_pos": 2, "value_text": ""},
            ],
        }
        result = X12Validator(self._provider()).validate_transaction(_tx(seg), "005010")
        assert result.is_valid is True


class TestX12ValidatorElementChecks:
    """Covers the per-element type, length and code checks."""

    @staticmethod
    def _provider() -> _SpecProvider:
        return _SpecProvider(
            [
                _make_segment_spec(
                    "BEG",
                    elements=[
                        _make_element_spec("353", 1, data_type="ID", min_length=2, max_length=2),
                        _make_element_spec("373", 2, data_type="DT", min_length=8, max_length=8),
                    ],
                )
            ],
            codes={"353": ["00", "05"]},
        )

    def test_valid_values_pass(self):
        result = X12Validator(self._provider()).validate_transaction(
            _tx(_seg("BEG", "00", "20260222")), "005010"
        )
        assert result.is_valid is True

    def test_type_error(self):
        result = X12Validator(self._provider()).validate_transaction(
            _tx(_seg("BEG", "00", "20261322")), "005010"
        )
        assert [(e.element_pos, e.error_type, e.value) for e in result.errors] == [
            (2, "TYPE_ERROR", "20261322")
        ]

    def test_length_error(self):
        result = X12Validator(self._provider()).validate_transaction(
            _tx(_seg("BEG", "00", "260222")), "005010"
        )
        assert [(e.element_pos, e.error_type) for e in result.errors] == [(2, "INVALID_LENGTH")]

    def test_code_error(self):
        result = X12Validator(self._provider()).validate_transaction(
            _tx(_seg("BEG", "99", "20260222")), "005010"
        )
        assert [(e.element_pos, e.error_type, e.value) for e in result.errors] == [
            (1, "INVALID_CODE", "99")
        ]

    def test_element_without_spec_ignored(self):
        result = X12Validator(self._provider()).validate_transaction(
            _tx(_seg("BEG", "00", "20260222", "anything")), "005010"
        )
        assert result.is_valid is True


class TestX12ValidatorRelationalSeverity:
    @staticmethod
    def _provider(condition_type: str) -> _SpecProvider:
        seg = _make_segment_spec("N1")
        seg["relational_conditions"] = [
            {"condition_type": condition_type, "element_positions": [2, 3]}
        ]
        return _SpecProvider([seg])

    def test_paired_violation_is_error(self):
        result = X12Validator(self._provider("P")).validate_transaction(
            _tx(_seg("N1", "BY", "Name")), "005010"
        )
        assert result.is_valid is False
        assert [e.error_type for e in result.errors] == ["RELATIONAL_CONDITION"]

    def test_required_violation_is_error(self):
        result = X12Validator(self._provider("R")).validate_transaction(
            _tx(_seg("N1", "BY")), "005010"
        )
        assert result.is_valid is False
        assert result.warnings == []
        assert [e.error_type for e in result.errors] == ["RELATIONAL_CONDITION"]
        assert "Required condition" in result.errors[0].message

    def test_exclusion_violation_is_error(self):
        result = X12Validator(self._provider("E")).validate_transaction(
            _tx(_seg("N1", "BY", "Name", "92")), "005010"
        )
        assert result.is_valid is False
        assert [e.error_type for e in result.errors] == ["RELATIONAL_CONDITION"]

    def test_list_conditional_violation_is_error(self):
        result = X12Validator(self._provider("L")).validate_transaction(
            _tx(_seg("N1", "BY", "Name")), "005010"
        )
        assert result.is_valid is False
        assert [e.error_type for e in result.errors] == ["RELATIONAL_CONDITION"]

    def test_composite_counts_as_present(self):
        composite = {
            "element_pos": 3,
            "value_text": None,
            "is_composite": 1,
            "components": [{"component_pos": 1, "value_text": "X"}],
        }
        seg = {
            "segment_id": "N1",
            "elements": [
                {"element_pos": 1, "value_text": "BY"},
                {"element_pos": 2, "value_text": "Name"},
                composite,
            ],
        }
        result = X12Validator(self._provider("P")).validate_transaction(_tx(seg), "005010")
        assert result.is_valid is True


class TestRouteIssues:
    def test_routes_by_severity(self):
        """No built-in check emits "warning" now, but routing still honours it."""
        from draftedi.validate import make_issue
        from draftedi.validator.core import _route_issues

        errors: list[ValidationError] = []
        warnings: list[str] = []
        _route_issues(
            [
                make_issue("error", "envelope", "SE", None, 1, "count mismatch"),
                make_issue("warning", "segment_max_use", "PO1", None, None, "advisory"),
            ],
            errors,
            warnings,
        )
        assert [(e.segment_id, e.error_type, e.message) for e in errors] == [
            ("SE", "ENVELOPE_ERROR", "count mismatch")
        ]
        assert warnings == ["advisory"]
