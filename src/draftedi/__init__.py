"""draftedi — X12 EDI parser and validator.

Provides pure-Python X12 EDI parsing (``parse_edi_file``,
``parse_interchange``) and database-free validation functions
(``check_element_data_type``, ``check_envelope``, etc.).

All public names are listed in ``__all__``.
"""

from __future__ import annotations

__version__ = "1.1.0"

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
]
