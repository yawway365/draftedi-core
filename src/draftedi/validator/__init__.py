"""draftedi.validator — X12 validation class and result types.

Public surface: X12Validator (validation executor), ValidationResult (outcome),
ValidationError (per-segment/element issue). All check logic delegates to
validate.py; this package provides the class interface only. (ref: DL-001)
"""

from __future__ import annotations

from draftedi.validator.core import X12Validator, ValidationResult, ValidationError

__all__ = ["X12Validator", "ValidationResult", "ValidationError"]
