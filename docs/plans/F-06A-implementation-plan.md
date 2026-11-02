# F-06A — Implementation Plan

**Version:** 0.1\
**Status:** APPROVED — Gate P, explicit owner authorization supplied 2026-11-02\
**Prepared:** 2026-11-02 (BRT)\
**Spec:** [F-06A specification v0.1](../specs/F-06A-catalog-retrieval-grounding.md)\
**Baseline:** `main @ 6d83c45484d31284fc6653b72d5b77c07ed6a888`

## Authority and preflight

The owner's attached request explicitly approves F-06A v0.1 Gate S and Gate P
and authorizes local implementation and offline verification. The spec and plan
files were absent at preflight; these versions record the supplied scope and
its minimal implementation details, not unseen prior document wording. This
record grants no external-service, Git-publication or Gate V approval.

Observed preflight: branch `main`, HEAD exactly matching the authorized SHA,
only pre-existing `.vscode/` untracked. Root agent observed the baseline command
`.venv/bin/python -m pytest -q`: **633 passed in 15.10s**. The private `.env` and
untracked `.vscode/` must be preserved. `docs/decisions/` contains no decision
files. Relevant F-05 specs/plans/verification and the proposed F-06 roadmap are
context; the explicit F-06A owner request supplies this feature's authorization.

## File-level changes

| File | Minimal change | AC coverage |
| --- | --- | --- |
| `app/agent/orchestrator.py` | Exact monetary-token parsing, narrowly verified current-turn budget clauses, and private current-turn search-parameter provenance for completeness/scope/minimum validation | AC-01–06, AC-09 |
| `app/agent/prompt.py` | Explain budget/price separation, completeness requirements and bounded scoped-minimum wording; retain semantic model tool selection | AC-03–06, AC-09 |
| `tests/test_f06a_reliability.py` | Additive offline RED/GREEN and adversarial regressions | AC-01–09 |
| `README.md` | Describe only verified outcomes and remaining limitations | AC-07–09 |
| `docs/specs/F-06A-catalog-retrieval-grounding.md` | Version supplied owner-approved requirements and provenance | Governance |
| This plan | Version supplied owner-approved scope and local workflow | Governance |
| `docs/verification/F-06A-verification.md` | Actual commands/results, AC mapping, security review and limitations | AC-07–09; human Gate V review |

All other files stay unchanged, including existing tests, F-01/F-02 contracts,
catalog SQL, dependencies, provider configuration, deadlines/workers/diagnostic
contracts, `.env`, `.vscode/`, `AGENTS.md`, the constitution and all source or
generated data. No new dependency or migration is planned.

## Implementation sequence

1. **PHASE 0 — Preflight.** Read governance in order; confirm branch, HEAD and
   status; stop on baseline mismatch. Read only relevant implementation/test
   contracts. Establish the 633-test baseline before changes.
2. **PHASE 1 — RED.** Add deterministic tests for supported BRL punctuation,
   explicit customer budgets and unsupported lowest-price claims based on a
   truncated result. Include negative security controls before changing runtime
   code. Record actual failures and distinguish reproduced defects from already
   correct rejection behavior.
3. **PHASE 2 — Minimal correction.** Parse BRL into integer cents with strict
   malformed-token rejection. Pass the current customer turn privately to final
   validation. Budget quoting uses a complete affirmative customer declaration
   and an answer starting with the exact standalone budget clause, followed
   only by explicit full-name catalog product/price pairs. This closes implicit
   reuse such as "the product costs that amount". Other customer requests can
   receive supported product prices without quoting their budget. All remaining
   amounts retain tool-evidence checks.
4. Preserve validated current-turn `search_products` arguments privately beside
   their original result. Do not alter serialized tool messages, schemas or
   dispatch. Validate minimum claims against one complete search and its
   parameters, without combining partial evidence or inferring a wider scope.
   Update the prompt to request sufficient retrieval and bounded wording.
5. **PHASE 3 — GREEN.** Run the targeted regression file, then the full offline
   suite. Preserve every existing test and assertion. Resolve failures inside
   scope; do not add speculative argument normalization.
6. **PHASE 4 — Review.** Inspect monetary boundaries, provenance separation,
   scope/completeness, minimum identity, read-only behavior, policy cautions,
   current-turn/injection guards and sanitized diagnostics. Review the diff,
   dependency changes and `git diff --check`.
7. **PHASE 5 — Evidence.** Record actual RED/GREEN/full-suite commands, AC mapping,
   unchanged boundaries and limitations. Update README claims only from observed
   results. Stop for human Gate V review; do not commit or publish.

## Bounded comparison design

The host may accept an explicitly scoped full-answer minimum statement such as:

```text
Na categoria Violões, o menor preço disponível é NOME por R$ 429,90.
Na busca por "violão", o menor preço disponível é NOME por R$ 429,90.
```

Require one successful current-turn search with matching validated arguments,
`truncated` exactly `false`, `returned` matching the product count, coherent
snapshot provenance, available products and no price bounds. Category wording
requires the exact category without a narrower query; query wording requires
that exact lexical query without a narrower category. The named product and
exact integer-cent price must attain the minimum of that complete result.
Equivalent narrower implementation wording is acceptable only with the same
fail-closed evidence requirements.

Unqualified global comparisons, incomplete metadata, details-only evidence,
wrong or ambiguous scope and merging partial searches fail closed. Existing
result/output limits remain binding. This validates an explicit retrieval
scope, not arbitrary natural-language entailment.

## Test cases and acceptance mapping

| AC | Planned evidence |
| --- | --- |
| AC-01 | Supported comma/period/semicolon and other ordinary punctuation; thousands formatting and exact cents |
| AC-02 | Fabricated prices, malformed amounts, extra decimal digits and one-cent mismatches stay rejected |
| AC-03 | Explicit current-turn budget accepted only in its budget clause; unsupported budget, stale provenance and budget-as-product-price rejected |
| AC-04 | Complete matching scoped search accepts the actual minimum; wrong product or price rejected |
| AC-05 | Truncated, missing/invalid metadata, narrow filters, wrong scope, details-only and partial-union comparisons rejected |
| AC-06 | Existing validator continues rejecting unknown fields, invalid units/types/ranges, duplicate keys and ambiguous arguments |
| AC-07 | Record observed RED before correction and targeted GREEN afterward |
| AC-08 | Full offline suite includes all 633 unchanged existing tests |
| AC-09 | Existing and additive current-turn, source/injection, read-only, policy-caution and sanitized-diagnostic checks; diff review |

Tests must not instantiate a production model transport or contact an external
provider. Any local source inspection is read-only and must not rebuild or
modify generated artifacts.

## Risks, rollback and stop conditions

Strict budget/comparison wording may reject valid paraphrases; document that
limitation. A complete query result does not establish a semantic category-wide
minimum. More than 50 matches or oversized tool output may prevent completeness.
Recognized minimum phrases are guarded; exhaustive natural-language entailment
is not claimed. A budget-containing answer cannot mix arbitrary policy prose;
omit the budget quote for that composition, preserving normal policy cautions.
Offline fixtures cannot prove real-model adherence or improved latency.

Rollback requires reversing only these task-owned changes and removing only the
new F-06A artifacts if requested. Preserve user files and concurrent work; no Git
history rewrite or data migration is needed.

Stop if AC-03/04/05 needs changes beyond approved files/contracts, a dependency,
weakened safety controls, real inference or provider/model changes. Do not infer
the cause of historical Nemotron invalid arguments without raw evidence. Gate V
remains **PENDING OWNER REVIEW**, even when all local checks pass. No commit,
push, PR, merge or submission is authorized.
