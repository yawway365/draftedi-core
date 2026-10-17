# draftedi

X12 EDI parser and validator for Python. Zero dependencies.

[![PyPI version](https://img.shields.io/pypi/v/draftedi)](https://pypi.org/project/draftedi/)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![MIT license](https://img.shields.io/badge/license-MIT-green)
[![CI](https://github.com/yawway365/draftedi-core/actions/workflows/ci.yml/badge.svg)](https://github.com/yawway365/draftedi-core/actions/workflows/ci.yml)

draftedi handles ANSI X12 only (not EDIFACT).

## Install

```
pip install draftedi
```

## Parse

```python
from draftedi import parse_edi_file

raw = (
    b"ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
    b"*260222*1200*^*00501*000000001*0*P*>~"
    b"GS*PO*SENDER*RECEIVER*20260222*1200*1*X*005010~"
    b"ST*850*0001~"
    b"BEG*00*NE*PO-001**20260222~"
    b"N1*BY*Buyer Company*92*BUYERID~"
    b"PO1*1*10*EA*25.00**BP*ITEM001~"
    b"CTT*1~"
    b"SE*6*0001~"
    b"GE*1*1~"
    b"IEA*1*000000001~"
)
# or from a file: raw = open("sample.edi", "rb").read()

parsed = parse_edi_file(raw, source="example")

for interchange in parsed["interchanges"]:
    print(interchange["isa_sender_id"])   # "SENDER         " (ISA fields keep their padding)
    print(interchange["element_sep"])     # "*"
    for group in interchange["groups"]:
        for transaction in group["transactions"]:
            for segment in transaction["segments"]:
                print(segment["segment_id"])  # "BEG", "N1", "PO1", "CTT" (ST and SE are not listed)
```

`parse_edi_file` takes `bytes` (decoded as UTF-8 with `errors="replace"`) and returns plain `TypedDict` / `dict` instances. Index them with string keys.

Separators are read from each ISA header. `repetition_sep` and `component_sep` can be `None`:

- `repetition_sep` is `None` when ISA12 is earlier than `00402` (ISA11 is then the Interchange Control Standards Identifier, usually `U`), when ISA12 is not five digits, or when ISA11 is blank, a letter or digit, or the same character as another delimiter.
- `component_sep` is `None` when ISA16 is blank.

## Validate

`validate_edi()` takes the raw document as `str` or `bytes`.

```python
from draftedi import validate_edi

result = validate_edi(raw)
print(result.is_valid)   # None: no spec data, so validity is not determined
print(result.errors)     # []: the envelope checks found nothing
print(result.warnings)   # ['No spec_provider supplied. Structural checks only. ...']
```

Without spec data, only the envelope is checked. Envelope findings are errors, so `errors` can be non-empty while `is_valid` is `None`. **Check `errors`, not only `is_valid`:**

```python
if result.errors:
    print("invalid")       # at least one error, whatever is_valid says
elif result.is_valid:
    print("valid")         # checked against a spec, no errors
else:
    print("not determined")  # is_valid is None and no errors: only the envelope was checked
```

### ValidationResult

`validate_edi()` and `X12Validator.validate_transaction()` return a `ValidationResult` dataclass.

| Field | Type | Notes |
|---|---|---|
| `is_valid` | `Optional[bool]` | See below |
| `errors` | `list[ValidationError]` | Every finding. All findings are errors. |
| `warnings` | `list[str]` | Advisory notes only, such as `"No spec found ..."`. They never affect `is_valid`. |
| `spec_provider` | `Optional[str]` | Class name of the spec provider used, or `None` |

| `is_valid` | When |
|---|---|
| `True` | A spec matched and `errors` is empty. |
| `False` | A spec matched and `errors` is not empty (envelope errors included), or the text could not be parsed (`PARSE_ERROR`). |
| `None` | Not determined: no `spec_provider`, the provider has no spec for the document's version and transaction set, no functional group or transaction set was found, or validation stopped with `SPEC_ERROR` or `INTERNAL_ERROR`. `errors` can still hold findings such as `ENVELOPE_ERROR`. |

`ValidationError` is a dataclass:

| Field | Type | Notes |
|---|---|---|
| `segment_id` | `str` | `""` for `PARSE_ERROR`, `SPEC_ERROR` and `INTERNAL_ERROR` |
| `element_pos` | `Optional[int]` | 1-based element position, or `None` for a segment-level finding |
| `error_type` | `str` | See [Error types](#error-types) |
| `value` | `Optional[str]` | The element value for `TYPE_ERROR`, `INVALID_LENGTH` and `INVALID_CODE`; otherwise `None` |
| `message` | `str` | Human-readable description |

### What validate_edi() checks

`validate_edi()` validates the first interchange, functional group and transaction set in the text.

Always, with or without spec data (envelope):

- IEA01 against the number of functional groups, IEA02 against ISA13
- GE01 against the number of transaction sets, GE02 against GS06
- SE01 against the number of segments (ST and SE included), SE02 against ST02
- a missing SE, GE or IEA trailer, and counts that are not numeric

Numeric control numbers (ISA13/IEA02, GS06/GE02) are compared by value, so `000000001` matches `1`. ST02/SE02 are compared as text.

With a spec for the document's version (GS08) and transaction set (ST01), it also runs `X12Validator`:

- mandatory segments (a mandatory segment inside a loop is required only when the loop occurs)
- segment maximum use, counted per loop iteration
- mandatory elements that are missing or empty
- element data type, length, and code values
- relational conditions P, R, E, C and L

### Errors and exceptions

`validate_edi()` does not raise for any input. A parse failure returns `is_valid=False` with a `PARSE_ERROR`. An exception from the spec provider (for example, a malformed skeleton file) returns `is_valid=None` with a `SPEC_ERROR`, and any other unexpected failure returns `is_valid=None` with an `INTERNAL_ERROR`; findings made before the failure are kept. Only exceptions that do not derive from `Exception`, such as `KeyboardInterrupt`, propagate.

The other functions can raise:

| Function | Raises |
|---|---|
| `parse_edi_file()` | `ValueError` when the input is not X12: it does not start with `ISA` (including input that starts with a UTF-8 byte order mark), the ISA header is shorter than 106 characters, `GS` comes before `ISA`, `ST` before `GS`, or `SE` appears outside a transaction set. Also `ValueError` when SE01 has more than 4,300 digits (Python's limit on converting strings to `int`). |
| `parse_interchange()` | `ValueError` when the text does not start with `ISA` or is shorter than 106 characters. |
| `X12Validator.validate_transaction()` | Any exception the spec provider raises; `KeyError` for a malformed transaction dict, such as a segment without `segment_id`. |
| `JSONSkeletonSpecProvider` methods | `json.JSONDecodeError`, `UnicodeDecodeError` or `OSError` for a spec file that cannot be read or parsed; `KeyError`, `TypeError` or `AttributeError` for a skeleton missing required fields or with the wrong structure. |

## Error types

| `error_type` | Needs a spec | Meaning |
|---|---|---|
| `ENVELOPE_ERROR` | No | An SE, GE or IEA trailer disagrees with its envelope: the count is wrong or not numeric (`element_pos` 1), the control number differs from ST02, GS06 or ISA13 (`element_pos` 2), or the trailer is missing (`element_pos` `None`). `X12Validator` checks SE only. |
| `MISSING_MANDATORY` | Yes | A mandatory segment is missing (`element_pos` `None`), or a mandatory element is missing or empty (`element_pos` set). |
| `MAX_USE_EXCEEDED` | Yes | A segment occurs more often than its maximum use within one loop iteration. |
| `RELATIONAL_CONDITION` | Yes | A P, R, E, C or L relational condition is violated. |
| `TYPE_ERROR` | Yes | A value does not match its data type (N, N0 to N9, R, DT or TM). |
| `INVALID_LENGTH` | Yes | A value is shorter than the minimum or longer than the maximum length. |
| `INVALID_CODE` | Yes | An ID value is not in the provider's code list. |
| `PARSE_ERROR` | No | `validate_edi()` only. The text could not be parsed. `is_valid` is `False`. |
| `SPEC_ERROR` | No | `validate_edi()` only. The spec provider raised an exception. `is_valid` is `None`. |
| `INTERNAL_ERROR` | No | `validate_edi()` only. An unexpected failure in draftedi's own checks. `is_valid` is `None`. |

## Spec data (bring your own spec)

draftedi ships without X12 spec data: the ASC X12 standards are copyrighted and cannot be bundled. Spec-aware validation uses data you supply through a spec provider.

### JSONSkeletonSpecProvider

Loads structural-only JSON skeleton files from a directory you supply.

```python
from draftedi import validate_edi
from draftedi.spec import JSONSkeletonSpecProvider

provider = JSONSkeletonSpecProvider("path/to/specs/")   # a leading "~" is expanded
result = validate_edi(raw, spec_provider=provider)

print(result.is_valid)        # True or False when a spec file matched, None when none did
print(result.spec_provider)   # "JSONSkeletonSpecProvider"
for err in result.errors:
    print(err.segment_id, err.element_pos, err.error_type, err.message)
```

- Files are named `{version}-{tsid}.json`. `{version}` is GS08 exactly as it appears in the document (for example `005010`, or `005010X222A1` for an 837 that uses an implementation guide) and `{tsid}` is ST01 (for example `850`).
- GS08 must be 1 to 12 letters or digits and ST01 exactly 3 letters or digits. When either is not, or no file matches, the provider returns `None` and `validate_edi()` reports `is_valid=None` with a warning.
- Loaded files are cached per provider instance. Create a new instance after changing a file.
- Skeleton files contain no names: `element_name`, `segment_name` and `transaction_set_name` are always `None`.

See [specs/README.md](https://github.com/yawway365/draftedi-core/blob/main/specs/README.md) for the file format.

### Your own provider

Any object with these four methods satisfies the `X12SpecProvider` protocol. No inheritance is needed. For example, a provider that serves specs from a dict:

```python
from typing import Optional

from draftedi.spec import SegmentSpec, TransactionSetSpec


class DictSpecProvider:
    def __init__(self, specs: dict[tuple[str, str], TransactionSetSpec]) -> None:
        self._specs = specs  # keyed by (GS08 version, ST01 transaction set ID)

    def get_transaction_set(
        self, version: str, transaction_set_id: str
    ) -> Optional[TransactionSetSpec]:
        return self._specs.get((version, transaction_set_id))

    def get_element_codes(self, version: str, element_id: str) -> list[str]:
        return []  # no code lists: code values are not checked

    def get_segment_spec(self, version: str, segment_id: str) -> Optional[SegmentSpec]:
        return None

    def get_available_versions(self) -> list[str]:
        return sorted({version for version, _ in self._specs})


result = validate_edi(raw, spec_provider=DictSpecProvider({}))
print(result.is_valid)   # None: this provider has no spec for 005010/850
```

`X12Validator` calls `get_transaction_set()` and `get_element_codes()`. The `TypedDict` definitions (`TransactionSetSpec`, `SegmentSpec`, `ElementSpec`, `RelationalCondition`) are in [`draftedi/spec/protocol.py`](https://github.com/yawway365/draftedi-core/blob/main/src/draftedi/spec/protocol.py).

### X12Validator

`validate_edi()` validates only the first transaction set. To validate every transaction set, parse the file and call `X12Validator.validate_transaction()` on each one:

```python
from draftedi import X12Validator, parse_edi_file

validator = X12Validator(provider)
for interchange in parse_edi_file(raw)["interchanges"]:
    for group in interchange["groups"]:
        for transaction in group["transactions"]:
            result = validator.validate_transaction(transaction, version=group["x12_release"] or "")
            print(transaction["control_number"], result.is_valid, result.errors)
```

`X12Validator` checks the SE trailer of each transaction set but not the GE and IEA trailers, and it does not catch exceptions (see [Errors and exceptions](#errors-and-exceptions)).

## What is not checked

- `validate_edi()` validates only the first interchange, functional group and transaction set. Use `X12Validator` for the others (their GE and IEA trailers are then not checked).
- Segments that the spec does not define, elements beyond those the spec defines, and segment order are not reported.
- Composite elements: component values are not checked for data type, length or code values. A composite counts as present in mandatory and relational checks when any component has data.
- Data types: only N, N0 to N9, R, DT and TM values are checked. AN values are not checked against the X12 character set, and ID values only against code lists.
- Element requirements other than M (for example X) are not enforced; conditional requirements come only from relational conditions.
- Loop repeat limits (`loop_repeat`) are not checked.
- `X12Validator` flattens nested loops when it converts a spec: loops that share a loop ID cannot be told apart for element rules or maximum use, and a parent-loop segment that follows a nested loop is treated as outside any loop (so a mandatory one can be reported missing).
- Code values are checked only for ID elements whose spec has `repetition_count` greater than 0, and code lists are looked up by element ID, not by segment and position.
- A skeleton JSON file can define each segment ID only once per transaction set, so a segment used in two places (for example N1 in the heading and in the PO1 loop) has one definition.
- `validate_edi()` reports an unexpected failure inside `X12Validator` as `SPEC_ERROR`, not `INTERNAL_ERROR`.

## Lower-level functions

All functions below are importable from `draftedi` and from `draftedi.validate`. They take `parse_edi_file()` output, spec dicts or plain values, and return `ValidationIssue` dicts or message strings.

### Without spec data

```python
from draftedi.validate import check_element_data_type, check_element_length, check_envelope

transaction = parsed["interchanges"][0]["groups"][0]["transactions"][0]

# SE01 segment count, SE02 against ST02, and a missing SE
issues = check_envelope(transaction, transaction["segments"])
print(issues)   # []: list[ValidationIssue]

print(check_element_data_type("20260222", "DT", "BEG05"))   # None (valid)
print(check_element_data_type("20260230", "DT", "BEG05"))   # Element BEG05: invalid date '20260230'
print(check_element_length("PO-001", 1, 22))                # None (valid)
```

`check_relational_conditions()` checks one segment. Pass the conditions and a map of element position to value:

```python
from draftedi.validate import check_relational_conditions

# P (paired): if N103 or N104 is present, both must be
rc_list = [
    {"transaction_set_segment_rc_type": "P", "transaction_set_segment_rc_elements": ["3", "4"]},
]
val_by_pos = {1: "BY", 2: "Buyer Company", 3: "92"}

issues = check_relational_conditions("N1", rc_list, val_by_pos)
print(issues[0]["message"])
# Paired condition: if any of (N103,N104) is present, all must be present. Missing: N104
```

### With spec data

These functions take spec data as nested dicts: segment entries with `segment_id`, `segment_requirement` and `segment_maximum_use`, and loop entries `{"type": "loop", "loop_id": ..., "segments": [...]}` whose first segment starts the loop. Nested loops are supported.

```python
from draftedi.validate import (
    assign_loop_paths,
    build_nav_tree,
    check_mandatory_segments,
    check_segment_max_use,
)

spec_segments = [
    {"segment_id": "BEG", "segment_requirement": "M", "segment_maximum_use": 1},
    {
        "type": "loop",
        "loop_id": "N1",
        "segments": [
            {"segment_id": "N1", "segment_requirement": "M", "segment_maximum_use": 1},
        ],
    },
    {
        "type": "loop",
        "loop_id": "PO1",
        "segments": [
            {"segment_id": "PO1", "segment_requirement": "M", "segment_maximum_use": 1},
            {
                "type": "loop",
                "loop_id": "PID",
                "segments": [
                    {"segment_id": "PID", "segment_requirement": "O", "segment_maximum_use": 1},
                ],
            },
        ],
    },
    {"segment_id": "CTT", "segment_requirement": "O", "segment_maximum_use": 1},
]

root = build_nav_tree(spec_segments)
loop_assignments = assign_loop_paths(transaction["segments"], root)
print([(seg["segment_id"], path) for seg, path in loop_assignments])
# [('BEG', None), ('N1', 'N1'), ('PO1', 'PO1'), ('CTT', None)]

print(check_mandatory_segments(loop_assignments, spec_segments))   # []
print(check_segment_max_use(loop_assignments, spec_segments))      # []
```

## API reference

Signatures are as in the source. `X12SpecProvider` is shown above.

### Parser (`draftedi`, `draftedi.parser`)

- `parse_edi_file(raw_bytes: bytes, source: str = "manual upload") -> ParsedFile`: parses a document into interchanges, groups, transaction sets, segments, elements and components.
- `parse_interchange(x12_text: str) -> SeparatorInfo`: reads the separators from the first ISA header.

### Validation (`draftedi`)

- `validate_edi(edi_text: Union[str, bytes], spec_provider: Optional[X12SpecProvider] = None) -> ValidationResult`: see [Validate](#validate).
- `X12Validator(spec_provider: X12SpecProvider)`, with `validate_transaction(parsed_transaction: Mapping[str, Any], version: str) -> ValidationResult`. Also in `draftedi.validator`.
- `JSONSkeletonSpecProvider(specs_dir: Union[str, Path])`: import from `draftedi.spec`.
- `MissingSpecError`: a `ValueError` subclass exported for API compatibility. No draftedi function raises it.

### Check functions (`draftedi`, `draftedi.validate`)

- `check_envelope(transaction: Mapping[str, Any], parsed_segments: list[Any]) -> list[ValidationIssue]`: compares SE01 with `len(parsed_segments) + 2`. When `transaction` has `raw_se_segment` (as `parse_edi_file()` output does), also reports an SE02 that differs from ST02, a missing SE and a non-numeric SE01.
- `check_element_data_type(value: str, element_type: str, element_id: str) -> Optional[str]`: checks N and N0 to N9 (ASCII digits, optional leading minus), R (decimal), DT (CCYYMMDD or YYMMDD, calendar-aware) and TM (HHMM, HHMMSS, HHMMSSd or HHMMSSdd). Returns an error message, or `None` when the value is valid, empty, or of another type.
- `check_element_length(value: str, min_length: int | str, max_length: int | str) -> Optional[str]`: returns an error message, or `None`. An empty value passes; a `max_length` of 0 means no maximum.
- `check_relational_conditions(seg_id: str, rc_list: list[dict[str, Any]], val_by_pos: dict[int, str]) -> list[ValidationIssue]`: checks P (paired), R (required), E (exclusion), C (conditional) and L (list conditional) conditions for one segment.
- `build_nav_tree(spec_segments: list[Any]) -> LoopEntry`: builds the loop navigation tree used by `assign_loop_paths`.
- `assign_loop_paths(parsed_segments: list[Any], root: LoopEntry) -> list[tuple[dict[str, Any], Optional[str]]]`: returns each segment with its loop path, such as `"PO1/PID"`, or `None` outside any loop.
- `build_spec_lookup(spec_segments: list[Any], parent_loop_id: Optional[str] = None) -> dict[tuple[str, Optional[str]], dict[str, Any]]`: flattens the spec into a `(segment_id, loop_id) -> spec dict` lookup. The first entry for a key wins.
- `check_mandatory_segments(loop_assignments: list[tuple[dict[str, Any], Optional[str]]], spec_segments: list[Any]) -> list[ValidationIssue]`: reports missing M segments. A mandatory segment in a loop is required only when that loop occurs.
- `check_segment_max_use(loop_assignments: list[tuple[dict[str, Any], Optional[str]]], spec_segments: list[Any]) -> list[ValidationIssue]`: reports segments that exceed their maximum use within one loop iteration. A maximum use of 0 means no limit.
- `leaf_loop(loop_path: Optional[str]) -> Optional[str]`: returns the innermost loop ID (`"PO1/N1"` gives `"N1"`), or `None` for `None` or `""`.
- `make_issue(severity: str, category: str, segment_id: Optional[str], segment_position: Optional[int], element_pos: Optional[int], message: str) -> ValidationIssue`: builds a `ValidationIssue`.

### Parser types

- **`ParsedFile`**: `file_hash`, `processed_at`, `filename`, `source`, `interchanges`.
- **`Interchange`**: one ISA/IEA envelope. Includes `isa_sender_id`, `isa_receiver_id`, `isa_control_number`, `version` (ISA12), `element_sep`, `component_sep`, `repetition_sep`, `segment_term`, `raw_isa`, `groups`.
- **`FunctionalGroup`**: one GS/GE envelope. Includes `functional_id_code`, `gs_sender_id`, `gs_receiver_id`, `group_control_number`, `x12_release` (GS08), `transactions`.
- **`Transaction`**: one ST/SE envelope. Includes `transaction_set_id`, `control_number` (ST02), `segment_count_reported` (SE01 as `int`, or `None` when SE is missing or SE01 is not digits), `raw_se_segment`, `segments` (without ST and SE).
- **`Segment`**: `position`, `segment_id`, `loop_path` (always `None` from the parser; see `assign_loop_paths`), `raw_segment`, `elements`.
- **`Element`**: `element_pos`, `value_text` (`None` for a composite), `is_composite`, `present`, `repetition_index`, `components`. A repeated element gives one `Element` per repetition, all with the same `element_pos`.
- **`Component`**: `component_pos`, `value_text`.
- **`SeparatorInfo`**: `element_sep`, `segment_term`, `repetition_sep`, `component_sep`, `raw_isa`, `isa_parts`.

### Validator types

**`ValidationIssue`**, a `TypedDict` returned by the check functions:

| Field | Type | Description |
|---|---|---|
| `severity` | `str` | `"error"` for every issue from the built-in checks |
| `category` | `str` | From the built-in checks: `"envelope"`, `"mandatory_segment"`, `"segment_max_use"` or `"relational_condition"` |
| `segment_id` | `Optional[str]` | Segment the issue is about |
| `segment_position` | `Optional[int]` | `None` in issues from the built-in checks |
| `element_pos` | `Optional[int]` | Element position, if the issue is about one element |
| `message` | `str` | Human-readable description |

`X12Validator` and `validate_edi()` turn issues with severity `"error"` into `ValidationError`s and add the message of any other issue to `warnings`.

**`SegEntry`**: a segment in the navigation tree (`segment_id`, `spec_dict`).

**`LoopEntry`**: a loop in the navigation tree. Fields: `loop_id`, `trigger_id` (the segment ID that starts the loop), `children`, `valid_seg_ids`.

### Import paths

```python
from draftedi import validate_edi, X12Validator, ValidationResult, ValidationError, X12SpecProvider
from draftedi.spec import JSONSkeletonSpecProvider, TransactionSetSpec, SegmentSpec, ElementSpec
from draftedi.validator import X12Validator, ValidationResult, ValidationError
```

## Development

```
pip install -e ".[dev]"
pytest
ruff check src tests
ruff format --check src tests
mypy src
```

The `dev` extra installs the `test` extra (pytest and plugins) and the `lint` extra (ruff and mypy, pinned to the versions CI uses; on Python 3.9 it installs mypy 1.19.1, the last release that runs there).

## Contributing

Contributions are welcome. Code changes need a Contributor License Agreement; doc fixes and changes of 15 lines or fewer don't. See [CONTRIBUTING.md](https://github.com/yawway365/draftedi-core/blob/main/CONTRIBUTING.md). Changes are listed in [CHANGELOG.md](https://github.com/yawway365/draftedi-core/blob/main/CHANGELOG.md).

## License

MIT. See [LICENSE](https://github.com/yawway365/draftedi-core/blob/main/LICENSE).
