# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.1] - Unreleased

Bug fixes and a security fix. Some validation results change: read **Changed** before upgrading.

### Security

- `JSONSkeletonSpecProvider`: the version and transaction set ID it builds a file path from come from the document being validated (GS08 and ST01). In 1.3.0 a crafted value, such as GS08 `../x` or an absolute path, made the provider read a `.json` file outside the spec directory. Both identifiers are now checked against the X12 formats (version: 1 to 12 letters or digits; transaction set ID: exactly 3), and the resolved path must stay inside the spec directory. Affects 1.3.0, the first release with the provider.

### Fixed

- Parser: element values in 004010 and other interchanges before version 00402 are no longer split on ISA11. Before 00402, ISA11 is the Interchange Control Standards Identifier (normally `U`), not a repetition separator; 1.3.0 split BEG03 `PUR-123` into `P` and `R-123`.
- Parser: an interchange no longer falls back to the first interchange's repetition or component separator.
- Parser: control characters such as RS or US work as repetition and component separators in every interchange, and `raw_isa` keeps a control-character ISA16 (1.3.0 stripped it).
- Parser: a non-ASCII digit in SE01 (such as `²`) gives `segment_count_reported=None`; 1.3.0's `parse_edi_file()` raised `ValueError`.
- Segment maximum use is counted per loop iteration and per loop path. 1.3.0 reported an 850 with two PO1 iterations, or with a heading N1 loop and a PO1/N1 loop, as exceeding maximum use.
- `X12Validator` looks up element rules for the loop a segment is in, so a segment ID used in several loops gets the rules of its own loop.
- `validate_edi()` uses the parser's element positions; in 1.3.0 a repeated element shifted the positions of the elements after it. Composite and repeated elements with data count as present in mandatory and relational checks.
- `validate_edi()` no longer raises. In 1.3.0 an exception from the spec provider (for example, `json.JSONDecodeError` for a malformed skeleton file) propagated. It now returns `is_valid=None` with a `SPEC_ERROR`; any other unexpected failure returns `is_valid=None` with an `INTERNAL_ERROR`. Findings made before the failure are kept. Only exceptions that do not derive from `Exception`, such as `KeyboardInterrupt`, propagate.
- `check_element_data_type()`: N, N0 to N9, R, DT and TM accept ASCII digits only and no longer raise on values such as `²`. R accepts `.5`, rejects a trailing newline and is matched in linear time. TM accepts HHMMSSd (tenths of a second) as well as HHMM, HHMMSS and HHMMSSdd.
- `JSONSkeletonSpecProvider` expands a leading `~` in `specs_dir`, as the documentation already showed, and returns `None` for a directory named like a spec file.
- Envelope counts and control numbers are compared after trimming spaces. GS06/GE02 and ISA13/IEA02 are compared by value without `int()` digit limits.
- Test fixture `tests/fixtures/sample_850.edi`: SE01 corrected from 9 to 8.

### Changed

- **Severity correction.** These findings now have severity `"error"` instead of `"warning"`, because X12 997 acknowledgments treat them as errors:
  - `check_envelope()`: SE01 count mismatch.
  - `check_segment_max_use()`: every finding.
  - `check_relational_conditions()`: R, E and L violations. P and C violations were already errors.

  No built-in check produces a `"warning"` issue any more.
