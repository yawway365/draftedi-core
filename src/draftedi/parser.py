"""X12 EDI document parser.

Parses raw X12 bytes into hierarchical Python dictionaries:
interchanges -> groups -> transactions -> segments -> elements -> components.

Encoding strategy: ``parse_edi_file`` decodes bytes with UTF-8 and
``errors='replace'``.  Latin-1 bytes become U+FFFD replacement characters
rather than raising; a UTF-8 BOM causes ``ValueError`` because the decoded
text does not start with ``ISA``; non-UTF-8 content degrades gracefully.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional, TypedDict


# ---------------------------------------------------------------------------
# TypedDict definitions
# ---------------------------------------------------------------------------


class Component(TypedDict):
    component_pos: int
    value_text: str


class Element(TypedDict):
    element_pos: int
    is_composite: int
    value_text: Optional[str]
    present: int
    repetition_index: Optional[int]
    components: list[Component]


class Segment(TypedDict):
    position: int
    segment_id: str
    loop_path: Optional[str]
    raw_segment: str
    elements: list[Element]


class Transaction(TypedDict):
    transaction_set_id: Optional[str]
    control_number: Optional[str]
    implementation_version: Optional[str]
    segment_count_reported: Optional[int]
    raw_st_segment: Optional[str]
    raw_se_segment: Optional[str]
    segments: list[Segment]


class FunctionalGroup(TypedDict):
    functional_id_code: Optional[str]
    gs_sender_id: Optional[str]
    gs_receiver_id: Optional[str]
    group_control_number: Optional[str]
    x12_release: Optional[str]
    raw_gs_segment: str
    transactions: list[Transaction]


class Interchange(TypedDict):
    isa_control_number: Optional[str]
    isa_sender_qualifier: Optional[str]
    isa_sender_id: Optional[str]
    isa_receiver_qualifier: Optional[str]
    isa_receiver_id: Optional[str]
    isa_date: Optional[str]
    isa_time: Optional[str]
    usage_indicator: Optional[str]
    version: Optional[str]
    element_sep: str
    component_sep: Optional[str]
    segment_term: str
    repetition_sep: Optional[str]
    raw_isa: str
    groups: list[FunctionalGroup]


class ParsedFile(TypedDict):
    file_hash: str
    processed_at: str
    filename: str
    source: str
    interchanges: list[Interchange]


class SeparatorInfo(TypedDict):
    element_sep: str
    segment_term: str
    repetition_sep: Optional[str]
    component_sep: Optional[str]
    raw_isa: str
    isa_parts: list[str]


# ---------------------------------------------------------------------------
# Separator detection
# ---------------------------------------------------------------------------


def parse_interchange(x12_text: str) -> SeparatorInfo:
    """Detect element/component/repetition separators and segment terminator from the ISA header.

    Separator detection must complete before any other parsing occurs.  The ISA
    header is exactly 106 characters: element separator at position 3, segment
    terminator at position 105.

    Args:
        x12_text: Raw X12 text.  Must start with ``ISA`` and be at least 106 characters.

    Returns:
        A ``SeparatorInfo`` dict with keys ``element_sep``, ``segment_term``,
        ``repetition_sep``, ``component_sep``, ``raw_isa``, and ``isa_parts``.
        ``repetition_sep`` and ``component_sep`` are ``None`` when the
        corresponding ISA field is absent or empty.

    Raises:
        ValueError: If the text does not start with ``ISA`` or is shorter than
            106 characters.
    """
    if not x12_text.startswith("ISA"):
        raise ValueError("File does not start with ISA segment")

    if len(x12_text) < 106:
        raise ValueError("File does not contain a full ISA segment")

    element_sep = x12_text[3]
    segment_term = x12_text[105]
    raw_isa = x12_text[0:106]
    isa_parts = raw_isa.split(element_sep)

    repetition_sep: Optional[str] = isa_parts[11] if len(isa_parts) > 11 else None
    # isa_parts[16] may be an empty string; indexing [0] on an empty string raises IndexError.
    component_sep: Optional[str] = (
        isa_parts[16][0] if len(isa_parts) > 16 and isa_parts[16] else None
    )

    # Normalize blanks
    repetition_sep = repetition_sep if repetition_sep else None
    component_sep = component_sep if component_sep else None

    return SeparatorInfo(
        element_sep=element_sep,
        segment_term=segment_term,
        repetition_sep=repetition_sep,
        component_sep=component_sep,
        raw_isa=raw_isa,
        isa_parts=isa_parts,
    )


# ---------------------------------------------------------------------------
# Main file parser
# ---------------------------------------------------------------------------


def parse_edi_file(raw_bytes: bytes, source: str = "manual upload") -> ParsedFile:
    """Parse raw X12 EDI bytes into a hierarchical Python structure.

    Decodes ``raw_bytes`` with UTF-8 and ``errors='replace'``.  Latin-1 bytes
    produce U+FFFD replacement characters rather than raising.  A UTF-8 BOM
    causes ``ValueError`` because the decoded text does not start with ``ISA``.
    Non-UTF-8 content degrades gracefully.

    The filename is read from ``raw_bytes.filename`` when that attribute exists
    (e.g. file-like objects); otherwise ``'raw text'`` is used.

    Separator detection from the first ISA header completes before any segment
    is parsed.  Each subsequent ISA header overrides the active repetition and
    component separators for elements within that interchange.

    Segments outside ST/SE envelopes (between GS and ST) are silently ignored.

    Args:
        raw_bytes: Raw X12 content as bytes.
        source: Optional source label (default: ``"manual upload"``).

    Returns:
        A flat ``ParsedFile`` dict with keys ``file_hash``, ``processed_at``,
        ``filename``, ``source``, and ``interchanges``.  No DB-specific fields
        are present in any nested dict.

    Raises:
        ValueError: If content does not start with ``ISA``, the ISA header is
            incomplete, ``GS`` appears before ``ISA``, ``ST`` appears before
            ``GS``, or ``SE`` appears with no active transaction.
    """
    x12_text = raw_bytes.decode("utf-8", errors="replace")

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    filename: str = getattr(raw_bytes, "filename", "raw text")
    processed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Separator detection from the first ISA header
    sep = parse_interchange(x12_text)
    element_sep = sep["element_sep"]
    segment_term = sep["segment_term"]
    repetition_sep = sep["repetition_sep"]
    component_sep = sep["component_sep"]

    # Split into segments; trim whitespace/newlines around each segment
    raw_segments = [s.strip() for s in x12_text.split(segment_term)]
    segments = [s for s in raw_segments if s]

    interchanges: list[Interchange] = []

    current_interchange: Optional[Interchange] = None
    current_group: Optional[FunctionalGroup] = None
    current_tx: Optional[Transaction] = None
    current_tx_pos = 0
    # Active element sep: may change per interchange when each ISA declares its own
    active_element_sep = element_sep

    for seg in segments:
        # ISA segments self-declare their element separator at position 3.
        # When a new ISA uses a different element sep, switch the active sep
        # so that all subsequent segments in that interchange are parsed correctly.
        if seg.startswith("ISA") and len(seg) >= 4:
            active_element_sep = seg[3]

        parts = seg.split(active_element_sep)
        seg_id = parts[0].strip() if parts else ""
        seg_elements = parts[1:] if len(parts) > 1 else []

        if seg_id == "ISA":
            isa_parts = parts
            isa_sender_qual: Optional[str] = isa_parts[5] if len(isa_parts) > 5 else None
            isa_sender_id: Optional[str] = isa_parts[6] if len(isa_parts) > 6 else None
            isa_receiver_qual: Optional[str] = isa_parts[7] if len(isa_parts) > 7 else None
            isa_receiver_id: Optional[str] = isa_parts[8] if len(isa_parts) > 8 else None
            isa_date: Optional[str] = isa_parts[9] if len(isa_parts) > 9 else None
            isa_time: Optional[str] = isa_parts[10] if len(isa_parts) > 10 else None
            isa_control: Optional[str] = isa_parts[13] if len(isa_parts) > 13 else None
            usage_indicator: Optional[str] = isa_parts[15] if len(isa_parts) > 15 else None
            version: Optional[str] = isa_parts[12] if len(isa_parts) > 12 else None

            # Per-interchange separator overrides (ISA11 = repetition, ISA16 = component)
            ic_rep_sep: Optional[str] = isa_parts[11] if len(isa_parts) > 11 else None
            ic_comp_sep: Optional[str] = (
                isa_parts[16][0] if len(isa_parts) > 16 and isa_parts[16] else None
            )
            ic_rep_sep = ic_rep_sep if ic_rep_sep and ic_rep_sep.strip() else repetition_sep
            ic_comp_sep = ic_comp_sep if ic_comp_sep and ic_comp_sep.strip() else component_sep

            current_interchange = Interchange(
                isa_control_number=isa_control,
                isa_sender_qualifier=isa_sender_qual,
                isa_sender_id=isa_sender_id,
                isa_receiver_qualifier=isa_receiver_qual,
                isa_receiver_id=isa_receiver_id,
                isa_date=isa_date,
                isa_time=isa_time,
                usage_indicator=usage_indicator,
                version=version,
                element_sep=active_element_sep,
                component_sep=ic_comp_sep,
                segment_term=segment_term,
                repetition_sep=ic_rep_sep,
                raw_isa=seg,
                groups=[],
            )
            interchanges.append(current_interchange)
            continue

        if seg_id == "GS":
            if current_interchange is None:
                raise ValueError("Encountered GS before ISA")

            functional_id_code: Optional[str] = seg_elements[0] if len(seg_elements) > 0 else None
            gs_sender_id: Optional[str] = seg_elements[1] if len(seg_elements) > 1 else None
            gs_receiver_id: Optional[str] = seg_elements[2] if len(seg_elements) > 2 else None
            group_control_number: Optional[str] = seg_elements[5] if len(seg_elements) > 5 else None
            x12_release: Optional[str] = seg_elements[7] if len(seg_elements) > 7 else None

            current_group = FunctionalGroup(
                functional_id_code=functional_id_code,
                gs_sender_id=gs_sender_id,
                gs_receiver_id=gs_receiver_id,
                group_control_number=group_control_number,
                x12_release=x12_release,
                raw_gs_segment=seg,
                transactions=[],
            )
            current_interchange["groups"].append(current_group)
            continue

        if seg_id == "ST":
            if current_group is None:
                raise ValueError("Encountered ST before GS")

            transaction_set_id: Optional[str] = seg_elements[0] if len(seg_elements) > 0 else None
            control_number: Optional[str] = seg_elements[1] if len(seg_elements) > 1 else None
            impl_version: Optional[str] = seg_elements[2] if len(seg_elements) > 2 else None

            current_tx = Transaction(
                transaction_set_id=transaction_set_id,
                control_number=control_number,
                implementation_version=impl_version,
                segment_count_reported=None,
                raw_st_segment=seg,
                raw_se_segment=None,
                segments=[],
            )
            current_group["transactions"].append(current_tx)
            current_tx_pos = 0
            continue

        if seg_id == "SE":
            if current_tx is None:
                raise ValueError("Encountered SE but no active transaction")

            seg_count: Optional[int] = None
            if len(seg_elements) > 0 and seg_elements[0].isdigit():
                seg_count = int(seg_elements[0])

            current_tx["segment_count_reported"] = seg_count
            current_tx["raw_se_segment"] = seg
            current_tx = None
            current_tx_pos = 0
            continue

        if seg_id == "GE":
            current_group = None
            continue

        if seg_id == "IEA":
            current_interchange = None
            continue

        # Normal business segments: only store if inside an active transaction
        if current_tx is not None:
            current_tx_pos += 1

            # Use per-interchange separators for element parsing
            ic_rep_sep_active: Optional[str] = repetition_sep
            ic_comp_sep_active: Optional[str] = component_sep
            if current_interchange is not None:
                ic_rep_sep_active = current_interchange.get("repetition_sep") or repetition_sep
                ic_comp_sep_active = current_interchange.get("component_sep") or component_sep

            seg_elements_parsed: list[Element] = []

            for element_pos, val in enumerate(seg_elements, start=1):
                if val is None:
                    val = ""

                reps = [val]
                if ic_rep_sep_active and ic_rep_sep_active in val:
                    reps = val.split(ic_rep_sep_active)

                for rep_index, rep_val in enumerate(reps, start=1):
                    # Fresh Element per repetition: a shared dict would alias
                    # all N seg_elements_parsed entries to the same object,
                    # making every repetition show the last value.
                    # One allocation per repetition is negligible — Element is a plain dict.
                    element_dict: Element = Element(
                        element_pos=element_pos,
                        is_composite=0,
                        value_text=None,
                        present=1,
                        repetition_index=rep_index,
                        components=[],
                    )

                    if ic_comp_sep_active and ic_comp_sep_active in rep_val:
                        element_dict["is_composite"] = 1
                        components: list[Component] = []
                        for component_pos, cval in enumerate(
                            rep_val.split(ic_comp_sep_active), start=1
                        ):
                            components.append(
                                Component(component_pos=component_pos, value_text=cval)
                            )
                        element_dict["components"] = components
                        seg_elements_parsed.append(element_dict)
                    else:
                        element_dict["value_text"] = rep_val
                        seg_elements_parsed.append(element_dict)

            segment_dict = Segment(
                position=current_tx_pos,
                segment_id=seg_id,
                loop_path=None,
                raw_segment=seg,
                elements=seg_elements_parsed,
            )
            current_tx["segments"].append(segment_dict)

    return ParsedFile(
        file_hash=sha256,
        processed_at=processed_at,
        filename=filename,
        source=source,
        interchanges=interchanges,
    )
