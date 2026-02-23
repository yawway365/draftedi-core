"""X12 EDI validation functions.

Pure validation functions for X12 EDI documents. All functions are
database-free and depend only on Python standard library modules.

Functions are extracted from the monolith validate_x12.py with the
following changes:

- Private names (``_foo``) are promoted to public names (``foo``).
- Bug fixes applied to ``check_element_data_type`` (DT calendar-aware
  validation, N-type single-minus enforcement, TM seconds range check)
  and ``check_relational_conditions`` (Exclusion condition dedup).
- DB-coupled functions are omitted entirely.
"""

from __future__ import annotations

import calendar
import re
from typing import Any, Optional, TypedDict


# ---------------------------------------------------------------------------
# Public TypedDict
# ---------------------------------------------------------------------------


class ValidationIssue(TypedDict):
    severity: str
    category: str
    segment_id: Optional[str]
    segment_position: Optional[int]
    element_pos: Optional[int]
    message: str


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def make_issue(
    severity: str,
    category: str,
    segment_id: Optional[str],
    segment_position: Optional[int],
    element_pos: Optional[int],
    message: str,
) -> ValidationIssue:
    """Build a ``ValidationIssue`` dict.

    Public utility helper for consumers building custom validation pipelines.
    """
    return ValidationIssue(
        severity=severity,
        category=category,
        segment_id=segment_id,
        segment_position=segment_position,
        element_pos=element_pos,
        message=message,
    )


# ---------------------------------------------------------------------------
# Loop detection — navigation tree + assignment
# ---------------------------------------------------------------------------


class SegEntry:
    """A segment position within the navigation tree."""

    __slots__ = ("segment_id", "spec_dict")

    def __init__(self, segment_id: str, spec_dict: dict[str, Any]) -> None:
        self.segment_id = segment_id
        self.spec_dict = spec_dict


class LoopEntry:
    """A loop position within the navigation tree."""

    __slots__ = ("loop_id", "trigger_id", "children", "valid_seg_ids")

    def __init__(
        self,
        loop_id: Optional[str],
        trigger_id: Optional[str],
        children: list[Any],
    ) -> None:
        self.loop_id = loop_id
        self.trigger_id = trigger_id
        self.children = children
        # Pre-compute all segment_ids valid in this loop (direct children only)
        self.valid_seg_ids: set[str] = set()
        for child in children:
            if isinstance(child, SegEntry):
                self.valid_seg_ids.add(child.segment_id)


def build_nav_tree(spec_segments: list[Any]) -> LoopEntry:
    """Convert the hierarchical spec structure into a navigation tree.

    Returns a root ``LoopEntry`` with ``loop_id=None`` representing the top
    level.
    """
    children = _build_children(spec_segments)
    root = LoopEntry(loop_id=None, trigger_id=None, children=children)
    return root


def _build_children(spec_items: list[Any]) -> list[Any]:
    children: list[Any] = []
    for item in spec_items:
        if item.get("type") == "loop":
            nested = _build_children(item.get("segments", []))
            trigger_id: Optional[str] = None
            for child in nested:
                if isinstance(child, SegEntry):
                    trigger_id = child.segment_id
                    break
            loop = LoopEntry(
                loop_id=item.get("loop_id"),
                trigger_id=trigger_id,
                children=nested,
            )
            children.append(loop)
        elif item.get("segment_id"):
            children.append(SegEntry(item["segment_id"], item))
    return children


def assign_loop_paths(
    parsed_segments: list[Any],
    root: LoopEntry,
) -> list[tuple[dict[str, Any], Optional[str]]]:
    """Walk parsed segments and determine which loop each belongs to.

    Uses a stack-based state machine that navigates the spec tree:

    - Each stack frame is (LoopEntry, cursor_position)
    - cursor_position tracks how far forward we have scanned in a scope

    Returns list of (segment_dict, loop_path_string_or_None) tuples.
    """
    # Stack frames: list of [LoopEntry, cursor_pos]
    stack: list[list[Any]] = [[root, 0]]
    results: list[tuple[dict[str, Any], Optional[str]]] = []

    for seg in parsed_segments:
        seg_id = seg["segment_id"]
        placed = False

        attempts = 0
        max_attempts = len(stack) + 20

        while not placed and attempts < max_attempts:
            attempts += 1
            scope: LoopEntry = stack[-1][0]
            cursor: int = stack[-1][1]

            # 1. Check if seg_id triggers a child loop from cursor onward
            for i in range(cursor, len(scope.children)):
                child = scope.children[i]
                if isinstance(child, LoopEntry) and child.trigger_id == seg_id:
                    stack[-1][1] = i
                    stack.append([child, 1])
                    placed = True
                    break

            if placed:
                break

            # 2. Check if seg_id matches a segment in current scope from cursor onward
            for i in range(cursor, len(scope.children)):
                child = scope.children[i]
                if isinstance(child, SegEntry) and child.segment_id == seg_id:
                    stack[-1][1] = i + 1
                    placed = True
                    break

            if placed:
                break

            # 3. Check if seg_id is the trigger of the CURRENT loop (new iteration)
            if scope.loop_id and scope.trigger_id == seg_id:
                stack[-1][1] = 1
                placed = True
                break

            # 4. Also scan from start of current scope (segment may repeat or
            #    appear before cursor due to segment ordering flexibility)
            for i in range(0, min(cursor, len(scope.children))):
                child = scope.children[i]
                if isinstance(child, SegEntry) and child.segment_id == seg_id:
                    stack[-1][1] = i + 1
                    placed = True
                    break
                if isinstance(child, LoopEntry) and child.trigger_id == seg_id:
                    stack[-1][1] = i
                    stack.append([child, 1])
                    placed = True
                    break

            if placed:
                break

            # 5. Pop up to parent scope
            if len(stack) > 1:
                stack.pop()
            else:
                placed = True

        # Build loop_path from the stack
        path_parts: list[str] = []
        for frame in stack:
            lid = frame[0].loop_id
            if lid:
                path_parts.append(str(lid))
        loop_path: Optional[str] = "/".join(path_parts) if path_parts else None

        results.append((seg, loop_path))

    return results


