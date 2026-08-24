---
protocol: evidence-integration
version: "0.2"
schema_compatibility: "0.3"
---

# Evidence Integration

Integrate new evidence with the existing portfolio. Do not use simple vote counts.

Allowed integration outcomes: `retain`, `advance`, `challenge`, `refine`.

## Principles

- Prefer `refine` when apparently conflicting evidence can be explained by meaningful task conditions.
- Prioritize evidence diversity, diagnosticity, independence, transfer, delay, exact claim relevance, and remaining alternative explanations.
- `supported` means current teaching may rely on the claim without extra verification cost unless meaningful contradictory evidence appears.
- `provisional` means there is useful support but important alternatives remain.
- `conflicted` means valid support and challenge remain unresolved for the same claim and conditions.
- `unsupported` means the capability cannot currently be relied on under the claim's stated conditions.

These capability states are the V0.3 learner Knowledge State values defined by `schema.md`. Evidence itself remains an immutable observation plus `interpretation` and target references; integration updates a capability claim only when persistence is justified.

## Default transition guidance

- absent/unknown + meaningful support -> `provisional`
- `provisional` + diverse support / reduced alternatives -> `supported`
- `provisional` + high direct challenge -> `conflicted`
- `supported` + isolated medium contradiction against a broad portfolio -> consider an active anomaly before downgrade
- `supported` + meaningful direct contradiction -> `conflicted` or refine
- `unsupported` + immediate post-intervention success -> normally at most `provisional`
- `conflicted` -> `supported` only after the conflict is explained or resolved, not merely after new correct answers

Higher-level hypotheses require broader evidence and slower updates than concept-level state.
