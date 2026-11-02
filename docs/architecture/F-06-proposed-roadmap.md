# F-06 — Proposed Post-Submission Engineering Roadmap

**Status:** PROPOSED ONLY — not approved, not implemented, no runtime changes
**Date:** 2026-11-02 (BRT)
**Baseline:** `feature/f05-latency-resilience` working tree over `main @ 2c7a7e57cb9eba566df9a75705eb2ed667e9fa5c`
**Owner decision:** F-05 is the intended final submission candidate. F-06 is a
documented future engineering roadmap only. No F-06 development is authorized by
this document.

## 1. Purpose

F-06 collects engineering improvements that are explicitly out of scope for the
F-05 release candidate. They are proposed because the current prototype has
demonstrated three real limitations:

1. A free model can emit syntactically or semantically invalid tool arguments,
   producing `INVALID_ARGUMENT` even when the catalog query is conceptually valid.
2. A model can produce a final answer that fails the host grounding guard, producing
   `GROUNDING_FAILED` even when retrieval succeeded.
3. Free-provider latency and output quality vary; the current benchmark measures
   protocol behavior with synthetic fixtures but cannot establish real customer
   experience.

F-06 is not a bug-fix plan for F-05. It does not authorize changing F-05 runtime
behavior, models, prompts, allowlists, tests or documentation claims.

## 2. Scope and non-goals

In scope for future approval:

- Shared argument contracts and normalization design.
- Grounding calibration and diagnostics.
- Conversational quality and model evaluation methodology.
- Documentation, test strategy and stop conditions for those topics.

Out of scope:

- Any change to F-01/F-02 public catalog or policy contracts.
- Any change to F-05 deadlines, workers, diagnostics or benchmark behavior.
- Paid inference, paid fallback or API-credit spending.
- New frameworks, vector databases, persistent services, caches or dependencies.
- Customer/order data, payments, mutations or autonomous actions.
- Automatic model switching without owner approval and evidence.

## 3. Priority order

| Priority | Workstream | Rationale |
| --- | --- | --- |
| P1 | A. Structured argument normalization | Directly addresses observed `INVALID_ARGUMENT` failures while preserving strict validation. |
| P2 | B. Grounding calibration | Addresses false positives/negatives in the host grounding guard and preserves policy cautions. |
| P3 | C. Conversational quality and model evaluation | Improves answer usability and makes future model comparisons reproducible and privacy-bounded. |

Workstream A should be designed before B/C because argument contracts define the
evidence that grounding and quality evaluation consume.

## 4. Workstream A — Structured argument normalization

### 4.1 Problem

The model currently sends JSON tool arguments that are validated by
`parse_and_validate_arguments` and `ToolRegistry.dispatch`. Invalid types, ranges,
unknown tools, duplicate keys and malformed JSON are correctly rejected. That
safety is required. However, benign model variations (for example, a price sent as
a string, a category name with different casing, or a budget expressed in reais
rather than cents) can fail before retrieval. The observed budget-recommendation
failure is consistent with this class, although its original arguments were not
retained.

### 4.2 Proposed design

- Define one shared contract per tool in a single module, including field types,
  ranges, required filters, enum values and error codes.
- Separate three phases:
  1. **Parse**: strict JSON decoding with duplicate-key rejection.
  2. **Normalize**: only safe, reversible canonical transformations.
  3. **Validate**: re-run the full contract after normalization.
- Canonical transformations must be allowlisted and deterministic. Examples:
  - trim surrounding whitespace from string fields;
  - normalize category lookup keys without changing stored category names;
  - convert an explicitly labeled decimal currency value to integer cents only
    when the source unit is unambiguous;
  - reject ambiguous or lossy conversions instead of guessing.
- Rejected inputs must return the existing `INVALID_ARGUMENT` code with no partial
  tool execution.
- Normalization metadata, if exposed at all, must be sanitized and must not include
  raw customer text, arguments or tool payloads.

### 4.3 Acceptance criteria

- A-01: Every tool has one shared contract definition used by both validation and
  any future normalization layer.
- A-02: Normalization is optional and disabled by default until owner approval.
- A-03: No transformation can bypass range, type, enum or required-filter checks.
- A-04: Ambiguous inputs are rejected with `INVALID_ARGUMENT`; no guessed values
  reach retrieval.
- A-05: Existing valid calls produce byte-identical arguments and results.
- A-06: Regression tests cover valid, invalid, ambiguous and adversarial inputs,
  including prompt-injection strings.
- A-07: No host keyword router or model-result rewriting is introduced.

### 4.4 Risks and stop conditions

- Risk: normalization could mask model-quality problems by accepting weak inputs.
  Mitigation: keep strict validation and report normalization outcomes separately.
- Risk: currency conversion can introduce off-by-one cent errors.
  Mitigation: reject ambiguous units; require explicit cents for price filters.
- Stop if normalization requires changing F-01/F-02 public schemas or accepting
  untrusted free-form SQL or shell input.

## 5. Workstream B — Grounding calibration

### 5.1 Problem