# ---------------------------------------------------------------------------
# Spec lookup
# ---------------------------------------------------------------------------


def build_spec_lookup(
    spec_segments: list[Any],
    parent_loop_id: Optional[str] = None,
) -> dict[tuple[str, Optional[str]], dict[str, Any]]:
    """Flatten the hierarchical spec into a lookup dict keyed by (segment_id, loop_id).

    If the same key appears twice (rare), the first entry wins.
    """
    lookup: dict[tuple[str, Optional[str]], dict[str, Any]] = {}
    for item in spec_segments:
        if item.get("type") == "loop":
            loop_id: Optional[str] = item.get("loop_id")
            nested = build_spec_lookup(item.get("segments", []), loop_id)
            for key, val in nested.items():
                if key not in lookup:
                    lookup[key] = val
        elif item.get("segment_id"):
            key = (item["segment_id"], parent_loop_id)
            if key not in lookup:
                lookup[key] = item
    return lookup


def leaf_loop(loop_path: Optional[str]) -> Optional[str]:
    """Extract the innermost loop_id from a loop_path like ``'PO1/N1'`` -> ``'N1'``.

    Behavioral normalization: empty string and None both represent 'no loop
    path'. ``leaf_loop('')`` returns ``None`` via the ``if not loop_path``
    guard, identical to ``leaf_loop(None)``.
    """
    if not loop_path:
        return None
    parts = loop_path.split("/")
    return parts[-1] if parts else None


# ---------------------------------------------------------------------------
# Envelope checks
# ---------------------------------------------------------------------------


