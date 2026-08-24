---
protocol: repository-governance-policy
version: "0.1"
schema_compatibility: "0.3"
---

# Repository Governance Policy

This policy defines how Learning OS repository paths are governed without replacing subsystem semantic authority, generation fencing, fresh-read reconciliation, or blob-SHA compare-and-swap (CAS).

The current repository intentionally contains both architecture/core material and live learner/runtime state. Governance MUST therefore preserve legitimate direct state persistence while making architectural writes harder to perform accidentally.

## 1. Principles

1. Deterministic invariants belong in deterministic validation where practical.
2. Semantic authority remains governed by the responsible Learning OS protocol and generation/session rules.
3. GitHub controls reinforce but do not replace Learning OS authority.
4. Runtime persistence must remain live.
5. Core changes SHOULD use branch -> pull request -> validation -> merge -> production readback.
6. Direct-CAS permission for runtime state MUST NOT be interpreted as permission to mutate core files.
7. Force-push/history rewrite is not an acceptable normal repair mechanism.
8. Repository-snapshot validation cannot prove that a change arrived through a pull request.
9. Physical conversation naming, chat titles, and reading `active_generation` never grant repository writer authority.

## 2. Write classes

### CORE_PROTECTED

Architecture, protocol, deterministic validation, CI configuration, and governance material. Normal project-design changes require a feature branch, pull request, successful validator/tests, merge, and production readback.

Direct writes to `main` are prohibited for ordinary work even when the writer has project-design generation authority. Project-design authority is necessary for semantic ownership but is not a bypass around the core-change flow.

### INSTANCE_CAS

Mutable learner/runtime canonical state whose normal persistence is part of Learning OS operation. Direct canonical persistence MAY continue when the responsible subsystem writer is authorized and all applicable fresh-read, generation/authority, semantic reconciliation, and blob-SHA CAS guards pass.

### IMMUTABLE_APPEND

Create-only historical facts or continuity artifacts. Authorized writers MAY append a new artifact directly when the responsible protocol permits it. Existing immutable artifacts MUST NOT be rewritten merely to align history with current semantics; correction normally uses a new superseding/reinterpretation artifact.

### GENERATED_OR_PROJECTION

Rebuildable or derived state. It MAY be persisted directly when its owning protocol permits, but its source canonical state outranks a stale projection. Writers MUST preserve provenance/reconciliation semantics where defined.

### MIXED / REQUIRES_SPLIT

A directory containing materially different write classes, or reusable/shared content whose current runtime semantics do not cleanly fit a branch-wide protection rule. Writers MUST resolve the concrete subpath/semantic object before choosing a write path. Parent-directory classification alone is insufficient.

### UNKNOWN

No write is permitted until current canonical semantics determine the correct class and authority.

## 3. Current write-class inventory

