---
protocol: evidence-classification
version: "0.3"
schema_compatibility: "0.3"
---

# Evidence Classification

Use this protocol when an observation may become persistent evidence or when interpretation is ambiguous.

## Procedure

1. Record the observation before interpretation.
2. Record learner self-report separately.
3. Identify the smallest relevant target claim(s).
4. Verify that the observed task actually required the target capability.
5. Record observed confounds only; do not invent them.
6. Identify plausible alternative explanations.
7. Classify direction: `support`, `challenge`, `neutral`, or `deferred`.
8. Classify diagnosticity: `low`, `medium`, or `high`.
9. Classify novelty: `low`, `medium`, or `high`.
10. Record `interpretation.confidence`: `low`, `medium`, or `high`.
11. Decide whether diagnosis is needed and its decision relevance.
12. Persist only when the event adds future decision value.

## Learner feedback about the task or intervention

Learner feedback may change how an observation should be interpreted without itself becoming capability evidence.

When the learner says a task was too easy, answerable by a shortcut, insufficiently discriminating, confusing for representational reasons, or otherwise mismatched to what it was meant to test:

1. preserve the self-report separately from the observed answer/performance;
2. reassess whether the task genuinely required the target capability;
3. add any learner-identified plausible alternative path or confound only when it is concrete enough to be semantically meaningful;
4. reassess diagnosticity and interpretation confidence rather than mechanically preserving the original interpretation;
5. if success could plausibly be achieved without the target capability, retain correctness as an observation while reducing or withholding support for the capability claim;
6. when decision-relevant uncertainty remains, route the next action to `teaching-decision.md` for a more discriminating but proportionate probe.

A learner's claim that a probe is weakly diagnostic is not automatically true, but it is a decision-relevant self-report that MUST be considered when evaluating alternative explanations. Likewise, a learner saying an explanation felt helpful or unhelpful is direct feedback about the intervention experience, not proof of intervention effectiveness or capability change.

## Hard constraints

The classifier MUST NOT infer:

- mastery from one correct response;
- a stable misconception from one incorrect response;
- conceptual failure from poor verbal fluency alone;
- an effective teaching strategy from learner preference alone;
- a causal error mechanism solely from outcome;
- a global learner trait from one concept or domain;
- mastery merely because the learner continued without asking questions.

Correctness is an observation attribute, not an evidence direction. One observation MAY support different claims with different diagnosticity.

Success on a task MAY support capabilities necessary for that task when alternative paths are limited. Failure on a composite task MUST NOT automatically be attributed to one component capability.

An interpretation with `interpretation.confidence: low` MUST NOT alone trigger a persistent state transition.
