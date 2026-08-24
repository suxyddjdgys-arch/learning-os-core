---
protocol: project-handoff-policy
version: "0.1"
schema_compatibility: "0.3"
---

# Project Handoff Policy

This protocol defines safe writer-authority transfer for a long-lived logical work lineage whose canonical state lives in GitHub rather than in one physical conversation.

It is the generic transaction kernel for project/design conversation generations. Learning Branch continuity may conform through its existing Branch runtime and MUST NOT duplicate authority state merely to use this protocol.

## 1. Core model

- **Lineage**: a long-lived logical work stream.
- **Generation**: one writer epoch within a lineage.
- **Physical conversation**: an interaction surface, not canonical lineage identity.
- **active_generation**: the current monotonic fencing token.
- **session_generation**: session-local generation identity acquired through an allowed transition; it is not inferred merely by reading `active_generation`.

At most one generation of a lineage may hold ordinary canonical writer authority at a time.

## 2. Authority

Authority order:

1. current explicit user instruction;
2. current canonical repository state;
3. canonical lineage control;
4. published handoff packet;
5. conversation / Project memory.

A handoff packet never overrides newer canonical state. Historical conversation context never grants writer authority by itself.

## 3. Checkpoint vs handoff

A checkpoint persists durable state while the current generation remains active. It does not advance generation or transfer authority.

A formal handoff is used only when the current writer epoch is expected to end and another generation is expected to take over, such as explicit transfer, context pressure, or deliberate work-surface replacement.

Phase completion alone is not a handoff trigger.

## 4. Invariants

1. **Canonical first**: settled operational truth belongs in responsible canonical artifacts before handoff publication.
2. **Single writer**: one lineage has at most one active ordinary canonical writer generation.
3. **Fencing**: a generation lower than `active_generation` MUST NOT perform lineage-governed canonical writes.
4. **Generation acquisition**: reading `active_generation` MUST NOT grant a fresh session that generation. A session acquires `session_generation` only through an already-established continuous-session identity, successful successor claim, successful explicit takeover, or one-time migration bootstrap.
5. **Pending freeze**: once a normal handoff is published, the outgoing generation MUST NOT perform ordinary lineage-governed canonical work until the handoff is cancelled. Only transaction maintenance is allowed.
6. **Packet identity**: a published packet is identified by immutable content identity (`blob_sha`), not only by mutable path.
7. **Drift**: the recovery anchor is the canonical settlement baseline, not a promise that repository HEAD will remain frozen. Newer canonical state must be reconciled.
8. **Bounded recovery**: the current relevant handoff must be recovery-complete relative to current canonical state and MUST NOT require recursive loading of predecessor packets for normal recovery.
9. **Liveness**: loss of a predecessor conversation MUST NOT permanently lock the lineage; explicit current user authorization may perform takeover.
10. **Physical-chat independence**: renaming, deleting, reopening, or replacing a physical chat does not itself change canonical writer authority.
11. **Sparse control**: this protocol does not require a heartbeat, lease, TTL, lock server, receipt database, chat registry, or exactly-once message bus.

## 5. Canonical authority states

The generic authority model has only two steady states:

- `ACTIVE`: `pending_handoff == null`;
- `PENDING_CLAIM`: `pending_handoff != null`.

`PREPARING` is a local transaction phase and is not persisted as an authority state. `CLAIMED` is a transition result, not a steady state.

## 6. Minimal lineage control

A project-level lineage MAY use `runtime/lineages/<lineage-id>.yaml` with document type `lineage_control`.

It stores only writer-authority state and compact transition provenance. It MUST NOT become a system summary, chat history, plan store, or rationale archive.

Recommended structure:

```yaml
schema_version: "0.3"
document_type: lineage_control
updated_at: <timestamp>

lineage:
  id: <lineage-id>
  kind: <lineage-kind>

active_generation: <integer>
pending_handoff: <object-or-null>
bootstrap: <optional-object>
last_transition: <optional-object>
```

A semantic `revision` is not required in V0 unless a real downstream consumer needs one. Git blob SHA supplies compare-and-swap concurrency for the control file; `active_generation` carries the important writer-epoch semantics.

## 7. Pending handoff

