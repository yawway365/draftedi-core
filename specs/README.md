# Skeleton Spec Files — BYOS (Bring Your Own Spec)

`JSONSkeletonSpecProvider` reads structural-only X12 specification files
("skeletons") from a directory you supply. draftedi ships no spec files and no
tool to generate them.

## What Skeleton Spec Files Are

Skeleton spec files encode the structural grammar of an X12 transaction set:

- Which segments are present and their requirement (mandatory/optional)
- Maximum use counts per segment
- Loop structure (loop ID, nesting level, repeat limits)
- Element data types, min/max lengths, and requirement
- Relational conditions (P/R/E/C/L rules between elements)

**What is intentionally absent:**
- Segment names (e.g., "Health Care Claim") — copyrighted ASC X12 expression
- Element names (e.g., "Entity Identifier Code") — copyrighted ASC X12 expression
- Code descriptions (e.g., "PT" = "Patient") — potentially copyrighted

This keeps `draftedi-core` copyright-clean: the library contains no X12 spec
content, and the provider returns `None` for `segment_name`, `element_name` and
`transaction_set_name`.

## Writing Skeleton Files

Write skeleton files yourself from X12 data you are licensed to use, keeping
only the structural facts listed above. Code values you add (see
[Code Value Validation](#code-value-validation)) are governed by the license of
the data they come from.

## File Naming Convention

Files are named `{version}-{tsid}.json`:

- `{version}` is GS08 exactly as it appears in the document: 1 to 12 letters or
  digits, such as `005010`, `004010`, or `005010X222A1` for an 837 sent under an
  implementation guide.
- `{tsid}` is ST01: exactly 3 letters or digits, such as `850`.

For example, `005010-850.json` or `004010-810.json`. When no file matches, or
GS08 or ST01 is not in this format, the provider returns `None` and
`validate_edi()` reports `is_valid=None` with a warning.

## JSON Format

Each file has two top-level keys, `_meta` and `segments`:

```json
{
  "_meta": {
    "format": "draftedi-skeleton-spec",
    "format_version": "1.0",
    "x12_version": "005010",
    "transaction_set_id": "850",
    "functional_group_id": "PO",
    "generated_at": "2026-02-21T00:00:00Z",
    "data_source": "user-supplied",
    "includes_codes": false
  },
  "segments": {
    "BEG": {
      "seq": 20,
      "area": "HEADING",
      "req": "M",
      "max_use": 1,
      "loop": null,
      "loop_level": 0,
      "loop_repeat": 1,
      "elements": [
        { "pos": 1, "element_id": "353", "req": "M", "type": "ID", "min": 2, "max": 2, "repeat": 1, "codes": [] }
      ],
      "relational_conditions": []
    },
    "N1": {
      "seq": 310,
      "area": "HEADING",
      "req": "O",
      "max_use": 1,
      "loop": "N1",
      "loop_level": 1,
      "loop_repeat": 200,
      "elements": [
        { "pos": 1, "element_id": "98", "req": "M", "type": "ID", "min": 2, "max": 3, "repeat": 1, "codes": [] },
        { "pos": 3, "element_id": "66", "req": "X", "type": "ID", "min": 1, "max": 2, "repeat": 1, "codes": [] },
        { "pos": 4, "element_id": "67", "req": "X", "type": "AN", "min": 2, "max": 80, "repeat": 1, "codes": [] }
      ],
      "relational_conditions": [
        { "type": "P", "positions": [3, 4] }
      ]
    }
  }
}
```

### `_meta`

| Key | Required | Notes |
|---|---|---|
| `transaction_set_id` | Yes | Returned as `TransactionSetSpec["transaction_set_id"]` |
| `functional_group_id` | Yes | Returned as `TransactionSetSpec["functional_group_id"]` |
| `format`, `format_version`, `x12_version`, `generated_at`, `data_source`, `includes_codes` | No | Not read by the provider. Use them for your own records. |

### `segments`

An object keyed by segment ID, listed in transaction-set order. The provider
keeps the order of the keys; `seq` is not used for ordering.

| Key | Required | Notes |
|---|---|---|
| `req` | Yes | `"M"` segments are checked for presence |
| `max_use` | Yes | Maximum use within one loop iteration; `0` means no limit |
| `loop` | No | Loop ID, or `null` (or absent) outside any loop. The first segment listed with a loop ID starts that loop. |
| `loop_level` | Yes | Read but not used: nested loops are flattened (see [Limitations](#limitations)) |
| `loop_repeat` | Yes | Read but not checked |
| `seq`, `area` | Yes | Read but not used |
| `elements` | Yes | List of element entries (below) |
| `relational_conditions` | No | List of `{"type": "P", "positions": [3, 4]}` entries; `type` is P, R, E, C or L and `positions` are 1-based element positions |

### `elements`

| Key | Required | Notes |
|---|---|---|
| `pos` | Yes | 1-based position in the segment |
| `element_id` | Yes | Element reference number; code lists are looked up by it |
| `req` | Yes | `"M"` elements must be present and not empty. Other values are not enforced. |
| `type` | Yes | N, N0 to N9, R, DT and TM values are checked. AN and ID values are not checked for content (ID values are checked against `codes`). |
| `min`, `max` | Yes | Length bounds; a `max` of `0` means no maximum |
| `repeat` | Yes | Codes are checked only when this is greater than `0` |
| `codes` | No | Allowed values for an ID element |

A file missing a required key makes the provider raise `KeyError` or
`TypeError`; `validate_edi()` reports that as a `SPEC_ERROR`.

## Using the Files

Place the files in a directory and point `JSONSkeletonSpecProvider` at it:

```python
from draftedi import validate_edi
from draftedi.spec import JSONSkeletonSpecProvider

provider = JSONSkeletonSpecProvider("~/.draftedi/specs/")   # a leading "~" is expanded
with open("order.edi", "rb") as f:
    result = validate_edi(f.read(), spec_provider=provider)
print(result.is_valid, result.errors)
```

The provider caches each file the first time it loads it. Create a new provider
after changing a file.

## Code Value Validation

To check an ID element's values, list them in its `codes` array. Codes are
checked when all of these hold:

- the element's `type` is `ID`
- its `repeat` is greater than `0`
- the provider returns a non-empty code list for its `element_id`

`includes_codes` in `_meta` is not read.

Code lists are looked up by element ID, not by segment and position. The
provider returns the first non-empty `codes` array for that element ID among
the files of the same version it has loaded. An element with an empty `codes`
array is therefore still checked when the same element ID has codes elsewhere,
so give an element ID the same code list everywhere it appears.

## Limitations

- `segments` is keyed by segment ID, so each segment ID can be defined only
  once per transaction set. A segment used in two places (for example N1 in the
  heading and in the PO1 loop) gets one definition.
- `X12Validator` flattens nested loops: `loop_level` is ignored, every loop is
  treated as a top-level loop, and a parent-loop segment that follows a nested
  loop is treated as outside any loop.
- `loop_repeat` is not checked.

The README lists [what draftedi does not check](https://github.com/yawway365/draftedi-core/blob/main/README.md#what-is-not-checked).

## Reference

- [`JSONSkeletonSpecProvider`](https://github.com/yawway365/draftedi-core/blob/main/src/draftedi/spec/json_skeleton_provider.py)
- [`X12SpecProvider` and the spec `TypedDict`s](https://github.com/yawway365/draftedi-core/blob/main/src/draftedi/spec/protocol.py)
