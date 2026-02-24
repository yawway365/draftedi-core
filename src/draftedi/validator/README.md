# draftedi.validator

X12 transaction validation class interface over the existing validate.py check functions.

## Architecture

X12Validator is a thin delegation layer. No check logic lives here.
All validation is performed by calling validate.py functions directly. (ref: DL-001)

```
X12Validator.validate_transaction()
  -> _check_envelope()        -> validate.check_envelope()
  -> _check_mandatory_segments() -> validate.check_mandatory_segments()
  -> _check_segment_max_use() -> validate.check_segment_max_use()
  -> _check_element_types()   -> validate.check_element_data_type() / check_element_length()
  -> _check_relational_conditions() -> validate.check_relational_conditions()
```

## Spec Conversion

validate.py functions expect a hierarchical dict format where loop segments are nested
under `{type: loop, ...}` entries. TransactionSetSpec.segments is a flat list.

`_spec_to_hierarchical()` translates the flat list to the hierarchical format before
each check call. Key name mapping (SegmentSpec -> validate.py internal): (ref: DL-002, R-002)

| SegmentSpec key       | validate.py internal key                      |
| --------------------- | --------------------------------------------- |
| requirement           | segment_requirement                           |
| max_use               | segment_maximum_use                           |
| condition_type        | transaction_set_segment_rc_type               |
| element_positions     | transaction_set_segment_rc_elements (str list)|

Segments with `loop_id != None` are collected into nested loop dicts. Loop order
preserves first-seen order from the flat list. (ref: R-001)

## ValidationResult Semantics

| is_valid | Meaning                                              |
| -------- | ---------------------------------------------------- |
| None     | No spec found for version/ts_id; envelope check only |
| True     | All five checks passed with a matched spec           |
| False    | One or more errors detected, or parse failure        |

`is_valid=None` is the indeterminate state — not valid, not invalid. Never raises
MissingSpecError on the spec-absent path. (ref: DL-003)

## Error Type Mapping

ValidationError.error_type is derived from ValidationIssue.category: (ref: DL-005)

| category            | error_type           |
| ------------------- | -------------------- |
| mandatory_segment   | MISSING_MANDATORY    |
| segment_max_use     | MAX_USE_EXCEEDED     |
| relational_condition| RELATIONAL_CONDITION |
| element_type        | TYPE_ERROR           |
| element_length      | INVALID_LENGTH       |
| element_code        | INVALID_CODE         |
| envelope            | MISSING_MANDATORY    |

## Architectural Note: Class-vs-Function Convention (Cat-2)

draftedi-core uses a function-based module convention for all other submodules.
X12Validator is a class, which conflicts with that convention.

This tension is documented in edi_db_decouple.md as a Category-2 deferred
decision. The class form was chosen for Sprint 2 because it aligns with the
task-board specification and allows per-instance spec_provider injection.
Resolution (refactor to function-based or formalize the class exception) is
deferred to Sprint 3. Future maintainers encountering this inconsistency
should consult edi_db_decouple.md before normalizing it.
