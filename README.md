# draftedi

EDI parser and validator for Python. Zero dependencies.

![PyPI version](https://img.shields.io/badge/pypi-1.3.0-blue)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![MIT license](https://img.shields.io/badge/license-MIT-green)
![CI](https://img.shields.io/badge/CI-passing-brightgreen)

## Install

```
pip install draftedi
```

## Quickstart — Parse

```python
from draftedi.parser import parse_edi_file

raw = open("sample.edi", "rb").read()
# or use bytes directly:
# raw = b"ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260222*1200*^*00501*000000001*0*P*:~..."

result = parse_edi_file(raw, source="sample.edi")

for interchange in result["interchanges"]:
    print(interchange["isa_sender_id"])   # e.g. "SENDER         "
    print(interchange["element_sep"])     # e.g. "*"
    for group in interchange["groups"]:
        for transaction in group["transactions"]:
            for segment in transaction["segments"]:
                print(segment["segment_id"])  # e.g. "BEG", "PO1", "SE"
```

`parse_edi_file` returns plain `TypedDict` / `dict` instances — no custom objects, no ORM. Index directly with string keys.

## Quickstart — Validate (no spec data needed)

```python
from draftedi.validate import check_envelope, check_element_data_type

# Envelope check: SE01 reported count vs actual parsed count
issues = check_envelope(transaction, transaction["segments"])
# issues is a list[ValidationIssue] — plain dicts

# Element data type check
error = check_element_data_type("20260222", "DT", "BEG03")
# error is None if valid, or an error string if invalid
```

Both functions operate on the output of `parse_edi_file` with no spec data required.

## Spec-aware validation (BYOS)

`draftedi` ships without X12 spec databases — ANSI/X12 spec data is copyrighted and cannot be bundled. Spec-aware validation follows a **Bring Your Own Spec (BYOS)** model: you supply spec data as Python dicts, and the library applies loop-aware rules against your parsed output.

Minimal example:

```python
from draftedi.validate import build_nav_tree, assign_loop_paths, check_mandatory_segments

# spec_segments: a list of dicts you provide, following the expected schema.
# Each dict describes a segment's position, requirement, max use, and loop membership.
spec_segments = [
    {
        "segment_id": "BEG",
        "segment_requirement": "M",
        "segment_maximum_use": 1,
    },
    {
        "type": "loop",
        "loop_id": "PO1",
        "segments": [
            {
                "segment_id": "PO1",
                "segment_requirement": "M",
                "segment_maximum_use": 999999,
            },
            {
                "type": "loop",
                "loop_id": "N1",
                "segments": [
                    {
                        "segment_id": "N1",
                        "segment_requirement": "O",
                        "segment_maximum_use": 200,
                    }
                ],
            },
        ],
    },
]

root = build_nav_tree(spec_segments)
loop_assignments = assign_loop_paths(transaction["segments"], root)
issues = check_mandatory_segments(loop_assignments, spec_segments)
# issues: list[ValidationIssue]
```

The same `loop_assignments` output can be passed to `check_segment_max_use` and `check_relational_conditions`.

## Validation API (v1.3.0)

### validate_edi() — convenience function

`validate_edi(edi_text, spec_provider=None) -> ValidationResult`

The top-level entry point for validation. Accepts raw X12 text. Never raises.

**Without a spec provider** — envelope check only. `is_valid` is `None` (indeterminate), not `False`.

```python
from draftedi import validate_edi

result = validate_edi(edi_text)
print(result.is_valid)   # None — indeterminate without spec data
print(result.errors)     # list[ValidationError] from envelope check
print(result.warnings)   # list[str]
```

**With a spec provider** — full structural validation against your spec data.

```python
from draftedi import validate_edi
from draftedi.spec import JSONSkeletonSpecProvider

provider = JSONSkeletonSpecProvider("path/to/specs/")
result = validate_edi(edi_text, spec_provider=provider)

print(result.is_valid)         # True or False
print(result.spec_provider)    # "JSONSkeletonSpecProvider"
for err in result.errors:
    print(err.segment_id, err.error_type, err.message)
```

### JSONSkeletonSpecProvider — BYOS with JSON files

Loads structural-only JSON skeleton files from a local directory. Files must be named `{version}-{tsid}.json` (e.g., `005010-850.json`). Returns `None` for any missing file rather than raising. Caches loaded specs per instance.

No X12 spec data is included or required — you supply the files.

```python
from draftedi.spec import JSONSkeletonSpecProvider

provider = JSONSkeletonSpecProvider("path/to/specs/")
result = validate_edi(edi_text, spec_provider=provider)
```

See `specs/README.md` in this repository for the JSON skeleton file format and field reference.

Note: `element_name` and `segment_name` fields are `None` in skeleton providers. ASC X12 copyrights prohibit bundling human-readable element and segment names.

### X12Validator — direct usage

Accepts any object that satisfies the `X12SpecProvider` Protocol via structural subtyping — no explicit inheritance required.

```python
from draftedi import X12Validator
from draftedi.spec import JSONSkeletonSpecProvider

provider = JSONSkeletonSpecProvider("path/to/specs/")
validator = X12Validator(provider)

# parsed_transaction: a Transaction dict from parse_edi_file()
result = validator.validate_transaction(parsed_transaction, version="005010")

print(result.is_valid)
for err in result.errors:
    print(f"{err.segment_id}[{err.element_pos}] {err.error_type}: {err.message}")
```

### ValidationResult and ValidationError

`ValidationResult` is a dataclass returned by `validate_edi()` and `X12Validator.validate_transaction()`.

| Field | Type | Notes |
|---|---|---|
| `is_valid` | `Optional[bool]` | `None` = indeterminate (no spec); `True`/`False` when spec is present |
| `errors` | `list[ValidationError]` | Structured error records |
| `warnings` | `list[str]` | Non-fatal advisory strings |
| `spec_provider` | `Optional[str]` | Name of the provider class used, or `None` |

`ValidationError` is a dataclass with the following fields:

| Field | Type |
|---|---|
| `segment_id` | `str` |
| `element_pos` | `Optional[int]` |
| `error_type` | `str` |
| `value` | `Optional[str]` |
| `message` | `str` |

`error_type` values: `MISSING_MANDATORY`, `INVALID_LENGTH`, `INVALID_CODE`, `MAX_USE_EXCEEDED`, `RELATIONAL_CONDITION`, `TYPE_ERROR`.

### Import paths

```python
from draftedi import validate_edi, X12Validator, ValidationResult, ValidationError
from draftedi.spec import JSONSkeletonSpecProvider
from draftedi.validator import X12Validator, ValidationResult, ValidationError
```

## API reference

### Parser functions

| Function | Returns | Raises |
|---|---|---|
| `parse_edi_file(raw_bytes: bytes, source: str = "manual upload") -> ParsedFile` | Full document hierarchy as a `ParsedFile` TypedDict | `ValueError` on malformed input |
| `parse_interchange(x12_text: str) -> SeparatorInfo` | Separator characters extracted from the ISA header | `ValueError` if text does not start with `ISA` or is shorter than 106 characters |

### Parser TypedDicts

The parsed hierarchy maps directly onto the X12 envelope structure.

- **`ParsedFile`** — top-level container. Key field: `interchanges` (list of `Interchange`).
- **`Interchange`** — one ISA/IEA envelope. Key fields: `isa_sender_id`, `isa_receiver_id`, `element_sep`, `segment_term`, `groups`.
- **`FunctionalGroup`** — one GS/GE envelope. Key fields: `gs_sender_id`, `gs_receiver_id`, `transactions`.
- **`Transaction`** — one ST/SE envelope. Key fields: `transaction_set_id`, `control_number`, `segments`.
- **`Segment`** — one X12 segment. Key fields: `segment_id`, `position`, `loop_path`, `elements`.
- **`Element`** — one element within a segment. Key fields: `element_pos`, `value_text`, `is_composite`, `components`.
- **`Component`** — one component within a composite element. Key fields: `component_pos`, `value_text`.
- **`SeparatorInfo`** — separator characters detected from the ISA header. Key fields: `element_sep`, `component_sep`, `repetition_sep`, `segment_term`.

### Validator — spec-free functions

- `check_element_data_type(value, element_type, element_id)` — validates AN, N/N0–N9, DT, TM, R, and ID element types. Returns an error string or `None`.
- `check_element_length(value, min_length, max_length)` — validates character length bounds. Returns an error string or `None`.
- `check_envelope(transaction, parsed_segments)` — checks SE01 reported segment count against the actual count of parsed segments. Returns a list of `ValidationIssue`.
- `check_relational_conditions(seg_id, rc_list, val_by_pos)` — checks P (Paired), R (Required), E (Exclusion), C (Conditional), and L (List Conditional) relational conditions. Returns a list of `ValidationIssue`.
- `leaf_loop(loop_path)` — extracts the innermost loop ID from a path string such as `"PO1/N1"` → `"N1"`. Returns `None` if input is `None`.
- `make_issue(severity, category, segment_id, segment_position, element_pos, message)` — constructs a `ValidationIssue` dict.

### Validator — spec-aware functions

- `build_nav_tree(spec_segments)` — converts a hierarchical spec structure into a `LoopEntry` navigation tree used by `assign_loop_paths`.
- `build_spec_lookup(spec_segments, parent_loop_id)` — flattens a spec into a `(segment_id, loop_id) -> spec_dict` lookup dict.
- `assign_loop_paths(parsed_segments, root)` — walks parsed segments and assigns a loop path to each using a stack-based state machine. Returns a list of `(segment_dict, loop_path_or_None)` tuples.
- `check_mandatory_segments(loop_assignments, spec_segments)` — loop-aware check for segments with M (Mandatory) requirement. Returns a list of `ValidationIssue`.
- `check_segment_max_use(loop_assignments, spec_segments)` — loop-aware check for segments that exceed their specified maximum use count. Returns a list of `ValidationIssue`.

### Validator types

**`ValidationIssue`** — a `TypedDict` with the following fields:

| Field | Type | Description |
|---|---|---|
| `severity` | `str` | `"error"` or `"warning"` |
| `category` | `str` | Broad classification of the issue (e.g. `"envelope"`, `"data_type"`) |
| `segment_id` | `str` | ID of the segment where the issue occurred |
| `segment_position` | `int` | Position of the segment within the transaction |
| `element_pos` | `Optional[int]` | Position of the element within the segment, if applicable |
| `message` | `str` | Human-readable description of the issue |

**`SegEntry`** — wraps a segment ID and its spec dict. Used internally by spec-aware functions.

**`LoopEntry`** — represents a node in the navigation tree. Fields: `loop_id`, `trigger_id` (the segment ID that starts this loop), `children` (list of `LoopEntry`).

### Validator — high-level API (v1.3.0)

- `validate_edi(edi_text: str, spec_provider=None) -> ValidationResult` — top-level convenience function. Envelope check only when `spec_provider` is omitted (`is_valid=None`); full validation when a provider is supplied.
- `X12Validator(spec_provider)` — wraps the low-level check functions. Accepts any object satisfying the `X12SpecProvider` Protocol (structural subtyping). Method: `validate_transaction(parsed_transaction, version) -> ValidationResult`.
- `JSONSkeletonSpecProvider(directory: str)` — loads `{version}-{tsid}.json` skeleton files from `directory`. Returns `None` for missing specs. Import from `draftedi.spec`.

### Validator — high-level types (v1.3.0)

**`ValidationResult`** — dataclass returned by `validate_edi()` and `X12Validator.validate_transaction()`.

| Field | Type | Notes |
|---|---|---|
| `is_valid` | `Optional[bool]` | `None` = indeterminate |
| `errors` | `list[ValidationError]` | Structured error records |
| `warnings` | `list[str]` | Non-fatal advisory strings |
| `spec_provider` | `Optional[str]` | Provider class name, or `None` |

**`ValidationError`** — dataclass attached to `ValidationResult.errors`.

| Field | Type |
|---|---|
| `segment_id` | `str` |
| `element_pos` | `Optional[int]` |
| `error_type` | `str` |
| `value` | `Optional[str]` |
| `message` | `str` |

`error_type` values: `MISSING_MANDATORY`, `INVALID_LENGTH`, `INVALID_CODE`, `MAX_USE_EXCEEDED`, `RELATIONAL_CONDITION`, `TYPE_ERROR`.

## Development

```
pip install -e ".[dev]"
pytest
ruff check src tests
mypy src
```

## Contributing

We welcome contributions. DraftEDI uses a Contributor License Agreement for code changes — see [CONTRIBUTING.md](CONTRIBUTING.md) for details. Doc fixes and small patches (15 lines or fewer) don't require signing.

## License

MIT — see [LICENSE](LICENSE).