A published normal handoff records:

```yaml
pending_handoff:
  id: <handoff-id>
  from_generation: <N>
  to_generation: <N+1>
  anchor:
    repository: <owner/repo>
    ref: <canonical-ref>
    canonical_head: <commit-sha>
  packet:
    path: <repository-path>
    blob_sha: <git-blob-sha>
  published_at: <timestamp>
```

`canonical_head` is the commit at which the outgoing generation finished settling ordinary canonical state that the handoff depends on.

`packet.blob_sha` identifies the exact published residual packet. `packet.path` is navigation metadata and is not packet identity.

Stored commit/blob SHAs here are snapshot/integrity anchors, not semantic revisions of normal Learning OS artifacts.

## 8. Handoff packet

A Project Handoff Packet is immutable supplemental recovery context. It SHOULD contain only information with future recovery value that cannot be naturally reconstructed from canonical state, such as:

- compact system snapshot;
- residual rationale;
- verified tests and platform behavior;
- important rejected approaches;
- current implementation state;
- genuine open issues;
- current frontier;
- recovery assertions.

The frontier SHOULD make clear:

- `NEXT ACTION`;
- `PRECONDITIONS`;
- `DONE WHEN`;
- `BLOCKED BY`;
- `DO NOT REOPEN`.

A `supersedes` reference is historical succession, not a recursive bootstrap dependency.

## 9. Normal publish

A source generation `N` publishes a handoff to `N+1` only after:

1. verifying its already-established `session_generation == active_generation` and `pending_handoff == null`;
2. fresh-reading decision-relevant canonical state;
3. writing settled operational truth to responsible canonical artifacts;
4. reading those writes back;
5. recording the current canonical ref HEAD as settlement anchor `H`;
6. creating a new immutable handoff packet;
7. reading the packet back and obtaining exact blob `B`;
8. fresh-fetching lineage control and its current blob SHA;
9. revalidating `active_generation == N` and `pending_handoff == null`;
10. CAS-updating lineage control with the `N -> N+1` pending transaction, anchor `H`, and packet `B`;
11. reading lineage control back.

A packet created without the control transition is an orphan supplemental artifact and does not transfer or freeze authority.

After publication, generation `N` is frozen from ordinary lineage-governed canonical work.

## 10. Cancellation and repair

Before successor claim, an explicit cancellation MAY CAS-clear `pending_handoff`, leaving generation `N` active.

If only packet continuity is incomplete, the outgoing generation MAY create a replacement immutable packet and CAS-update the pending transaction to point to it. The old packet remains historical.

If ordinary canonical truth itself must change, cancel the handoff first, resume generation `N`, settle the new canonical truth, create a new anchor/packet, and republish.

A pending generation MUST NOT silently change ordinary canonical project state while retaining the original settlement anchor.

## 11. Successor recovery

A fresh candidate successor does not acquire `to_generation` by observing a pending handoff. It is initially read/recovery-capable only.

It loads:

- fresh lineage control;
- current canonical bootstrap state;
- the published packet by `blob_sha`;
- the settlement anchor.

It then reconciles changes after `canonical_head`.

The exact packet mutation and exact lineage-control publication are expected transaction changes. Do not broadly ignore all `docs/handoffs/**` or `runtime/**` changes, because unrelated canonical drift may exist there.

Newer canonical truth overrides stale packet statements.

If the anchor and current intended canonical state diverge without a clear merge/promotion/rebase interpretation, recovery requires reconciliation before claim.

## 12. Recovery assertions

Before normal claim, the successor MUST be able to:

1. identify the canonical repository and current relevant ref;
2. identify the current architecture/schema/runtime generation;
3. identify current implementation/operational state;
4. identify the immediate frontier;
5. identify genuine blockers/open issues;
6. identify settled boundaries that should not be casually reopened;
7. continue without requiring the predecessor physical conversation.

Adapters MAY add stronger assertions.

Failed recovery assertions block normal claim.

## 13. Claim

After successful recovery, the successor fresh-fetches lineage control and verifies the expected pending transaction still matches.

Normal claim CAS-updates:

