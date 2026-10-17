# draftedi.spec

Protocol and TypedDict contracts for X12 specification data, and the built-in
JSON skeleton provider.

## BYOS — Bring Your Own Spec

draftedi cannot bundle copyrighted X12 specification data. `X12SpecProvider` is
a `typing.Protocol` that defines the interface a spec source must satisfy. Pass
a conforming object to `validate_edi()` or `X12Validator` for spec-aware
validation; no inheritance is needed.

`JSONSkeletonSpecProvider` is the built-in implementation. It reads
`{version}-{tsid}.json` skeleton files from a directory you supply; see
[specs/README.md](https://github.com/yawway365/draftedi-core/blob/main/specs/README.md)
for the file format.

## Public symbols

| Symbol | Location | Who imports it |
|---|---|---|
| `X12SpecProvider` | `draftedi.spec` / `draftedi` | Consumers and provider implementors |
| `JSONSkeletonSpecProvider` | `draftedi.spec` | Consumers |
| `ElementSpec` | `draftedi.spec` | Provider implementors |
| `RelationalCondition` | `draftedi.spec` | Provider implementors |
| `SegmentSpec` | `draftedi.spec` | Provider implementors |
| `TransactionSetSpec` | `draftedi.spec` | Provider implementors |
| `MissingSpecError` | `draftedi.spec` / `draftedi` | Defined for API compatibility; no draftedi function raises it |

## Which provider methods are called

`X12Validator` calls `get_transaction_set()` and `get_element_codes()`.
`get_segment_spec()` and `get_available_versions()` are part of the protocol
but draftedi does not call them.

When `get_transaction_set()` returns `None`, validation reports
`is_valid=None`. Exceptions from a provider propagate out of
`X12Validator.validate_transaction()`; `validate_edi()` reports them as
`SPEC_ERROR`.

## Stability

TypedDict field names and Protocol method signatures are frozen since 1.2.0
(first published on PyPI in 1.3.0). Any change is a semver major bump (2.0.0).
