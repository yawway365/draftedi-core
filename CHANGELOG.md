# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - Unreleased

### Added

**Validator — high-level API**

- `validate_edi(edi_text, spec_provider=None) -> ValidationResult` — top-level convenience function (S2-9). Envelope check only when called without a spec provider; `is_valid` is `None` (indeterminate), not `False`. Full structural validation when a spec provider is supplied. Never raises. Exported from `draftedi`.
- `X12Validator(spec_provider)` — class that wraps the existing `validate.py` check functions (S2-7). Accepts any object satisfying the `X12SpecProvider` Protocol via structural subtyping; no inheritance required. Method: `validate_transaction(parsed_transaction, version) -> ValidationResult`. Exported from `draftedi` and `draftedi.validator`.
- `JSONSkeletonSpecProvider(directory)` — BYOS spec provider that loads structural-only JSON skeleton files from a local directory (S2-8). File naming convention: `{version}-{tsid}.json` (e.g., `005010-850.json`). Returns `None` on missing file rather than raising. Caches loaded specs per instance. Satisfies `X12SpecProvider` via structural subtyping; no explicit inheritance. `element_name` and `segment_name` fields are `None` (ASC X12 copyright). Exported from `draftedi.spec`.

**Dataclasses**

- `ValidationResult` — dataclass with fields: `is_valid` (`Optional[bool]`), `errors` (`list[ValidationError]`), `warnings` (`list[str]`), `spec_provider` (`Optional[str]`). Exported from `draftedi` and `draftedi.validator`.
- `ValidationError` — dataclass with fields: `segment_id`, `element_pos`, `error_type`, `value`, `message`. `error_type` values: `MISSING_MANDATORY`, `INVALID_LENGTH`, `INVALID_CODE`, `MAX_USE_EXCEEDED`, `RELATIONAL_CONDITION`, `TYPE_ERROR`. Exported from `draftedi` and `draftedi.validator`.

**Documentation**

- `specs/README.md` — documents the BYOS JSON skeleton file format, required fields, and workflow for authoring custom spec files.

**Tests**

- 205 passing tests across parser, validator, and high-level API surface.

## [1.2.0] - 2026-02-24

### Added
- `X12SpecProvider` protocol (typing.Protocol) -- BYOS (Bring Your Own Spec) injection interface
- `MissingSpecError` exception for spec-absent validation scenarios
- `ElementSpec`, `SegmentSpec`, `RelationalCondition`, `TransactionSetSpec` TypedDicts
- `X12SpecProvider` and `MissingSpecError` exported from `draftedi` top-level

**Stability note:** X12SpecProvider method signatures and all TypedDict field names
are frozen from this release.

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
