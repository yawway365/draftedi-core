# draftedi.spec

Protocol and TypedDict contracts for X12 specification data injection.

## BYOS — Bring Your Own Spec

The OSS `draftedi` package cannot bundle copyrighted X12 specification databases.
`X12SpecProvider` is a `typing.Protocol` that defines the interface your spec
implementation must satisfy. Supply a conforming implementation to enable
spec-dependent validation in v1.3.0+.

## Public symbols

| Symbol | Location | Who imports it |
|---|---|---|
| `X12SpecProvider` | `draftedi.spec` / `draftedi` | Consumers |
| `MissingSpecError` | `draftedi.spec` / `draftedi` | Consumers |
| `ElementSpec` | `draftedi.spec` | Provider implementors |
| `RelationalCondition` | `draftedi.spec` | Provider implementors |
| `SegmentSpec` | `draftedi.spec` | Provider implementors |
| `TransactionSetSpec` | `draftedi.spec` | Provider implementors |

## Stability

TypedDict field names and Protocol method signatures are frozen from v1.2.0.
Any change is a semver major bump (v2.0.0).