| Path / object | Class | Normal writer | Direct CAS to canonical `main`? | PR normally required? | Immutable after creation? | Current validator coverage |
| --- | --- | --- | --- | --- | --- | --- |
| `config/**` | CORE_PROTECTED | project-design/maintenance | no | yes | no | YAML structure for canonical config; not PR provenance |
| `protocol/**` | CORE_PROTECTED | project-design/maintenance | no | yes | no | Markdown not mechanically schema-validated |
| `scripts/**` | CORE_PROTECTED | project-design/maintenance | no | yes | no | exercised by CI/tests; source provenance not provable from snapshot |
| `tests/**` | CORE_PROTECTED | project-design/maintenance | no | yes | no | executed by CI; provenance not provable from snapshot |
| `.github/**` | CORE_PROTECTED | project-design/maintenance | no | yes | no | workflow is externally exercised by GitHub Actions |
| `requirements-dev.txt` | CORE_PROTECTED | project-design/maintenance | no | yes | no | consumed by CI |
| `README.md` | CORE_PROTECTED | project-design/maintenance | no | yes | no | none beyond review/CI presence |
| `docs/acceptance/**` | CORE_PROTECTED | project-design/maintenance | no | yes | historical records should not be rewritten to fake later success | not mechanically semantic-validated |
| `docs/handoffs/README.md` | CORE_PROTECTED | project-design/maintenance | no | yes | no | none |
| dated project handoff packets under `docs/handoffs/**` | IMMUTABLE_APPEND | authorized project-handoff transaction | create-only direct append allowed | no for packet creation itself | yes | packet identity enforced by lineage/handoff semantics, not full content validation |
| `domains/_template/**` | CORE_PROTECTED | project-design/maintenance | no | yes | no | curriculum structural checks when YAML is scanned |
| reusable `domains/<domain>/curriculum.yaml` | MIXED / REQUIRES_SPLIT | curriculum/project planning authority; may be extended as teaching needs | currently possible with fresh-read/CAS when semantically justified | not globally enforceable without changing current runtime model | no | curriculum enums/refs partially covered |
| `learner/**` | INSTANCE_CAS | authorized learner/runtime writer by semantic field | yes | no | no | selected document/enums/reference invariants |
| Topic Goal/Plan/Progress/Deferred and mutable coordination state under `topics/**` | INSTANCE_CAS | responsible Topic/Subtopic/Hub/Branch writer | yes, with applicable generation guards | no | no | plan/progress/ref and Branch runtime invariants partially covered |
| execution sessions / coordination events / learning handoffs under `topics/**` | IMMUTABLE_APPEND | responsible authorized runtime/continuity writer | create-only direct append allowed | no | yes | document/path and selected runtime invariants |
| Branch/Topic reports and similar rebuildable reports under `topics/**` | GENERATED_OR_PROJECTION | responsible Branch/Hub | yes | no | no | selected structural checks when materialized |
| `evidence/**` | IMMUTABLE_APPEND | authorized learning writer after evidence classification | create-only direct append allowed | no | yes | Evidence enums and Knowledge reference existence |
| `execution/weekly/**` and other execution projections | GENERATED_OR_PROJECTION / INSTANCE_CAS | responsible execution owner | yes | no | no | Weekly projection provenance and selected enums/refs |
| `runtime/lineages/**` | INSTANCE_CAS (authority-critical) | project-design handoff/claim/takeover transaction | yes, only under project-handoff transaction semantics | no | no | lineage active/pending/anchor/packet invariants |
| `runtime/ui/**` | INSTANCE_CAS (special metadata) | conversation-sequence allocator / authorized repair | yes, under naming policy CAS rules | no | no | sequence/repair structure |
| unclassified new path | UNKNOWN | none until classified | no | unresolved | unresolved | none |

`topics/**`, `docs/**`, and `domains/**` are therefore not safely governable by directory name alone.

## 4. Core-change rule

Normal `CORE_PROTECTED` change flow:

1. establish the applicable project-design writer authority;
2. fresh-read canonical `main` and decision-relevant core files;
3. create a fresh feature branch from the observed canonical baseline;
4. make narrowly scoped changes on that branch using fresh target content/SHA where applicable;
5. open a pull request;
6. run the canonical validator and deterministic tests on a full checkout;
7. inspect the PR diff and authority state again before merge;
8. merge without force-pushing or rewriting history;
9. fresh-read production `main` and changed files.

A project-design generation is not permission to skip these steps for ordinary core work.

## 5. Runtime-state rule

`INSTANCE_CAS`, `IMMUTABLE_APPEND`, and `GENERATED_OR_PROJECTION` writes remain compatible with direct canonical persistence only where their responsible protocols permit it.

All existing subsystem constraints remain in force, including:

- session/generation authority when materialized;
- `pending_handoff` or `pending_successor` restrictions;
- fresh-read before mutation;
- semantic reconciliation of relevant upstream state;
- current blob SHA for mutable-file CAS;
- create-only behavior for immutable artifacts;
- read-time reconciliation for stale projections.

A runtime writer MUST NOT include a `CORE_PROTECTED` path in an ordinary learning/runtime persistence transaction.

## 6. GitHub enforcement boundary

The current single repository cannot cleanly express "core paths require PR, instance paths may direct-CAS to `main`" using a branch-wide PR rule alone.

A branch rule/ruleset that requires pull requests or pre-existing required checks for every update to `main` conflicts with direct runtime CAS unless a runtime actor receives bypass permission. A repository-wide bypass restores liveness but also allows that same actor to bypass protection for core paths.

Path-restriction push rulesets are not an equivalent solution: they apply to pushes repository-wide rather than expressing "this path is allowed through PR but not direct `main` writes" for the same privileged actor. They also depend on GitHub plan/capability availability.

