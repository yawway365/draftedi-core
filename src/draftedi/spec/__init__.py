"""Public surface of the draftedi.spec subpackage.

Exports all Protocol and TypedDict symbols for provider implementors.
X12SpecProvider and MissingSpecError are re-exported at draftedi top-level
for consumer imports; TypedDicts remain at draftedi.spec only. (ref: DL-004)
"""

from draftedi.spec.protocol import (
    X12SpecProvider,
    TransactionSetSpec,
    SegmentSpec,
    ElementSpec,
    RelationalCondition,
)
from draftedi.spec.exceptions import MissingSpecError

__all__ = [
    "X12SpecProvider",
    "TransactionSetSpec",
    "SegmentSpec",
    "ElementSpec",
    "RelationalCondition",
    "MissingSpecError",
]
