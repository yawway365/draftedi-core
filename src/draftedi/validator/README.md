# draftedi.validator

`X12Validator`, `ValidationResult` and `ValidationError`: a class interface
over the check functions in `validate.py`.

## Architecture

`X12Validator.validate_transaction()` runs six checks:

```
X12Validator.validate_transaction()
  1. envelope (no spec needed)  -> validate.check_envelope()
  2. mandatory segments         -> validate.check_mandatory_segments()
  3. segment maximum use        -> validate.check_segment_max_use()
  4. mandatory elements         -> X12Validator._check_mandatory_elements()
  5. element type, length, code -> validate.check_element_data_type(), validate.check_element_length(),
                                   spec_provider.get_element_codes()
  6. relational conditions      -> validate.check_relational_conditions()
```

The envelope check runs first. When the provider returns no spec for the
version and transaction set ID, validation stops there with `is_valid=None`.

Checks 4 to 6 pair each parsed segment with the `SegmentSpec` of the loop
`assign_loop_paths()` placed it in, keyed by `(segment_id, loop_id)`. A segment
placed outside every loop that defines it falls back to the first spec entry
with its ID. Check 5 skips composite elements (their `value_text` is `None`)
and checks codes only for ID elements whose `repetition_count` is greater
than 0.

`X12Validator` is a class, while the rest of the package is function-based, so
that a spec provider can be bound to an instance.

## Spec Conversion

The `validate.py` functions take spec data as nested dicts, with loop segments
under `{"type": "loop", "loop_id": ..., "segments": [...]}` entries.
`TransactionSetSpec["segments"]` is a flat list. `_spec_to_hierarchical()`
converts it before each check and renames keys:

| SegmentSpec key | validate.py key |
| --------------- | --------------- |
| `requirement` | `segment_requirement` |
| `max_use` | `segment_maximum_use` |
| `elements` | `segment_elements` |
| `relational_conditions` | `segment_relational_conditions` |
| `condition_type` (relational condition) | `transaction_set_segment_rc_type` |
| `element_positions` (relational condition) | `transaction_set_segment_rc_elements` (list of str) |

Each distinct `loop_id` becomes one loop at the top level, in first-seen order;
segments without a `loop_id` are placed before all loops. `loop_level` is not
used, so nested loops are flattened: loops that share a loop ID cannot be told
apart, and a parent-loop segment that follows a nested loop is placed outside
any loop. `loop_repeat` is not checked.

## ValidationResult Semantics

| is_valid | Meaning |
| -------- | ------- |
| None | No spec for the version and transaction set; only the envelope was checked. `errors` can still hold `ENVELOPE_ERROR`. (`validate_edi()` also returns `None` without a provider, when no group or transaction set is found, and with `SPEC_ERROR` or `INTERNAL_ERROR`.) |
| True | A spec matched and there are no errors. |
| False | A spec matched and there is at least one error. (`validate_edi()` also returns `False` with `PARSE_ERROR`.) |

Findings are routed by severity: issues with severity `"error"` become
`ValidationError` entries in `errors`; the message of any other issue goes to
`warnings`. No built-in check produces a non-error issue, so `warnings` holds
only advisory notes such as "No spec found ...". `MissingSpecError` is never
raised.

## Error Type Mapping

`ValidationIssue` dicts from `validate.py` become `ValidationError`s with
`error_type` taken from the issue's `category`:

| category | error_type |
| -------- | ---------- |
| envelope | ENVELOPE_ERROR |
| mandatory_segment | MISSING_MANDATORY |
| segment_max_use | MAX_USE_EXCEEDED |
| relational_condition | RELATIONAL_CONDITION |
| element_type | TYPE_ERROR |
| element_length | INVALID_LENGTH |
| element_code | INVALID_CODE |
| any other | TYPE_ERROR |

Checks 4 and 5 build `ValidationError`s directly: `MISSING_MANDATORY` with
`element_pos` set, `TYPE_ERROR`, `INVALID_LENGTH` and `INVALID_CODE`.
`validate_edi()` adds `PARSE_ERROR`, `SPEC_ERROR` and `INTERNAL_ERROR`.

## Exceptions

`validate_transaction()` does not catch exceptions. Anything the spec provider
raises propagates, and a malformed transaction dict raises (for example
`KeyError` for a segment without `segment_id`). `validate_edi()`, which builds
the transaction dict itself, reports any exception from `validate_transaction()`
as `SPEC_ERROR`.
