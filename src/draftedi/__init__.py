"""draftedi — X12 EDI parser and validator.

Provides pure-Python X12 EDI parsing (``parse_edi_file``,
``parse_interchange``) and database-free validation functions
(``check_element_data_type``, ``check_envelope``, etc.).

All public names are listed in ``__all__``.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _dist_version
from typing import Any, Optional, Union

# The version lives only in pyproject.toml; read it from the installed metadata.
try:
    __version__ = _dist_version("draftedi")
except PackageNotFoundError:  # pragma: no cover - source tree that was never installed
    __version__ = "0.0.0+unknown"

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

# Private helpers shared with validate_edi(); not part of __all__.
from draftedi.validate import _check_trailer
from draftedi.validator.core import _route_issues


def _first_trailers(x12_text: str) -> tuple[Optional[list[str]], Optional[list[str]]]:
    """Return the elements of the GE and IEA closing the first group and interchange.

    parse_edi_file() does not keep GE or IEA, so they are re-read here with the
    separators declared by the first ISA. Either value is None when that trailer
    is missing: the text ends, or another GS (for GE) or ISA comes first.
    """
    sep = parse_interchange(x12_text)
    ge: Optional[list[str]] = None
    groups_seen = 0
    # Chunk 0 is the first ISA itself; another ISA starts the next interchange.
    for raw_segment in x12_text.split(sep["segment_term"])[1:]:
        parts = raw_segment.strip().split(sep["element_sep"])
        seg_id = parts[0].strip()
        if seg_id == "ISA":
            break
        if seg_id == "GS":
            groups_seen += 1
        elif seg_id == "GE" and groups_seen == 1 and ge is None:
            ge = parts[1:]
        elif seg_id == "IEA":
            return ge, parts[1:]
    return ge, None


def validate_edi(
    edi_text: Union[str, bytes],
    spec_provider: Optional[X12SpecProvider] = None,
) -> ValidationResult:
    """Validate an X12 EDI document.

    edi_text may be str or bytes; bytes are decoded as parse_edi_file() decodes
    them (UTF-8 with errors='replace').

    Envelope checks always run: IEA01/IEA02 against the groups and ISA13, GE01/GE02
    against the transaction sets and GS06, SE01/SE02 against the segments and ST02.
    Their findings are errors. Without spec_provider, or when it has no spec for
    the version/transaction set, is_valid is None. With a spec: full validation
    via X12Validator.validate_transaction(). (ref: DL-003)

    Never raises for any input: a parse failure returns is_valid=False with a
    PARSE_ERROR, a spec provider that raises (e.g. on a malformed skeleton file)
    returns is_valid=None with a SPEC_ERROR, and any other unexpected failure
    returns is_valid=None with an INTERNAL_ERROR after the findings made so far.

    Processes only the first interchange, functional group, and transaction set found
    in edi_text. Multi-interchange documents: call validate_edi() per interchange.
    """
    try:
        raw = edi_text if isinstance(edi_text, bytes) else edi_text.encode()
        parsed = parse_edi_file(raw)
        ge, iea = _first_trailers(raw.decode("utf-8", errors="replace"))
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

    errors: list[ValidationError] = []
    warnings: list[str] = []
    try:
        return _validate_parsed(parsed, ge, iea, spec_provider, errors, warnings)
    except Exception as exc:
        # Backstop for the never-raises contract: a failure in draftedi's own
        # checks becomes a finding, keeping what was found before it.
        errors.append(
            ValidationError(
                segment_id="",
                element_pos=None,
                error_type="INTERNAL_ERROR",
                value=None,
                message=f"Validation failed: {type(exc).__name__}: {exc}",
            )
        )
        return ValidationResult(
            is_valid=None,
            errors=errors,
            warnings=warnings,
            spec_provider=None if spec_provider is None else type(spec_provider).__name__,
        )


def _validate_parsed(
    parsed: ParsedFile,
    ge: Optional[list[str]],
    iea: Optional[list[str]],
    spec_provider: Optional[X12SpecProvider],
    errors: list[ValidationError],
    warnings: list[str],
) -> ValidationResult:
    """validate_edi() after a successful parse.

    Appends to the caller's errors and warnings lists, so the caller still has
    the findings gathered so far if a check raises unexpectedly.
    """
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
    _route_issues(
        _check_trailer(
            "IEA",
            iea,
            len(interchange["groups"]),
            "functional groups",
            "ISA13",
            interchange["isa_control_number"],
            numeric_control=True,
        ),
        errors,
        warnings,
    )
    if not interchange["groups"]:
        warnings.append("No functional groups found. Structural checks only.")
        return ValidationResult(is_valid=None, errors=errors, warnings=warnings)

    group = interchange["groups"][0]
    _route_issues(
        _check_trailer(
            "GE",
            ge,
            len(group["transactions"]),
            "transaction sets",
            "GS06",
            group["group_control_number"],
            numeric_control=True,
        ),
        errors,
        warnings,
    )
    if not group["transactions"]:
        warnings.append("No transactions found. Structural checks only.")
        return ValidationResult(is_valid=None, errors=errors, warnings=warnings)

    transaction = group["transactions"][0]
    version: str = group["x12_release"] or ""
    # Parser segments are passed through unchanged: element_pos must come from
    # the parser, since repeated elements yield one entry per repetition.
    parsed_tx_dict: dict[str, Any] = {
        "transaction_set_id": transaction["transaction_set_id"],
        "control_number": transaction["control_number"],
        "segment_count_reported": transaction["segment_count_reported"],
        "raw_se_segment": transaction["raw_se_segment"],
        "segments": transaction["segments"],
    }

    if spec_provider is None:
        _route_issues(check_envelope(parsed_tx_dict, transaction["segments"]), errors, warnings)
        warnings.append(
            "No spec_provider supplied. Structural checks only. "
            "Supply an X12SpecProvider for full validation."
        )
        return ValidationResult(is_valid=None, errors=errors, warnings=warnings)

    provider_name = type(spec_provider).__name__
    try:
        result = X12Validator(spec_provider).validate_transaction(parsed_tx_dict, version)
    except Exception as exc:
        # The provider is user code or user-supplied files (e.g. a malformed
        # skeleton): report its failure, keeping the spec-free envelope findings.
        _route_issues(check_envelope(parsed_tx_dict, transaction["segments"]), errors, warnings)
        errors.append(
            ValidationError(
                segment_id="",
                element_pos=None,
                error_type="SPEC_ERROR",
                value=None,
                message=f"Spec provider {provider_name} failed: {type(exc).__name__}: {exc}",
            )
        )
        return ValidationResult(
            is_valid=None, errors=errors, warnings=warnings, spec_provider=provider_name
        )

    errors += result.errors
    warnings += result.warnings
    return ValidationResult(
        is_valid=None if result.is_valid is None else not errors,
        errors=errors,
        warnings=warnings,
        spec_provider=result.spec_provider,
    )


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
