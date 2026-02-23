from __future__ import annotations

"""Shared test helpers for unit tests."""


def to_bytes(edi_string: str) -> bytes:
    """Convert an EDI string to bytes, mimicking file content."""
    return edi_string.encode("utf-8")


def make_segment(seg_id, position, loop_path=None, elements=None):
    """Build a minimal parsed segment dict for validator tests."""
    return {
        "segment_id": seg_id,
        "segment_row_id": position,
        "position": position,
        "loop_path": loop_path,
        "elements": elements or [],
    }


def make_element(pos, value_text="", is_composite=0):
    """Build a minimal parsed element dict."""
    return {
        "element_pos": pos,
        "value_text": value_text,
        "is_composite": is_composite,
        "components": [],
    }


def make_spec_segment(seg_id, requirement="O", max_use=None, elements=None, rc=None):
    """Build a minimal spec segment entry."""
    entry = {
        "segment_id": seg_id,
        "segment_requirement": requirement,
        "segment_elements": elements or [],
        "segment_relational_conditions": rc or [],
    }
    if max_use is not None:
        entry["segment_maximum_use"] = max_use
    return entry


def make_spec_element(
    sequence,
    requirement="O",
    element_type="AN",
    element_id="E100",
    min_length=1,
    max_length=99,
    code_count=0,
):
    """Build a minimal spec element entry."""
    return {
        "segment_element_sequence": str(sequence),
        "segment_element_requirement": requirement,
        "element_type": element_type,
        "element_id": element_id,
        "element_min_length": min_length,
        "element_max_length": max_length,
        "element_code_count": code_count,
    }
