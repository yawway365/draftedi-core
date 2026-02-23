# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] — 2026-02-22

Initial release of `draftedi` on PyPI.

### Added

**Parser**

- `parse_edi_file(raw_bytes, source)` — decodes raw X12 bytes, detects separators from the ISA header, and returns a `ParsedFile` TypedDict (interchanges → groups → transactions → segments → elements → components). Per-interchange separator overrides supported for multi-interchange files.
- `parse_interchange(x12_text)` — extracts element separator, segment terminator, repetition separator, and component separator from the ISA header.
- TypedDicts: `ParsedFile`, `Interchange`, `FunctionalGroup`, `Transaction`, `Segment`, `Element`, `Component`, `SeparatorInfo`

**Validator — spec-free**

- `check_element_data_type(value, element_type, element_id)` — validates AN, N/N0–N9, DT, TM, R, and ID element types.
- `check_element_length(value, min_length, max_length)` — validates element character length bounds.
- `check_envelope(transaction, parsed_segments)` — checks SE01 reported segment count against actual parsed count.
- `check_relational_conditions(seg_id, rc_list, val_by_pos)` — checks P (Paired), R (Required), E (Exclusion), C (Conditional), and L (List Conditional) relational conditions.
- `leaf_loop(loop_path)` — extracts the innermost loop ID from a loop path string.
- `make_issue(severity, category, segment_id, segment_position, element_pos, message)` — constructs a `ValidationIssue`.
- TypedDict: `ValidationIssue`

**Validator — spec-aware (BYOS)**

- `build_nav_tree(spec_segments)` — converts a hierarchical spec structure into a `LoopEntry` navigation tree.
- `build_spec_lookup(spec_segments, parent_loop_id)` — flattens the spec into a `(segment_id, loop_id) → spec_dict` lookup.
- `assign_loop_paths(parsed_segments, root)` — walks parsed segments and assigns loop paths using a stack-based state machine.
- `check_mandatory_segments(loop_assignments, spec_segments)` — loop-aware check for M-requirement segments.
- `check_segment_max_use(loop_assignments, spec_segments)` — loop-aware check for segment maximum-use violations.
- Classes: `SegEntry`, `LoopEntry`

### Fixed

Validator bug fixes applied relative to the internal monolith:

- **`check_element_data_type` — DT type:** Day validation is now calendar-aware using `calendar.monthrange`. Previously used fixed day bounds that accepted invalid dates such as February 30.
- **`check_element_data_type` — N-type:** Exactly one optional leading minus is now enforced. Previously, values like `--5` were accepted as valid numeric.
- **`check_element_data_type` — TM type:** Seconds field (positions 4–5) is now validated to range 0–59 when present. Previously out-of-range seconds were not caught.
- **`check_relational_conditions` — E (Exclusion) type:** Element positions are now deduplicated before the Exclusion check. Duplicate positions in spec entries previously caused false violations.