- `validate_edi()` and `X12Validator` put each finding in `errors` or `warnings` according to its severity, the same way in both. In 1.3.0, `validate_edi()` without a spec provider put envelope findings in `warnings` as strings; they are now `ValidationError` entries in `errors`. `warnings` holds only advisory strings ("No spec_provider supplied...", "No spec found...", "No functional groups found...", "No transactions found..."). `is_valid` stays `None` when no spec is available, so check `errors` as well as `is_valid`.
- New `error_type` values: `ENVELOPE_ERROR` for envelope findings (`X12Validator` reported them as `MISSING_MANDATORY`), and `SPEC_ERROR` and `INTERNAL_ERROR` from `validate_edi()` (see Fixed).
- `validate_edi()` checks the whole envelope of the first interchange, functional group and transaction set: ST02/SE02, GS06/GE02 and ISA13/IEA02 control numbers, the SE01, GE01 and IEA01 counts, missing SE, GE and IEA trailers, and counts that are not numeric. 1.3.0 checked SE01 only. `check_envelope()` and `X12Validator` also check ST02/SE02 and a missing SE when the transaction comes from `parse_edi_file()` (it has `raw_se_segment`).
- Envelope checks run when no spec is available: without a provider, and when the provider has no matching spec. 1.3.0's `X12Validator` skipped them in that case.
- `X12Validator` and `validate_edi()` report a missing or empty mandatory (M) element as `MISSING_MANDATORY` with `element_pos` set.
- `validate_edi()` accepts `bytes` as well as `str`. Bytes are decoded as `parse_edi_file()` decodes them (UTF-8, `errors="replace"`).
- Parser: `repetition_sep` (`SeparatorInfo`, `Interchange`) is `None` when ISA12 is before 00402 or is not five ASCII digits, or when ISA11 is blank, a letter or digit, or the same character as another delimiter. `component_sep` is `None` when ISA16 is blank. Code that reads these values must handle `None`.
- Packaging: the version is set only in `pyproject.toml` and `draftedi.__version__` reads it from the installed metadata (1.3.0 reported `1.2.0`).
- Packaging: the `py.typed` marker is included, so type checkers use draftedi's annotations.
- Packaging: the source distribution includes the test suite (tests, helpers and fixtures), and CI runs the tests from the built sdist.
- Packaging: optional extras are now `test` (pytest and plugins), `lint` (ruff 0.15.22 and mypy 1.20.2, pinned) and `dev` (both). CI and the publish workflow install the pinned `lint` extra.
- Python 3.13 is tested in CI and listed in the classifiers.
- Documentation: the README describes the `validate_edi()` result semantics, error types, exceptions and known limitations, and uses absolute links so they work on PyPI. `MissingSpecError` is documented as not raised.

### Known limitations

Listed under "What is not checked" in the README. In short: `validate_edi()` validates only the first interchange, functional group and transaction set; `X12Validator` flattens nested loops; `loop_repeat` is not checked; code values are looked up by element ID and checked only when `repetition_count` is greater than 0; a skeleton file can define each segment ID once per transaction set; component values of composite elements are not checked; an unexpected failure inside `X12Validator` is reported as `SPEC_ERROR`.

## [1.3.0] - 2026-02-24

### Added

**Validator — high-level API**

- `validate_edi(edi_text, spec_provider=None) -> ValidationResult` — top-level convenience function. Envelope check only when called without a spec provider; `is_valid` is `None` (indeterminate), not `False`. Full structural validation when a spec provider is supplied. Never raises. Exported from `draftedi`. *(Note added in 1.3.1: in 1.3.0 an exception raised by the spec provider, for example for a malformed skeleton file, propagated out of `validate_edi()`. Fixed in 1.3.1.)*
- `X12Validator(spec_provider)` — class that wraps the existing `validate.py` check functions. Accepts any object satisfying the `X12SpecProvider` Protocol via structural subtyping; no inheritance required. Method: `validate_transaction(parsed_transaction, version) -> ValidationResult`. Exported from `draftedi` and `draftedi.validator`.
- `JSONSkeletonSpecProvider(directory)` — BYOS spec provider that loads structural-only JSON skeleton files from a local directory. File naming convention: `{version}-{tsid}.json` (e.g., `005010-850.json`). Returns `None` on missing file rather than raising. Caches loaded specs per instance. Satisfies `X12SpecProvider` via structural subtyping; no explicit inheritance. `element_name` and `segment_name` fields are `None` (ASC X12 copyright). Exported from `draftedi.spec`.

**Dataclasses**

- `ValidationResult` — dataclass with fields: `is_valid` (`Optional[bool]`), `errors` (`list[ValidationError]`), `warnings` (`list[str]`), `spec_provider` (`Optional[str]`). Exported from `draftedi` and `draftedi.validator`.
- `ValidationError` — dataclass with fields: `segment_id`, `element_pos`, `error_type`, `value`, `message`. `error_type` values: `MISSING_MANDATORY`, `INVALID_LENGTH`, `INVALID_CODE`, `MAX_USE_EXCEEDED`, `RELATIONAL_CONDITION`, `TYPE_ERROR`. Exported from `draftedi` and `draftedi.validator`.

**Documentation**

- `specs/README.md` — documents the BYOS JSON skeleton file format, required fields, and workflow for authoring custom spec files.

**Tests**

- 205 passing tests across parser, validator, and high-level API surface.

## [1.2.0] - 2026-02-24

Not published to PyPI. These changes were first released in 1.3.0.

### Added
- `X12SpecProvider` protocol (typing.Protocol) -- BYOS (Bring Your Own Spec) injection interface
- `MissingSpecError` exception for spec-absent validation scenarios *(note added in 1.3.1: no draftedi function raises it; it is exported for API compatibility)*
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
