"""X12Validator class and supporting dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from draftedi.spec.protocol import X12SpecProvider, TransactionSetSpec, SegmentSpec
import draftedi.validate as _validate


@dataclass
class ValidationError:
    """Single validation issue for a segment or element.

    Maps from validate.py ValidationIssue via _issue_to_error(). error_type
    is derived from category using _CATEGORY_TO_ERROR_TYPE; value is None
    when the issue is structural (not element-value-level). (ref: DL-005)
    """

    segment_id: str
    element_pos: Optional[int]
    error_type: str
    value: Optional[str]
    message: str


@dataclass
class ValidationResult:
    """Outcome of a validation run.

    is_valid=None: spec absent or spec returned no match; envelope check only.
    is_valid=True: all checks passed with a matched spec.
    is_valid=False: one or more errors detected with a matched spec or parse failure.
    Never raises MissingSpecError; callers test is_valid is None to detect
    spec-absent results. (ref: DL-003)
    """

    is_valid: Optional[bool]
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    spec_provider: Optional[str] = None


# Maps validate.py ValidationIssue category values to ValidationError.error_type strings
_CATEGORY_TO_ERROR_TYPE: dict[str, str] = {
    "mandatory_segment": "MISSING_MANDATORY",
    "segment_max_use": "MAX_USE_EXCEEDED",
    "relational_condition": "RELATIONAL_CONDITION",
    "element_type": "TYPE_ERROR",
    "element_length": "INVALID_LENGTH",
    "element_code": "INVALID_CODE",
    "envelope": "MISSING_MANDATORY",
}


def _issue_to_error(issue: _validate.ValidationIssue) -> ValidationError:
    """Convert a validate.py ValidationIssue dict to a ValidationError dataclass.

    Looks up error_type from _CATEGORY_TO_ERROR_TYPE; falls back to TYPE_ERROR
    for unknown categories. value is always None — ValidationIssue does not carry
    the raw element value. (ref: DL-005)
    """
    error_type = _CATEGORY_TO_ERROR_TYPE.get(issue["category"], "TYPE_ERROR")
    return ValidationError(
        segment_id=issue["segment_id"] or "",
        element_pos=issue["element_pos"],
        error_type=error_type,
        value=None,
        message=issue["message"],
    )


def _spec_to_hierarchical(spec: TransactionSetSpec) -> list[dict[str, Any]]:
    """Convert a flat TransactionSetSpec.segments list to validate.py internal format.

    validate.py check functions expect a hierarchical dict list where loop segments
    are nested under {type: loop, loop_id: ..., segments: [...]} entries. This function
    reconstructs that hierarchy from the flat SegmentSpec list using loop_id/loop_level
    fields. (ref: DL-002, R-001)

    Key translations applied to each segment dict (ref: R-002):
      requirement          -> segment_requirement
      max_use              -> segment_maximum_use
      condition_type       -> transaction_set_segment_rc_type
      element_positions    -> transaction_set_segment_rc_elements (as str list)

    Loop ordering preserves first-seen order of loop_id values. Segments without
    loop_id are inserted before loops in the result list.
    """
    result: list[dict[str, Any]] = []
    loops: dict[str, dict[str, Any]] = {}
    loop_order: list[str] = []

    for seg in spec["segments"]:
        seg_dict: dict[str, Any] = {
            "segment_id": seg["segment_id"],
            "segment_requirement": seg["requirement"],
            "segment_maximum_use": seg["max_use"],
            "segment_elements": [
                {
                    "segment_element_sequence": str(e["sequence"]),
                    "segment_element_requirement": e["requirement"],
                    "element_type": e["data_type"],
                    "element_id": e["element_id"],
                    "element_min_length": e["min_length"],
                    "element_max_length": e["max_length"],
                    "element_code_count": 0,
                }
                for e in seg["elements"]
            ],
            "segment_relational_conditions": [
                {
                    "transaction_set_segment_rc_type": rc["condition_type"],
                    "transaction_set_segment_rc_elements": [
                        str(p) for p in rc["element_positions"]
                    ],
                }
                for rc in seg["relational_conditions"]
            ],
        }

        loop_id = seg["loop_id"]
        if loop_id is not None:
            if loop_id not in loops:
                loops[loop_id] = {
                    "type": "loop",
                    "loop_id": loop_id,
                    "segments": [],
                }
                loop_order.append(loop_id)
            loops[loop_id]["segments"].append(seg_dict)
        else:
            result.append(seg_dict)

    for lid in loop_order:
        result.append(loops[lid])

    return result


class X12Validator:
    """Stateless X12 transaction validator backed by an X12SpecProvider.

    Delegates all check logic to existing validate.py functions; no check
    logic is duplicated here. (ref: DL-001)

    Each _check_* method calls _spec_to_hierarchical() independently. The
    conversion overhead is acceptable at per-validate_transaction() granularity;
    caching at the method level is not done to keep the class stateless. (ref: DL-002)
    """

    def __init__(self, spec_provider: X12SpecProvider) -> None:
        self._provider = spec_provider

    def validate_transaction(
        self, parsed_transaction: dict[str, Any], version: str
    ) -> ValidationResult:
        """Validate a single parsed X12 transaction dict.

        Returns ValidationResult(is_valid=None) when no spec is found for the
        given version/ts_id pair; does not raise. Runs five check passes when
        spec is available: envelope, mandatory segments, max-use, element types,
        relational conditions. (ref: DL-001, DL-003)
        """
        ts_id: Optional[str] = parsed_transaction.get("transaction_set_id")
        spec = self._provider.get_transaction_set(version, ts_id or "")

        if spec is None:
            return ValidationResult(
                is_valid=None,
                warnings=[
                    f"No spec found for version={version!r}, ts={ts_id!r}. "
                    f"Structural checks only. "
                    f"Provider: {type(self._provider).__name__}"
                ],
                spec_provider=type(self._provider).__name__,
            )

        errors: list[ValidationError] = []
        errors += self._check_envelope(parsed_transaction)
        errors += self._check_mandatory_segments(parsed_transaction, spec)
        errors += self._check_segment_max_use(parsed_transaction, spec)
        errors += self._check_element_types(parsed_transaction, spec, version)
        errors += self._check_relational_conditions(parsed_transaction, spec)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            spec_provider=type(self._provider).__name__,
        )

    def _check_envelope(
        self, transaction: dict[str, Any]
    ) -> list[ValidationError]:
        # Delegates to validate.check_envelope. Thin delegation: X12Validator holds
        # no check logic so validate.py remains the single authoritative source for
        # all check behavior; no spec required for envelope checks. (ref: DL-001)
        parsed_segments: list[Any] = transaction.get("segments", [])
        issues = _validate.check_envelope(transaction, parsed_segments)
        return [_issue_to_error(i) for i in issues]

    def _check_mandatory_segments(
        self, transaction: dict[str, Any], spec: TransactionSetSpec
    ) -> list[ValidationError]:
        # Delegates to validate.check_mandatory_segments. Thin delegation pattern:
        # wrap-not-rewrite keeps zero regression risk on the 621 LOC check logic.
        # Spec conversion via _spec_to_hierarchical is the only logic added here.
        # (ref: DL-001, DL-002)
        hierarchical = _spec_to_hierarchical(spec)
        root = _validate.build_nav_tree(hierarchical)
        parsed_segments: list[Any] = transaction.get("segments", [])
        loop_assignments = _validate.assign_loop_paths(parsed_segments, root)
        issues = _validate.check_mandatory_segments(loop_assignments, hierarchical)
        return [_issue_to_error(i) for i in issues]

    def _check_segment_max_use(
        self, transaction: dict[str, Any], spec: TransactionSetSpec
    ) -> list[ValidationError]:
        # Delegates to validate.check_segment_max_use. Rebuilds nav tree independently
        # because stateless design avoids caching between _check_* calls. (ref: DL-001, DL-002)
        hierarchical = _spec_to_hierarchical(spec)
        root = _validate.build_nav_tree(hierarchical)
        parsed_segments: list[Any] = transaction.get("segments", [])
        loop_assignments = _validate.assign_loop_paths(parsed_segments, root)
        issues = _validate.check_segment_max_use(loop_assignments, hierarchical)
        return [_issue_to_error(i) for i in issues]

    def _check_element_types(
        self, transaction: dict[str, Any], spec: TransactionSetSpec, version: str
    ) -> list[ValidationError]:
        # Delegates per-element checks to validate.check_element_data_type and
        # check_element_length. Thin delegation: X12Validator iterates segments/elements
        # but delegates all type/length logic to validate.py functions unchanged.
        # Code validation runs only for ID-typed elements with codes. (ref: DL-001)
        errors: list[ValidationError] = []
        spec_by_id = {s["segment_id"]: s for s in spec["segments"]}
        for seg in transaction.get("segments", []):
            seg_id: str = seg.get("segment_id", "")
            seg_spec = spec_by_id.get(seg_id)
            if seg_spec is None:
                continue
            elem_specs = {e["sequence"]: e for e in seg_spec["elements"]}
            for elem in seg.get("elements", []):
                pos: int = elem.get("element_pos", 0)
                value: str = elem.get("value_text", "") or ""
                espec = elem_specs.get(pos)
                if espec is None:
                    continue
                type_err = _validate.check_element_data_type(
                    value, espec["data_type"], espec["element_id"]
                )
                if type_err:
                    errors.append(ValidationError(
                        segment_id=seg_id,
                        element_pos=pos,
                        error_type="TYPE_ERROR",
                        value=value or None,
                        message=type_err,
                    ))
                len_err = _validate.check_element_length(
                    value, espec["min_length"], espec["max_length"]
                )
                if len_err:
                    errors.append(ValidationError(
                        segment_id=seg_id,
                        element_pos=pos,
                        error_type="INVALID_LENGTH",
                        value=value or None,
                        message=len_err,
                    ))
                if espec["data_type"] == "ID" and espec.get("repetition_count", 0) > 0:
                    codes = self._provider.get_element_codes(version, espec["element_id"])
                    if codes and value and value not in codes:
                        errors.append(ValidationError(
                            segment_id=seg_id,
                            element_pos=pos,
                            error_type="INVALID_CODE",
                            value=value or None,
                            message=f"Element {espec['element_id']}: value {value!r} not in allowed codes",
                        ))
        return errors

    def _check_relational_conditions(
        self, transaction: dict[str, Any], spec: TransactionSetSpec
    ) -> list[ValidationError]:
        # Delegates to validate.check_relational_conditions. Thin delegation: only
        # added logic is translating RelationalCondition TypedDict keys to the
        # validate.py rc dict format; all condition logic stays in validate.py.
        # (ref: DL-001, R-002)
        errors: list[ValidationError] = []
        spec_by_id = {s["segment_id"]: s for s in spec["segments"]}
        for seg in transaction.get("segments", []):
            seg_id = seg.get("segment_id", "")
            seg_spec = spec_by_id.get(seg_id)
            if seg_spec is None:
                continue
            val_by_pos: dict[int, str] = {}
            for elem in seg.get("elements", []):
                pos = elem.get("element_pos", 0)
                val_by_pos[pos] = elem.get("value_text", "") or ""
            rc_list = [
                {
                    "transaction_set_segment_rc_type": rc["condition_type"],
                    "transaction_set_segment_rc_elements": [
                        str(p) for p in rc["element_positions"]
                    ],
                }
                for rc in seg_spec["relational_conditions"]
            ]
            issues = _validate.check_relational_conditions(seg_id, rc_list, val_by_pos)
            errors += [_issue_to_error(i) for i in issues]
        return errors