def check_envelope(
    transaction: dict[str, Any],
    parsed_segments: list[Any],
) -> list[ValidationIssue]:
    """Check SE01 reported segment count against actual parsed segment count."""
    issues: list[ValidationIssue] = []
    reported = transaction.get("segment_count_reported")
    if reported is not None:
        actual = len(parsed_segments) + 2  # +2 for ST and SE themselves
        if reported != actual:
            issues.append(
                make_issue(
                    "warning",
                    "envelope",
                    "SE",
                    None,
                    1,
                    f"SE01 reports {reported} segments but actual count is {actual}",
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Mandatory segment checks (loop-aware)
# ---------------------------------------------------------------------------


_ENVELOPE_SEGMENTS = {"ST", "SE"}


def check_mandatory_segments(
    loop_assignments: list[tuple[dict[str, Any], Optional[str]]],
    spec_segments: list[Any],
) -> list[ValidationIssue]:
    """Check that all M-requirement segments are present.

    Loop-aware: a mandatory segment inside a loop is required only if that
    loop has at least one iteration in the parsed data.
    """
    issues: list[ValidationIssue] = []
    # Collect loop_ids that actually appear in parsed data
    active_loops: set[str] = set()
    for _, loop_path in loop_assignments:
        if loop_path:
            for part in loop_path.split("/"):
                active_loops.add(part)

    # Collect present (segment_id, loop_id) pairs
    present: set[tuple[str, Optional[str]]] = set()
    for seg, loop_path in loop_assignments:
        lid = leaf_loop(loop_path)
        present.add((seg["segment_id"], lid))

    _check_mandatory_in_scope(spec_segments, None, active_loops, present, issues)
    return issues


def _check_mandatory_in_scope(
    spec_items: list[Any],
    parent_loop_id: Optional[str],
    active_loops: set[str],
    present: set[tuple[str, Optional[str]]],
    issues: list[ValidationIssue],
) -> None:
    for item in spec_items:
        if item.get("type") == "loop":
            loop_id: Optional[str] = item.get("loop_id")
            if loop_id in active_loops:
                _check_mandatory_in_scope(
                    item.get("segments", []),
                    loop_id,
                    active_loops,
                    present,
                    issues,
                )
        elif item.get("segment_id"):
            req = item.get("segment_requirement", "")
            if req == "M":
                seg_id: str = item["segment_id"]
                if seg_id in _ENVELOPE_SEGMENTS:
                    continue
                if (seg_id, parent_loop_id) not in present:
                    loop_label = f" in loop {parent_loop_id}" if parent_loop_id else ""
                    issues.append(
                        make_issue(
                            "error",
                            "mandatory_segment",
                            seg_id,
                            None,
                            None,
                            f"Mandatory segment {seg_id} is missing{loop_label}",
                        )
                    )


# ---------------------------------------------------------------------------
# Segment max-use checks
# ---------------------------------------------------------------------------


def check_segment_max_use(
    loop_assignments: list[tuple[dict[str, Any], Optional[str]]],
    spec_segments: list[Any],
) -> list[ValidationIssue]:
    """Count occurrences of each segment per loop and compare to segment_maximum_use."""
    issues: list[ValidationIssue] = []

    max_use_map: dict[tuple[str, Optional[str]], Any] = {}
    _collect_max_use(spec_segments, None, max_use_map)

    counts: dict[tuple[str, Optional[str]], int] = {}
    for seg, loop_path in loop_assignments:
        lid = leaf_loop(loop_path)
        key = (seg["segment_id"], lid)
        counts[key] = counts.get(key, 0) + 1

    for key, count in counts.items():
        seg_id_mu, lid_mu = key
        max_use = max_use_map.get(key)
        if max_use is None:
            continue
        try:
            max_val = int(max_use)
        except (ValueError, TypeError):
            continue
        if max_val > 0 and count > max_val:
            loop_label = f" in loop {lid_mu}" if lid_mu else ""
            issues.append(
                make_issue(
                    "warning",
                    "segment_max_use",
                    seg_id_mu,
                    None,
                    None,
                    f"Segment {seg_id_mu} appears {count} time(s) but max use is "
                    f"{max_val}{loop_label}",
                )
            )

    return issues


def _collect_max_use(
    spec_items: list[Any],
    parent_loop_id: Optional[str],
    result: dict[tuple[str, Optional[str]], Any],
) -> None:
    for item in spec_items:
        if item.get("type") == "loop":
            _collect_max_use(
                item.get("segments", []),
                item.get("loop_id"),
                result,
            )
        elif item.get("segment_id"):
            key = (item["segment_id"], parent_loop_id)
            mu = item.get("segment_maximum_use")
            if mu is not None and key not in result:
                result[key] = mu


# ---------------------------------------------------------------------------
# Element-level checks
# ---------------------------------------------------------------------------


def check_element_data_type(
    value: str,
    element_type: str,
    element_id: str,
) -> Optional[str]:
    """Validate ``value`` against the X12 ``element_type`` code.

    Returns an error message string on failure, or ``None`` on success.

    Bug fixes applied vs. monolith:

    - DT: calendar-aware date validation (uses ``calendar.monthrange``).
    - N-type: exactly one optional leading minus is allowed.
    - TM: seconds field (positions 4-5) validated to range 0-59 when present.
    """
    if not value or element_type == "B":
        return None

    if element_type == "AN":
        return None

    if element_type and element_type.startswith("N"):
        # Numeric types: N, N0, N1, N2, etc. — digits only, optional single minus
        if value.startswith("-"):
            if not (len(value) > 1 and value[1:].isdigit()):
                return (
                    f"Element {element_id}: expected numeric (type {element_type}), got '{value}'"
                )
        else:
            if not value.isdigit():
                return (
                    f"Element {element_id}: expected numeric (type {element_type}), got '{value}'"
                )
        return None

    if element_type == "DT":
        if len(value) not in (6, 8) or not value.isdigit():
            return f"Element {element_id}: expected date (YYMMDD or CCYYMMDD), got '{value}'"
        if len(value) == 8:
            year = int(value[0:4])
            mm = int(value[4:6])
            dd = int(value[6:8])
        else:
            yy = int(value[0:2])
            year = 2000 + yy if yy < 50 else 1900 + yy
            mm = int(value[2:4])
            dd = int(value[4:6])
        if not (1 <= mm <= 12):
            return f"Element {element_id}: invalid date '{value}'"
        max_day = calendar.monthrange(year, mm)[1]
        if not (1 <= dd <= max_day):
            return f"Element {element_id}: invalid date '{value}'"
        return None

    if element_type == "TM":
        if len(value) not in (4, 6, 8) or not value.isdigit():
            return f"Element {element_id}: expected time (HHMM/HHMMSS/HHMMSSdd), got '{value}'"
        hh, mm_tm = int(value[0:2]), int(value[2:4])
        if not (0 <= hh <= 23) or not (0 <= mm_tm <= 59):
            return f"Element {element_id}: invalid time '{value}'"
        if len(value) >= 6:
            ss = int(value[4:6])
            if not (0 <= ss <= 59):
                return f"Element {element_id}: invalid time '{value}'"
        return None

    if element_type == "R":
        if not re.match(r"^-?\d+\.?\d*$", value):
            return f"Element {element_id}: expected decimal number (type R), got '{value}'"
        return None

    if element_type == "ID":
        return None

    return None


def check_element_length(
    value: str,
    min_length: int | str,
    max_length: int | str,
) -> Optional[str]:
    """Validate that ``len(value)`` falls within ``[min_length, max_length]``.

    Returns an error message string on failure, or ``None`` on success.
    """
    if not value:
        return None
    vlen = len(value)
    try:
        mn = int(min_length)
        mx = int(max_length)
    except (ValueError, TypeError):
        return None

    if vlen < mn:
        return f"Value '{value}' is {vlen} char(s), minimum is {mn}"
    if mx > 0 and vlen > mx:
        return f"Value '{value}' is {vlen} char(s), maximum is {mx}"
    return None


# ---------------------------------------------------------------------------
# Relational condition checks
# ---------------------------------------------------------------------------


def check_relational_conditions(
    seg_id: str,
    rc_list: list[dict[str, Any]],
    val_by_pos: dict[int, str],
) -> list[ValidationIssue]:
    """Check relational conditions for a segment.

    ``rc_list`` items have:

    - ``transaction_set_segment_rc_type``: P/R/E/C/L
    - ``transaction_set_segment_rc_elements``: list of element position strings
    """
    issues: list[ValidationIssue] = []

    for rc in rc_list:
        rc_type = rc.get("transaction_set_segment_rc_type", "")
        positions_raw = rc.get("transaction_set_segment_rc_elements", [])
        positions: list[int] = []
        for p in positions_raw:
            try:
                positions.append(int(p))
            except (ValueError, TypeError):
                continue

        if len(positions) < 2:
            continue

        present_positions = [p for p in positions if val_by_pos.get(p, "")]
        pos_label = ",".join(f"{seg_id}{p:02d}" for p in positions)

        if rc_type == "P":
            if present_positions and len(present_positions) != len(positions):
                missing = [p for p in positions if p not in present_positions]
                miss_label = ",".join(f"{seg_id}{p:02d}" for p in missing)
                issues.append(
                    make_issue(
                        "error",
                        "relational_condition",
                        seg_id,
                        None,
                        None,
                        f"Paired condition: if any of ({pos_label}) is present, "
                        f"all must be present. Missing: {miss_label}",
                    )
                )

        elif rc_type == "R":
            if not present_positions:
                issues.append(
                    make_issue(
                        "warning",
                        "relational_condition",
                        seg_id,
                        None,
                        None,
                        f"Required condition: at least one of ({pos_label}) must be present",
                    )
                )

        elif rc_type == "E":
            # Deduplicate positions before Exclusion check to avoid false violations
            positions = list(dict.fromkeys(positions))
            present_positions = [p for p in positions if val_by_pos.get(p, "")]
            if len(present_positions) > 1:
                filled = ",".join(f"{seg_id}{p:02d}" for p in present_positions)
                issues.append(
                    make_issue(
                        "warning",
                        "relational_condition",
                        seg_id,
                        None,
                        None,
                        f"Exclusion condition: at most one of ({pos_label}) "
                        f"may be present, but found: {filled}",
                    )
                )

        elif rc_type == "C":
            first = positions[0]
            rest = positions[1:]
            if val_by_pos.get(first, ""):
                missing_rest = [p for p in rest if not val_by_pos.get(p, "")]
                if missing_rest:
                    miss_label = ",".join(f"{seg_id}{p:02d}" for p in missing_rest)
                    issues.append(
                        make_issue(
                            "error",
                            "relational_condition",
                            seg_id,
                            None,
                            None,
                            f"Conditional: {seg_id}{first:02d} is present so "
                            f"({miss_label}) must also be present",
                        )
                    )

        elif rc_type == "L":
            first = positions[0]
            rest = positions[1:]
            if val_by_pos.get(first, ""):
                any_rest = any(val_by_pos.get(p, "") for p in rest)
                if not any_rest:
                    rest_label = ",".join(f"{seg_id}{p:02d}" for p in rest)
                    issues.append(
                        make_issue(
                            "warning",
                            "relational_condition",
                            seg_id,
                            None,
                            None,
                            f"List conditional: {seg_id}{first:02d} is present so "
                            f"at least one of ({rest_label}) must be present",
                        )
                    )

    return issues
