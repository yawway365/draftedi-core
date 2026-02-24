from __future__ import annotations
from typing import Protocol, TypedDict, Optional


class ElementSpec(TypedDict):
    element_id: str
    element_name: Optional[
        str
    ]  # None when spec DB omitted; BYOS (Bring Your Own Spec) model keeps OSS wheel copyright-clean (ref: DL-003)
    data_type: str  # "AN", "ID", "DT", "TM", "R", "N0" per X12 data type table
    min_length: int
    max_length: int
    requirement: str  # "M"=mandatory, "O"=optional, "C"=conditional, "X"=excluded
    sequence: (
        int  # 1-based position within parent segment; frozen public API from v1.2.0 (ref: DL-003)
    )
    repetition_count: int


class RelationalCondition(TypedDict):
    condition_type: str  # "P"=paired, "R"=required, "E"=exclusive, "C"=conditional, "L"=list
    element_positions: list[int]  # 1-based positions of elements subject to the relational rule


class SegmentSpec(TypedDict):
    segment_id: str
    segment_name: Optional[str]  # None when spec DB omitted; BYOS model (ref: DL-003)
    requirement: str  # "M"=mandatory, "O"=optional within parent loop
    max_use: int  # Maximum repetitions; 0 means unbounded ('>1' in X12 spec)
    loop_id: Optional[str]  # Loop identifier; None for segments outside any loop
    loop_level: int  # Nesting depth; 0 for top-level segments
    loop_repeat: (
        int  # Maximum loop repetitions; used by Phase 3 transformer for hierarchy reconstruction
    )
    sequence: int  # Position within the transaction set; used by Phase 3 transformer to reconstruct validate.py's hierarchical loop format
    area: str  # "HEADING", "DETAIL", or "SUMMARY" per X12 section
    elements: list[ElementSpec]
    relational_conditions: list[RelationalCondition]


class TransactionSetSpec(TypedDict):
    transaction_set_id: str
    transaction_set_name: Optional[str]
    functional_group_id: str
    segments: list[SegmentSpec]


class X12SpecProvider(Protocol):
    """
    Abstract source of X12 specification data.

    Note: get_element_codes() returns [] for both "no codes defined" AND
    "unknown version/element". These cases cannot be distinguished from the
    return value -- callers must not infer version support from an empty list.

    STABILITY: This Protocol method signatures and all TypedDict field names
    are frozen from v1.2.0. Any change is a semver major bump (v2.0.0).
    The private repo pins draftedi>=1.2.0,<2.0.0 against this contract.

    # TODO(v1.3.0): Add validate_provider() debug helper that calls each method
    # with sentinel values and checks return types for runtime conformance.
    """

    def get_transaction_set(
        self, version: str, transaction_set_id: str
    ) -> Optional[TransactionSetSpec]: ...

    def get_element_codes(self, version: str, element_id: str) -> list[str]: ...

    def get_segment_spec(self, version: str, segment_id: str) -> Optional[SegmentSpec]: ...

    def get_available_versions(self) -> list[str]: ...
