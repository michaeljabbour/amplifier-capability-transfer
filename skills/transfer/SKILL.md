---
name: transfer
description: Use for a bounded capability transfer across architectures or languages, while keeping host boundaries intact.
license: MIT
---

# Transfer

Bring a proven capability to the host you use.

## Gap-check before building

Declare donor(s), host(s), bounded capability/scope, excluded work, and acceptance surface. Read the host's current code and operate it where useful. Determine which behavior already exists and what is genuinely missing in each host; document keep/drop reasons. The original [principles](references/PRINCIPLES.md) and [runbook](references/hgt-runbook.md) preserve the multi-host HGT engine's stricter queue policy; state any intentional instance deviation rather than silently changing its graph.

## Extract the observable contract

Observe the donor's actual user-facing behavior and read its code to understand boundaries. Record trigger, inputs, state transitions, outputs, errors, recovery, cancellation, persistence, and dependencies. Do not import, vendor, or copy donor source. Preserve attribution for ideas. Source access and a working donor demo do not mean the host implementation already works.

## Plan through host seams

Choose each host's existing layer and interface. Keep a pure protocol client a client. A shared backend/protocol prerequisite lands before dependent clients. The retained ledger supports `a`, `ab`, and `split`; use distinct ordered rows for backend and client slices. Avoid duplicate work when the capability already exists. Independent disjoint work may run in parallel; competing edits and state dependencies need ordering.

## Build one vertical slice

Author an acceptance probe from the donor contract before host implementation. Re-express the feature in host idioms, with unit checks, the host's normal CI gate, and a real-surface probe. Terminal features require a real terminal; API/desktop features require the corresponding observable surface. Execute and preserve evidence. A passing unit fixture or an LLM statement alone is insufficient.

Use isolated branches and existing granted authority. The historical graph can push/open PRs, but installing this skill never authorizes publication. Bound attempts (the engine uses at most three), then acknowledge a blocker with reason and a reproducible handoff. Keep requested, implemented, independently verified, acknowledged, and released distinct.

## Verify against the donor

A verifier derives checks from the donor knowing only the capability ID/scope; hide builder artifacts and expected answers when feasible. Record what blindness and independence actually held. Findings may go to the builder; builder claims must not define the verification oracle. Reopen within a declared bound; preserve failed checks and remaining gaps. A ratchet metric tests ledger state transitions, not donor-host behavioral equivalence by itself.

## Return

Give the donor contract, per-host gap and seam decisions, changed interfaces, exact unit/real-surface/CI results, independent verification evidence, blockers, and rollback. Do not call a transfer proven merely because the queue has no new rows.
