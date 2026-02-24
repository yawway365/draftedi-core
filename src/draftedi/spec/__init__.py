"""Public surface of the draftedi.spec subpackage.

Exports all Protocol and TypedDict symbols for provider implementors.
X12SpecProvider and MissingSpecError are re-exported at draftedi top-level
for consumer imports; TypedDicts remain at draftedi.spec only. (ref: DL-004)
JSONSkeletonSpecProvider is exported here and at draftedi top-level as the
built-in BYOS spec provider; users may also implement X12SpecProvider directly.
"""

from __future__ import annotations

from draftedi.spec.protocol import (
    X12SpecProvider,
    TransactionSetSpec,
    SegmentSpec,
    ElementSpec,
    RelationalCondition,
)
from draftedi.spec.exceptions import MissingSpecError
from draftedi.spec.json_skeleton_provider import JSONSkeletonSpecProvider

__all__ = [
    "X12SpecProvider",
    "TransactionSetSpec",
    "SegmentSpec",
    "ElementSpec",
    "RelationalCondition",
    "MissingSpecError",
    "JSONSkeletonSpecProvider",
]