The host checks final structured envelopes, current-turn sources and numerical
grounding before displaying factual answers. This protects against unsupported
claims, but the current calibration is based on a small set of examples and can
both reject valid answers and accept subtle unsupported wording. The observed
category-listing `GROUNDING_FAILED` outcome demonstrates the former. The combined
example's unsupported "aplicado no checkout" wording demonstrates the latter risk.

### 5.2 Proposed design

- Build a labeled dataset of final envelopes marked `supported` or `unsupported`,
  including:
  - correct price and availability statements;
  - missing or incorrect product-price pairs;
  - policy cautions that must be preserved;
  - unsupported promotional or checkout wording;
  - clarification and out-of-scope envelopes.
- Add diagnostics for missing or incorrect sources, including which claimed fact
  lacked current-turn evidence.
- Separate numeric consistency checks from source-presence checks so failures can
  be classified without exposing raw payloads.
- Measure false rejections and false acceptances explicitly.
- Preserve policy cautions as non-optional content; a grounded answer must not
  drop a required caution to pass validation.

### 5.3 Acceptance criteria

- B-01: A versioned labeled dataset exists with at least the four authentic
  example outcomes plus synthetic adversarial cases.
- B-02: Grounding reports separate source-missing, numeric-mismatch and
  caution-dropped failures.
- B-03: False-rejection and false-acceptance rates are measured against the
  labeled dataset.
- B-04: Policy cautions present in retrieved evidence remain present in accepted
  answers.
- B-05: Numeric checks cover all product prices and availability states claimed
  in the final answer.
- B-06: Calibration changes include regression tests for both previously observed
  failure classes.

### 5.4 Risks and stop conditions

- Risk: overfitting the guard to examples could reduce recall for legitimate
  answers.
  Mitigation: measure false rejection explicitly and require owner review of
  threshold changes.
- Risk: labeled data may contain sensitive or copyrighted source text.
  Mitigation: use synthetic or sanitized excerpts only; no real customer data.
- Stop if calibration requires weakening evidence requirements or accepting
  unverified promotional wording.

## 6. Workstream C — Conversational quality and model evaluation

### 6.1 Problem

The prototype currently optimizes for safety and traceability. Answer clarity,
concision and user usefulness are not measured. Internal implementation details
can leak into prompts or documentation, and model comparison is not reproducible.
Free providers also impose retention and quota constraints that must be explicit.

### 6.2 Proposed design

- Define a human-reviewed rubric for answer clarity, concision, tone and
  appropriate next steps in pt-BR.
- Remove unnecessary internal implementation prose from customer-facing answers
  and from evaluation prompts; keep engineering detail in docs only.
- Define a reproducible model comparison protocol:
  - fixed scenario set and prompts;
  - fixed tool and grounding contracts;
  - separate metrics for reliability, factuality, latency and fallback rate;
  - no automatic model switching or paid fallback.
- Keep privacy and free-provider constraints explicit:
  - synthetic questions only;
  - no real customer records, secrets or sensitive conversations;
  - document provider retention/logging terms before any run;
  - respect free quotas and stop on 429/auth/non-free routing.

### 6.3 Acceptance criteria

- C-01: A documented rubric scores clarity, concision, tone and next-step
  usefulness.
- C-02: Customer-facing answers and evaluation prompts exclude internal
  implementation detail unless it is user-relevant.
- C-03: Model comparison uses identical scenarios, contracts and metrics.
- C-04: Reliability, factuality, latency and fallback are reported separately.
- C-05: No live evaluation exceeds its authorized request cap or uses paid
  routing.
- C-06: Privacy constraints are documented and tested where automatable.

### 6.4 Risks and stop conditions

- Risk: optimizing concision could remove required policy cautions.
  Mitigation: cautions are mandatory and scored separately.
- Risk: model comparison can exhaust free quotas.
  Mitigation: hard caps, stop conditions and no retries.
- Stop if a proposed evaluation requires paid inference, real customer data or
  changing F-05's authorized model boundary.

## 7. Cross-cutting architecture rationale

- Keep the current boundary: the LLM chooses tools and language; host code owns
  validation, retrieval, evidence and fallback. F-06 must not move authority into
  the model.
- Prefer deterministic, testable transformations over heuristic text repair.
- Preserve all F-01/F-02 read-only contracts and F-05 deadline/security behavior.
- Treat benchmark fixtures as protocol evidence, not proof of semantic truth.
- Make every proposed metric independently measurable and independently reported.

## 8. Dependencies and sequencing

1. Owner approval of F-06 scope and priority order.
2. Workstream A design and tests.
3. Workstream B dataset and calibration design.
4. Workstream C rubric and evaluation protocol.
5. Separate implementation plans and gates for each workstream.

No workstream may begin implementation without its own approved spec and plan.

## 9. Global stop conditions

Stop and request owner review if any proposed change:

- requires a new dependency, framework, database or persistent service;
- weakens F-01/F-02 contracts or F-05 deadlines/security guarantees;
- requires paid inference or paid provider fallback;
- uses real customer data or sensitive conversations;
- automatically changes the default model or allowlist;
- claims implementation of F-06 without separate Gate S/P/I/V approval.

## 10. Status statement

F-06 is a **proposal only**. It is not implemented, not tested as a feature and
not part of the F-05 release candidate. The F-05 runtime, tests, model
configuration and verification evidence remain unchanged by this document.
PY