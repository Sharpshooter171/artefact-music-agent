# F-06A — Catalog Retrieval & Grounding Reliability

**Version:** 0.1\
**Status:** APPROVED — Gate S, explicit owner authorization supplied 2026-11-02\
**Prepared:** 2026-11-02 (BRT)\
**Baseline:** `main @ 6d83c45484d31284fc6653b72d5b77c07ed6a888`\
**Plan:** [F-06A implementation plan](../plans/F-06A-implementation-plan.md)

## Approval provenance

The owner's attached implementation request states that F-06A specification
v0.1, AC-01–AC-09 and implementation plan v0.1 were approved in the ChatGPT
governance review, and explicitly authorizes local implementation. These files
were absent at preflight. This document records the supplied requirements and
authorization; it does not claim to reproduce unseen prior document wording or
self-approve any gate. Gate V remains pending human review.

The general F-06 roadmap remains a proposal. This authorization covers only
F-06A and does not approve its other workstreams, argument normalization,
model evaluation or external actions.

## Problem and user story

As a customer asking about instruments and a spending limit, I need supported
prices to survive ordinary punctuation, my budget to remain distinguishable
from store prices, and any lowest-price recommendation to use complete,
relevant catalog evidence.

- **R-01:** A supported amount followed by punctuation, such as
  `R$ 459,90, conforme...`, can incorrectly fail grounding.
- **R-02:** A customer budget such as `R$ 500,00` can fail when the amount is not
  a catalog price. Customer provenance must never establish a product price.
- **R-03:** The default alphabetically ordered ten-result search for `violão`
  omits the actual cheapest available model. The owner observed Rozini RC-104
  at `R$ 459,90` in the partial result (`truncated=true`), versus Tagima Memphis
  AC-39 at `R$ 429,90` in the complete 33-result search (`truncated=false`).

## Scope and contracts

The supplied CSV catalog remains the authority for product prices and
availability. The policy source text remains the authority for policy facts.
The current customer turn can establish only an explicitly stated personal
budget; it cannot establish store facts. Prior conversation is context, not
current-turn factual evidence.

The four read-only F-01/F-02 tool schemas and their result envelopes remain
unchanged. The LLM selects tools semantically. Host code validates the final
answer and evidence; it does not route customer intent by keywords.

Only the following files may change:

- `app/agent/orchestrator.py`
- `app/agent/prompt.py`
- `tests/test_f06a_reliability.py`
- `README.md` (verified outcomes and limitations)
- This spec, the F-06A implementation plan and
  `docs/verification/F-06A-verification.md`

No provider call, paid inference, model/provider/default change, dependency,
catalog SQL change, tool-schema change, raw/generated-data edit, `.env` or
`.vscode/` edit, governance-file edit, commit, push, PR, merge or submission is
authorized.

## Acceptance criteria

| ID | Required behavior |
| --- | --- |
| AC-01 | Accept valid supported BRL prices followed by ordinary punctuation. |
| AC-02 | Continue rejecting fabricated product prices. |
| AC-03 | Permit customer budget references only with verified provenance and without treating budgets as evidence of product prices. |
| AC-04 | Require complete relevant evidence before accepting a global lowest-price claim. |
| AC-05 | Reject unsupported global comparisons from truncated or insufficiently scoped results. |
| AC-06 | Preserve strict argument validation. Do not implement speculative normalization of invalid LLM arguments. Unknown fields and ambiguous units remain invalid. |
| AC-07 | Demonstrate RED tests for reproduced failures, then GREEN after correction. |
| AC-08 | Preserve all 633 previously passing tests. |
| AC-09 | Preserve source grounding, current-turn evidence, read-only tools, policy cautions, prompt-injection protections and sanitized diagnostics. |

## Bounded grounding behavior

Monetary parsing uses exact integer cents, including Brazilian thousands
separators. Punctuation is a token boundary, never permission to ignore malformed
amounts or unsupported prices.

Budget references require the entire current-turn customer message to be one
affirmative declaration, such as `Meu orçamento é R$ 500,00.`. The answer starts
with `Seu orçamento é R$ 500,00.` and can then contain only explicit
`FULL PRODUCT NAME por R$ PRICE.` clauses with exact catalog product/price pairs.
Only the verified budget clause is exempt from product-price validation. This
bounded full-answer grammar prevents prose such as "the product costs that
amount" from reusing a budget as a product price. There is no blanket whitelist
of customer numbers. Longer/ambiguous customer requests can receive supported
product prices without repeating the budget; other budget wording fails closed.

Lowest-price evidence requires the actual current-turn search parameters,
complete matching results and the claimed product/price minimum. Tool results
are not modified to add host metadata. Complete details for one product and
collections of partial searches do not prove a global minimum.

The minimal implementation can accept narrowly phrased, explicitly scoped
minimum claims backed by one complete search: an exact category scope or an
exact lexical-query scope. A query-scoped minimum describes that search's
matches, not an inferred semantic category. Unqualified global claims or scope
that cannot be established under existing contracts must fail closed. The
existing limit of 50 and tool-output budget can make a complete relevant search
unavailable; neither limit may be relaxed by this feature.

## Failure, privacy and security

Missing, stale, truncated, malformed or insufficiently scoped evidence produces
the existing safe fallback and human-confirmation option. Invalid arguments
continue to fail through existing validation without repair or retry. The
historical Nemotron `INVALID_ARGUMENT` calls did not retain raw arguments, so
their cause remains unknown.

Customer messages, catalog fields, policy text and tool results remain untrusted
data. Existing policy cautions and conflict handling, read-only dispatch,
deadlines, current-turn source checks, stock-count restrictions and sanitized
diagnostics remain required. No new raw arguments, customer text or tool payloads
may enter diagnostics or verification artifacts.

## Test strategy, dependencies and risks

Use deterministic offline regression tests with synthetic customer/model data,
plus existing read-only local retrieval where useful. Record RED before runtime
correction, targeted GREEN and the full unchanged baseline suite. Test valid
punctuation and exact cents alongside malformed/fabricated amounts; budget
provenance alongside product-price laundering and stale-turn attempts; complete
scope alongside truncation, details-only evidence, wrong scope, wrong minimum
and invalid arguments. Review security and policy regressions and map every AC
to observed evidence in the verification record.

No new dependency is required. The feature depends on existing F-01/F-02 tools
and F-03/F-05 orchestration. Conservative wording can reject valid paraphrases;
this is an explicit limitation, not a claim of general semantic validation.
The minimum detector covers recognized pt-BR comparison wording; it is not an
exhaustive natural-language entailment checker.
Offline tests do not establish real-model tool choice, latency or customer
experience. Stop if AC-03/04/05 cannot be implemented safely inside the approved
file and contract boundaries. Stop after local verification for human Gate V
review.
