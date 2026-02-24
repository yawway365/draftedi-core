"""Smoke tests for draftedi.spec -- Protocol, TypedDicts, and exceptions.

test_protocol_duck_typing_conformance verifies structural subtyping at runtime
behavior only; type correctness is enforced by mypy, not isinstance(). (ref: DL-001, DL-002)
"""


def test_imports_from_spec_package():
    """All public symbols importable from draftedi.spec."""
    from draftedi.spec import (
        X12SpecProvider,
        ElementSpec,
        RelationalCondition,
        SegmentSpec,
        TransactionSetSpec,
        MissingSpecError,
    )
    assert all([X12SpecProvider, ElementSpec, RelationalCondition,
                SegmentSpec, TransactionSetSpec, MissingSpecError])


def test_imports_from_top_level():
    """X12SpecProvider and MissingSpecError importable from draftedi top-level."""
    from draftedi import X12SpecProvider, MissingSpecError
    assert X12SpecProvider
    assert MissingSpecError


def test_missing_spec_error_is_value_error():
    """MissingSpecError is a ValueError subclass."""
    from draftedi.spec import MissingSpecError
    err = MissingSpecError("test message")
    assert isinstance(err, ValueError)
    assert str(err) == "test message"


def test_protocol_duck_typing_conformance():
    """A class implementing all 4 methods satisfies X12SpecProvider structurally."""
    from typing import Optional
    from draftedi.spec import TransactionSetSpec, SegmentSpec

    class MinimalProvider:
        def get_transaction_set(self, version: str, ts_id: str) -> Optional[TransactionSetSpec]:
            return None
        def get_element_codes(self, version: str, element_id: str) -> list[str]:
            return []
        def get_segment_spec(self, version: str, segment_id: str) -> Optional[SegmentSpec]:
            return None
        def get_available_versions(self) -> list[str]:
            return []

    provider = MinimalProvider()
    assert provider.get_element_codes("005010", "143") == []
    assert provider.get_available_versions() == []
    assert provider.get_transaction_set("005010", "850") is None