```yaml
active_generation: <N+1>
pending_handoff: null
last_transition:
  kind: normal_handoff
  handoff_id: <id>
  from_generation: <N>
  to_generation: <N+1>
  claimed_at: <timestamp>
  recovered_head: <current-recovered-head>
```

Only after claim readback succeeds may the session locally acquire `session_generation = N+1` and ordinary writer authority.

The successful CAS claim is the normal durable recovery receipt; no separate receipt artifact is required on the happy path.

If two successors race, both may recover but only one may successfully CAS-claim. The loser MUST fresh-read control and become non-authoritative rather than blindly retrying the same claim.

## 14. Writer guard

Before a lineage-governed canonical write, a writer MUST already possess a valid session-local generation identity and fresh-read the canonical authority control.

For normal work:

```text
session_generation == active_generation
pending_handoff == null
```

must hold.

The writer then separately fresh-fetches the target mutable artifact, semantically reconciles, and writes using its current target blob SHA.

Generation Guard prevents stale-writer ownership. Target-file CAS prevents concurrent overwrite. Neither substitutes for the other.

## 15. Stale predecessor

After `active_generation` advances, an older physical conversation may still read, discuss, inspect, and propose changes, but it MUST NOT perform lineage-governed canonical writes using its historical context.

If the user wants that physical work surface to become authoritative again, create a new monotonic generation through takeover rather than resurrecting an old generation.

## 16. Takeover

Takeover is a recovery/authority transition for cases such as unavailable predecessor, unrecoverable pending handoff, deliberate work-surface replacement, or loss of claimant session continuity.

Takeover MUST require explicit current user authorization. Time elapsed, inactivity, missing heartbeat, or inability to see an old conversation is insufficient by itself.

A takeover candidate fresh-bootstraps current canonical state, fresh-reads lineage control, chooses the next monotonic generation, and CAS-advances authority. It records:

```yaml
last_transition:
  kind: takeover
  from_generation: <old>
  to_generation: <new>
  claimed_at: <timestamp>
  reason: <short explicit reason>
  recovered_head: <current-head>
```

A takeover never resurrects an older fencing token.

If a session successfully claims a generation and then loses its local generation identity before further work, the safe recovery is an explicit takeover to a later generation, not silent re-adoption of the currently active number.

## 17. Packet integrity and schema failure

If a packet path later resolves to a different blob, recovery uses the published `blob_sha` when available and treats the path mismatch as an integrity anomaly.

Historical correction SHOULD use a new superseding packet rather than mutating recovery history.

If a runtime can read human-readable context but cannot safely interpret the current lineage-control/schema version, it may perform read-only recovery but MUST NOT structurally write or claim.

## 18. Adapter boundary

This protocol standardizes transaction semantics, not one mandatory storage implementation for every subsystem.

Learning Branch continuity already has Branch runtime lineage/generation state and an active-generation writer guard. It SHOULD conform semantically without adding a second project-level lineage-control file for the same Branch.

`continuity-policy.md` remains authoritative for learning-specific teaching-thread continuity, pending learner action, avoid-retesting/deferred references, Evidence/Knowledge/Progress restrictions, inactivity resume, execution-window reconciliation, and re-engagement.

## 19. Non-goals

This protocol is not:

- a distributed lock service;
- a heartbeat/lease system;
- an exactly-once event bus;
- a global repository writer registry;
- a full chat registry;
- a transcript mirror;
- a release/PR replacement;
- a generic workflow engine.

Different active lineages may legitimately touch the same artifact. Cross-lineage conflicts remain governed by target-file fresh-read, semantic reconciliation, and CAS.

## 20. Acceptance

Before broad reuse, real project-design tests SHOULD demonstrate:

- normal `N -> N+1` handoff;
- independent successor recovery;
- stale predecessor fencing after claim;
- a fresh unrelated chat cannot silently adopt the active generation;
- duplicate-successor CAS produces exactly one claimant;
- cancel-vs-claim race remains consistent;
- post-anchor canonical drift is reconciled;
- packet path mutation does not alter published packet identity;
- explicit takeover restores liveness;
- normal recovery does not depend on recursively loading the handoff chain.

Do not add leases, locks, or broader infrastructure unless concrete implementation evidence shows that the minimal mechanism is insufficient.
