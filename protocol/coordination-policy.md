---
protocol: coordination-policy
version: "0.3"
schema_compatibility: "0.3"
---

# Coordination Policy

Coordination connects learner-local Study Branches with Topic/Global planning without turning every chat turn into a distributed transaction.

## 1. Logical roles

- **Global Hub**: learner-level cross-Topic resource allocation and reconciliation. Materialize only when cross-Topic coordination is actually needed.
- **Topic Hub**: Topic goal/route/milestone/Subtopic coordination.
- **Study Branch**: teaching, exercises, local prerequisite repair, local progress, evidence generation, and bounded execution.

A Hub is a logical operation class, not an irreplaceable physical chat. A dedicated Hub chat is the normal UI, but a low-risk delegated Hub-class operation MAY be performed elsewhere when fresh canonical state and revision checks make it safe. Doing so does not rebind the chat identity.

### 1.1 Materialization triggers

Logical Hub authority and physical Hub conversations are distinct. Materialize additional work surfaces only when they reduce real coordination/context cost.

- A new Study Branch SHOULD be materialized when role-local work needs independent continuity, resume state, or writer boundaries beyond what the current Branch can safely carry. Do not create Practice or Deep-Dive Branches merely because those roles exist in the schema.
- A dedicated Topic Hub conversation SHOULD normally be suggested/materialized when a Topic gains a second concurrently useful Study Branch, or when recurrent Hub-class structural decisions make delegated Hub operations materially cumbersome. Before that point, a Main Branch may host bounded delegated Topic-Hub-class operations without becoming the Topic Hub identity.
- A Global Hub SHOULD be materialized when multiple active Topics create a real cross-Topic coordination need such as shared weekly-budget allocation, competing deadlines, prerequisite reuse, or route prioritization. The mere existence of a second Topic does not require an empty Global Hub if no cross-Topic decision exists.
- Materializing a Hub does not grant it a Study Branch generation and does not transfer Branch-local writer authority. Hub decisions and Branch writes continue to obey their own canonical ownership/concurrency rules.

### 1.2 Delegated Topic-Hub execution

A delegated Topic-Hub-class operation is an operation/decision class, not a requirement to move work to a physical Hub conversation.

When exactly one Topic is active and no dedicated Topic Hub is materialized, the active Main Branch is the default executor for bounded delegated Topic-Hub-class operations that are safe under fresh canonical state. This includes single-Topic Weekly activation/planning. The Main Branch MUST NOT refuse such an operation solely because its conversation role is `main`.

A Branch-originated canonical write performed as a delegated Topic-Hub operation still requires the Branch active-generation guard plus fresh target-file state/CAS rules. Delegation does not grant authority over another Study Branch's branch-local Progress, does not permit cross-Topic allocation, and does not turn the Main Branch identity into a Topic Hub identity.

If a dedicated Topic Hub already exists, prefer that Hub for ordinary Topic-Hub-class work. If the delegated operation depends on genuinely missing learner-authoritative information, ask only the scoped question needed to resolve it and keep the operation pending; otherwise execute the bounded operation rather than escalating merely because it is Hub-class.

## 2. Branch autonomy envelope

Within an already materialized Subtopic, a Study Branch MAY normally:

- advance within the current Subtopic Plan;
- form local Daily objectives;
- perform inline prerequisite repair;
- take a short detour and preserve a return point;
- deepen/practice current material;
- support learner-chosen extension.

Hub-class reconciliation is required for structural changes such as creating/splitting/merging Subtopics, materially changing the Topic route, pausing/completing a Topic, cross-Topic resource allocation, or a large prerequisite route.

## 3. Report and event

A Branch report is a rebuildable latest projection answering: "What does the Hub need to know about this Branch now?"

It SHOULD remain compact and may include consumed plan revisions, current local progress/readiness summary, current blockers, `hub_attention`, relevant execution context, and canonical source revisions. It MUST NOT duplicate the entire canonical Progress artifact.

A Coordination Event is an immutable semantic delta answering: "What changed that may materially affect routing or planning?"

Do not emit an event for every message, exercise, provisional evidence item, or daily micro-step. Escalate when hiding the change could make near-term planning/routing/resource allocation materially worse.

## 4. Event families and scope

Core event families:

- `progress_transition`
- `blocker_change`
- `route_request`
- `resource_request`
- `learner_directive`
- `reconciliation_needed`

More specific meaning belongs in `subtype` and a type-specific payload rather than an unbounded family list.

`target_scope` is normally `topic` or `global`. Cross-Topic issues MAY target global scope directly; they do not require a physical Topic Hub chat to relay them.

Coordination events are routing inputs, not commands and not learning evidence. An event MAY reference evidence when a learning observation has become routing-relevant.

## 5. Attention

`hub_attention` levels:

- `none`: no extra Hub decision needed;
- `review`: consider at the next ordinary reconciliation; local work may continue;
- `required`: the affected structural route is outside Branch autonomy and requires Hub-class reconciliation.

`required` does not automatically block all safe local learning.

## 6. Reconciliation

Hubs perform batch semantic reconciliation over fresh canonical facts, relevant reports/events, current goals, and current resource constraints. Events are inputs to one semantic decision; do not mechanically execute them one by one.

Use optimistic concurrency. Before modifying an existing mutable canonical artifact, fresh-fetch it and validate the revisions that are genuinely critical to the decision. Do not bind a Topic Plan to every ordinary Progress/Knowledge revision; replan only when a material trigger occurs.

For semantic conflicts, re-read and reintegrate; do not blind retry or use last-write-wins for competing capability/route decisions.

## 7. Reliability

The coordination model is at-least-once plus idempotent reconciliation. It MUST NOT depend on exactly-once event processing, heartbeat, TTL leases, realtime Hub presence, or a general inbox/outbox message-queue architecture.

Branch reports and events need not be atomically committed:

- if a report succeeds and an event fails, current `hub_attention` can still surface the issue;
- if an event succeeds and a report fails, the Hub can drill into canonical state.

Canonical state outranks projections/notifications for recovery.

A Hub cursor/runtime is an optimization, not correctness authority. If a reconciliation changes canonical Plan/Progress/Weekly decisions, write and verify those decisions before advancing any cursor. Cursor loss may cause event replay, not learner-state loss.

## 8. Global recursion

When Global Hub exists, Topic Hub may publish a compressed Topic report and global-scope events. Global Hub should normally read Topic-level projections first and drill into Branch detail only when necessary.

Do not materialize Global Hub, Topic reports, or allocation artifacts while only one Topic exists and no cross-Topic resource decision requires them.
