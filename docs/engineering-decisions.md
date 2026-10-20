# Engineering decision record

## Context

Protocol interpretation must distinguish valid events, incomplete frames and unknown identifiers.

## Decision

Keep frame decoding explicit and verify representative protocol cases with executable fixtures.

## Consequences and evidence

Eight decoder checks pass; bus hardware behavior and end-to-end device integration need separate verification.

See [architecture](architecture.md), [validation](validation.md) and the [case study](case-study.md) for implementation details and limits.
