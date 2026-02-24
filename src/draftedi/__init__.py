"""draftedi — X12 EDI parser and validator.

Provides pure-Python X12 EDI parsing (``parse_edi_file``,
``parse_interchange``) and database-free validation functions
(``check_element_data_type``, ``check_envelope``, etc.).

All public names are listed in ``__all__``.
"""

from __future__ import annotations

__version__ = "1.2.0"
from typing import Optional

from draftedi.parser import (
    parse_edi_file,
    parse_interchange,
    ParsedFile,
    Interchange,
    FunctionalGroup,
    Transaction,
    Segment,
    Element,
    Component,
    SeparatorInfo,
)

from draftedi.validate import (
    check_element_data_type,
    check_element_length,
    check_relational_conditions,
    leaf_loop,
    check_envelope,
    build_nav_tree,
    assign_loop_paths,
    build_spec_lookup,
    check_mandatory_segments,
    check_segment_max_use,
    make_issue,
    SegEntry,
    LoopEntry,
    ValidationIssue,
)

# X12SpecProvider and MissingSpecError at top-level only; TypedDicts remain at
# draftedi.spec to keep consumer imports minimal. (ref: DL-004)
from draftedi.spec.protocol import X12SpecProvider
from draftedi.spec.exceptions import MissingSpecError
# validator.core re-exported at top-level for consumer convenience. (ref: DL-006)
from draftedi.validator.core import X12Validator, ValidationResult, ValidationError


def validate_edi(
    edi_text: str,
    spec_provider: Optional[X12SpecProvider] = None,
) -> ValidationResult:
    """Validate an X12 EDI document.

    Without spec_provider: envelope structural check only; returns
    ValidationResult(is_valid=None, warnings=[...]). Never raises MissingSpecError.
    With spec_provider: full validation via X12Validator.validate_transaction().
    Handles parse failures by returning ValidationResult(is_valid=False). (ref: DL-003)

    Processes only the first interchange, functional group, and transaction set found
    in edi_text. Multi-interchange documents: call validate_edi() per interchange.
    """
    try:
        parsed = parse_edi_file(edi_text.encode())
    except Exception as exc:
        return ValidationResult(
            is_valid=False,
            errors=[
                ValidationError(
                    segment_id="",
                    element_pos=None,
                    error_type="PARSE_ERROR",
                    value=None,
                    message=f"Parse error: {exc}",
                )
            ],
        )

    if not parsed["interchanges"]:
        return ValidationResult(
            is_valid=False,
            errors=[
                ValidationError(
                    segment_id="",
                    element_pos=None,
                    error_type="PARSE_ERROR",
                    value=None,
                    message="No interchanges found in EDI text",
                )
            ],
        )

    interchange = parsed["interchanges"][0]
    if not interchange["groups"]:
        return ValidationResult(
            is_valid=None,
            warnings=["No functional groups found. Structural checks only."],
        )

    group = interchange["groups"][0]
    if not group["transactions"]:
        return ValidationResult(
            is_valid=None,
            warnings=["No transactions found. Structural checks only."],
        )

    transaction = group["transactions"][0]
    version: str = group["x12_release"] or ""

    if spec_provider is None:
        parsed_segments = transaction["segments"]
        issues = check_envelope(
            {
                "segment_count_reported": transaction["segment_count_reported"],
                "transaction_set_control_number": transaction["control_number"],
                "transaction_set_id": transaction["transaction_set_id"],
            },
            parsed_segments,
        )
        warnings = [i["message"] for i in issues]
        warnings.append(
            "No spec_provider supplied. Structural checks only. "
            "Supply an X12SpecProvider for full validation."
        )
        return ValidationResult(is_valid=None, warnings=warnings)

    validator = X12Validator(spec_provider)
    parsed_tx_dict = {
        "transaction_set_id": transaction["transaction_set_id"],
        "segment_count_reported": transaction["segment_count_reported"],
        "transaction_set_control_number": transaction["control_number"],
        "segments": [
            {
                "segment_id": seg["segment_id"],
                "elements": [
                    {
                        "element_pos": i + 1,
                        "value_text": elem["value_text"],
                    }
                    for i, elem in enumerate(seg["elements"])
                ],
            }
            for seg in transaction["segments"]
        ],
    }
    return validator.validate_transaction(parsed_tx_dict, version)


__all__ = [
    "__version__",
    "parse_edi_file",
    "parse_interchange",
    "ParsedFile",
    "Interchange",
    "FunctionalGroup",
    "Transaction",
    "Segment",
    "Element",
    "Component",
    "SeparatorInfo",
    "check_element_data_type",
    "check_element_length",
    "check_relational_conditions",
    "leaf_loop",
    "check_envelope",
    "build_nav_tree",
    "assign_loop_paths",
    "build_spec_lookup",
    "check_mandatory_segments",
    "check_segment_max_use",
    "make_issue",
    "SegEntry",
    "LoopEntry",
    "ValidationIssue",
    "X12SpecProvider",
    "MissingSpecError",
    "X12Validator",
    "ValidationResult",
    "ValidationError",
    "validate_edi",
]
