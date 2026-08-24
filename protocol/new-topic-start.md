---
protocol: new-topic-start
version: "0.3"
schema_compatibility: "0.3"
---

# New Topic Start

Use this protocol when the learner begins a genuinely new learner-specific Topic, when an existing Topic has no usable goal/plan, or when `plan.status: awaiting_intake`.

A Topic is a learner-specific learning project. A Domain is reusable knowledge structure. Starting a new Topic MUST NOT automatically create a new Domain or treat the Topic as a Domain.

## 1. Read before asking

Read only the persistent state that can change the startup decision:

- relevant `learner/background.yaml` entries;
- relevant learner model/calibration/cost information when it has direct routing value;
- `learner/execution.yaml` only if materialized and relevant;
- any existing `topics/<topic>/goal.yaml`, `plan.yaml`, and `progress.yaml`;
- relevant curricula only when needed to build the initial route.

Do not ask again for learner-authoritative information already recorded unless it is ambiguous, stale because of an explicit newer statement, or newly decision-relevant in a different scope.

## 2. Compact intake

Collect only missing information likely to materially change the initial route. Prefer one compact intake message.

High-value fields, when unknown and relevant:

- purpose / desired outcome;
- target depth or competence;
- horizon or deadline;
- realistic Topic-level resource preference when useful;
- relevant prior courses, projects, tools, or exposure;
- important constraints or content to include/avoid.

Do not use intake as a placement test. Prior exposure is background, not mastery.

If the learner explicitly asks to start immediately, intake MUST NOT block learning. Create a usable provisional route from known information and minimal assumptions; record only unresolved blocking/planning gaps that have a real future trigger.

## 3. Persist by responsibility

- durable history/exposure -> `learner/background.yaml`;
- learner-specific purpose/depth/horizon/constraints/success criteria -> `topics/<topic>/goal.yaml`;
- learner-global execution defaults -> `learner/execution.yaml` only when the learner has actually supplied global/default execution information;
- learner-specific route -> `topics/<topic>/plan.yaml`;
- capability state MUST NOT be created merely from background or intake answers.

Do not create synthetic evidence records merely to justify learner-authoritative goal/background writes.

## 4. Build Topic route separately from knowledge structure

Use existing Domain curricula when available. Create or extend reusable curriculum structure only as much as current teaching requires; do not build an exhaustive Domain taxonomy merely because a new Topic exists.

The initial Topic Plan SHOULD contain:

- a small set of meaningful Topic milestones;
- a coarse suggested sequence;
- explicit completion basis or exit criteria for milestones;
- only decision-relevant intake gaps;
- replanning triggers.

Plan status:

- `awaiting_intake`: route-changing intake is still required and the learner has not chosen to proceed without it;
- `provisional`: a usable route exists but assumptions or future planning gaps remain;
- `active`: the current route is sufficiently grounded;
- `paused`: the route is intentionally paused.

## 5. Materialize Subtopics lazily

A planned future Subtopic MAY exist only as a Topic Plan reference. Materialize `topics/<topic>/subtopics/<subtopic>/` only when it becomes a coherent multi-step unit that benefits from independent progress/continuity.

When materializing, prepare Subtopic Plan and Progress first and create `definition.yaml` last. The definition file acts as the materialization commit marker.

Do not precreate future Subtopics, Practice/Deep-Dive branches, coordination files, execution history, or learner knowledge files with empty state.

## 6. Placement and prerequisites

Do not run a broad placement test by default. Missing knowledge state means unknown, not inability. Use background only to choose a provisional starting point and observe naturally.

Use a targeted diagnostic only when uncertainty about a prerequisite can materially change the next teaching action and is worth the learner/flow cost.

## 7. Show and begin

After intake is answered, left unknown, or explicitly skipped:

1. persist learner-authoritative durable updates;
2. create a usable Topic Goal/Plan;
3. materialize only the current useful Subtopic if needed;
4. show a concise adaptive route;
5. begin full teaching.

Do not present a generic curriculum map as if it were the learner-specific plan.