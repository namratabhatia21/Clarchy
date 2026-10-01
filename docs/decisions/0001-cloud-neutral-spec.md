# 0001: Architectures are written in cloud-neutral capabilities

**Status:** accepted · 2026-10-01

## Context

Clarchy starts with AWS but must later compare the same design on GCP, Azure and
open-source stacks. If designs were written in AWS service names, every comparison would
be three separately generated designs with different sizing, which is not a fair
comparison.

## Decision

- A spec lists **capabilities** (`object-storage`, `relational-db`, ...) with sizing,
  edges and a rationale. It never names a provider service.
- Each provider has a mapping file (`data/mappings/<provider>.yaml`) that resolves every
  capability to a service, with a **fidelity** level (`exact`, `close`, `partial`) and a
  note whenever it is not exact.
- Tests require every provider to map every capability, so adding a capability forces a
  decision for every cloud.
- Sizing is a loose key/value map for now. The cost engine (phase 2) will introduce a
  typed usage model per capability.

## Consequences

- Adding a provider is mostly data: a mapping file, a pricing adapter and an icon set.
- One-provider designs feel slightly indirect in phase 1. That is the accepted cost.
- Some provider-specific features have no neutral equivalent. They are expressed as
  sizing options or alternatives in the mapping, not as new capabilities, unless several
  providers share them.
