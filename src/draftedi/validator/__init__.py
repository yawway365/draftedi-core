"""draftedi.validator — X12 validation class and result types.

Public surface: X12Validator (validation executor), ValidationResult (outcome),
ValidationError (per-segment/element issue). Most check logic lives in
validate.py; this package provides the class interface and the
mandatory-element check.
"""

from __future__ import annotations

from draftedi.validator.core import X12Validator, ValidationResult, ValidationError

__all__ = ["X12Validator", "ValidationResult", "ValidationError"]