Therefore current technical enforcement is explicitly bounded:

- CI validates repository state and PR candidates;
- canonical policy constrains conforming Learning OS writers;
- GitHub history controls such as blocking force pushes/deletions are desirable when configured without blocking normal pushes;
- clean path-level prevention requires a stronger trust boundary, most naturally Core/Instance repository separation or another architecture with distinct write identities/permissions.

Do not claim that core paths are technically protected merely because this policy says they are `CORE_PROTECTED`.

## 7. Threat model

### Accidental stale writer

Mitigation: subsystem generation fencing plus fresh target CAS. Repository governance does not replace it.

### Legitimate runtime writer touching core

Mitigation today: explicit write classes loaded by conforming Learning OS writers; core branch/PR flow. Technical prevention remains incomplete while the same repository credential can write both classes.

### Direct push bypass

CI on `push` detects deterministic invalid state after the fact but cannot reject an already accepted unprotected direct push. PR workflow provides pre-merge evidence only when the change actually uses PR flow.

### Force push / history rewrite

Prohibited by policy. GitHub branch/ruleset controls SHOULD block force pushes and deletion when available without breaking runtime direct writes. Until such settings are verified active, this remains a governance gap.

### Validator bypass / CI corruption

`scripts/**`, `tests/**`, `requirements-dev.txt`, and `.github/**` are all `CORE_PROTECTED` and should change together only through reviewed/validated PRs. A repository actor with unrestricted direct-write power can still weaken these controls; snapshot validation cannot create an independent root of trust inside the same repository.

### Generated-state noise

Instance/projection writes remain direct-CAS and do not require PRs, avoiding high-frequency governance friction.

## 8. Prohibited behavior

- ordinary runtime persistence that also changes `CORE_PROTECTED` files;
- blind overwrite or last-write-wins on mutable canonical state;
- force push or intentional history rewrite as normal maintenance;
- rewriting immutable Evidence/session/event/handoff history to make current state look cleaner;
- weakening validator/tests/workflow merely to obtain green CI;
- treating a failed validator as permission to bypass it;
- taking `active_generation`, `Cxx`, a title, or repository admin access as semantic Learning OS authority.

## 9. Emergency repair

Emergency repair exists only for a concrete failure that prevents the normal core PR/validation path, such as corrupted canonical validator source or broken CI configuration.

It is not a general bypass.

An emergency repair MUST:

1. identify the concrete blocker and why normal PR validation cannot safely complete;
2. retain valid Learning OS writer authority where the repair is lineage-governed;
3. fresh-read the affected core target and current canonical state;
4. make the minimum change necessary to restore the normal validation path;
5. preserve provenance in commit/acceptance history;
6. read back the repair;
7. immediately rerun validator/tests and return subsequent core work to normal PR flow.

If GitHub itself prevents the safe repair, stop and report the external blocker rather than bypassing with history rewrite.

## 10. GitHub settings target

Without introducing runtime breakage, the desired minimum branch-level safety is:

- block force pushes to `main`;
- block deletion of `main`;
- keep normal direct non-force updates possible for authorized instance CAS;
- retain `Validate Learning OS` on both `push` and `pull_request`;
- use PR + green validation for core changes.

Do **not** enable a branch-wide pull-request requirement or branch-wide required-status-check gate on `main` until runtime persistence has a compatible trust boundary.

If a runtime identity later receives a bypass to a stricter branch ruleset, acceptance MUST explicitly state whether that identity can also modify core paths. A repository-wide bypass is privileged and is not path-level enforcement.

## 11. Open-source preparation

Repository-governance readiness is separate from public-release readiness. Before a public open-source release, the owner must explicitly choose a license. No license is selected by this policy.

`CONTRIBUTING.md`, `SECURITY.md`, code-of-conduct material, and issue/PR templates should be added only when they serve an actual collaboration/governance need; V0.3.2 does not require boilerplate for its own sake.

## 12. Next architectural requirement

If stronger technical prevention is required—especially "runtime writer cannot modify core even if compromised or mistaken"—the current mixed repository is insufficient.

The next architecture phase SHOULD evaluate Core/Instance separation (or an equivalent distinct credential/storage boundary) before enabling strict PR-only protection on the core side. That migration must separately address canonical locations, bootstrap, references, handoff semantics, validator roots, and runtime permissions.
