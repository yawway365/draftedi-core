# Skeleton Spec Files — BYOS (Bring Your Own Spec)

This directory holds structural-only X12 specification files for use with
`JSONSkeletonSpecProvider`. These files contain structural facts only — no
copyrighted element names, segment descriptions, or code content.

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

This design keeps `draftedi-core` copyright-clean while enabling ~85–90% of
structural validation value from the skeleton alone.

## File Naming Convention

Files are named `{version}-{tsid}.json`, for example:

- `005010-850.json` — X12 005010 Purchase Order (850)
- `005010-837.json` — X12 005010 Health Care Claim (837)
- `004010-810.json` — X12 004010 Invoice (810)

## JSON Format Overview

Each file has two top-level keys:

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
      "seq": 10,
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
    }
  }
}
```

## BYOS Workflow

Users who hold an X12 subscription can self-generate complete skeleton files
from their own licensed X12 databases:

1. Use `build_skeleton.py` (available in the private `draftedi` repo, Sprint 3)
   to export structural facts from your licensed X12 SQLite database.
2. Place the generated `{version}-{tsid}.json` files in a local directory.
3. Point `JSONSkeletonSpecProvider` at that directory:

```python
from draftedi.spec import JSONSkeletonSpecProvider
from draftedi import validate_edi

provider = JSONSkeletonSpecProvider("~/.draftedi/specs/")
result = validate_edi(edi_text, spec_provider=provider)
print(result.is_valid, result.errors)
```

## Code Value Validation

Set `includes_codes: true` in `_meta` and populate `codes` arrays in element
entries to enable element code value validation. When `codes` is empty,
the validator skips code checking for that element.

The `build_skeleton.py --include-codes` flag populates code values from your
licensed database. Code values you generate this way are governed by your own
X12 license agreement.

## Reference

- `build_skeleton.py` — available in the private `draftedi` repository (Sprint 3)
- `JSONSkeletonSpecProvider` — `src/draftedi/spec/json_skeleton_provider.py`
- Architecture spec — `edi_db_decouple.md §6`
