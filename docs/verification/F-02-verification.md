# F-02 — Verification Evidence

**Date:** November 2, 2026 (BRT)\
**Feature:** Grounded Store Policy Retrieval\
**Baselines:** approved F-02 specification v1.0 and implementation plan v1.0\
**Branch / HEAD:** `main` / `b7f782a4e8cb21ad02fb558f76eaebb3efabeb9d`\
**Gates:** C/S/P approved; implementation authorized and completed; **Gate V pending human review**.

## Scope and environment

Implemented the four `app/policy/` modules, index-builder script, three policy
test modules, and one dependency declaration: `pypdf>=6,<7`. Reused `.venv/`
(Python 3.14.4); installed pypdf 6.21.4, which has no additional dependencies.
F-01 application modules and tests were not changed. No model, network service,
embeddings, order processing, or customer CLI was added. Dependency installation
used the package registry; policy extraction, retrieval, and tests run locally.

Pre-existing modifications to `AGENTS.md` and the constitution were preserved.
The approved F-02 spec/plan and original PDF were already untracked at preflight;
they were not edited. `docs/decisions/` had no files. Prior F-01 verification was
read; its current 114-test baseline was independently reproduced.

## RED → GREEN evidence

- Before implementation, each new test module failed collection with
  `ModuleNotFoundError: app.policy` (one collection error per focused run).
- Review added four unrelated-context cases sharing a policy word: four failed,
  eight existing no-match cases passed. Conservative vocabulary support and
  lexical overlap thresholds fixed those failures.
- A precise PAC query exposed an incidental customer-service match: one failed,
  two related precision cases passed. Stronger body-only relevance fixed it.
- Identical PDF bytes under another filename initially yielded different index
  bytes: one test failed. Canonical original-document filename metadata fixed
  reproducibility without changing extracted source text.
- Source-derived cautions cover lexical-only matches as well as topic aliases,
  before applying the public result limit.

## Executed verification

```bash
.venv/bin/python -m pytest -q
```

Final result: **265 passed in 5.23s; 0 failed; 0 skipped**.
Breakdown: 44 source tests, 57 search tests, 50 safety tests, 114 unchanged F-01
tests. Before implementation, the full baseline also returned 114 passed.

```bash
.venv/bin/python -m pytest -q --ignore=tests/test_policy_search.py --ignore=tests/test_policy_source.py --ignore=tests/test_policy_safety.py
```

Separate F-01 regression result: **114 passed in 0.43s**. The final full suite
also includes all 114 tests and the three existing catalog-tool contracts.

```bash
.venv/bin/python -m pip check
git diff --check
.venv/bin/python -m scripts.build_policy_index --input 'resources/políticas_da_loja.pdf' --output data/generated/policy_index.json
```

Observed: no broken requirements; no tracked-diff whitespace errors; builder
exit 0, document version 2.1, **8 physical pages / 28 numbered sections**.
The generated index is ignored by Git. Source and index identities:

| Artifact | Observed |
| --- | --- |
| Original PDF size | 180,519 bytes |
| Original PDF SHA-256 before and after | `b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7` |
| Canonical JSON SHA-256 | `78207611032d03efade012d06dfc6dd86d7ebe509ada17afdf4ce6175275a7e1` |

Repeated actual builds produced byte-identical JSON. The independent complete
text check reconstructs cleaned physical pages 2–8 from all 28 excerpts exactly
(10,670 characters), including headings, tables, bullets, numbered steps,
conditions, negations and continuation text. The cover is separately retained.

## Required real-source probes

All 12 plan questions passed against the generated default index using the
public tool, separately from temporary test fixtures. Tests also assert exact
source excerpt equality, expected clauses, and physical citations.

| Plan question / topic | Actual returned sections (physical PDF pages) |
| --- | --- |
| Saturday hours | 2 (2); 09:00–13:00, Sundays/holidays closed |
| PIX discount | 3 (3), 6.2 (6), 6.1 (6); discount and non-stacking clause retained |
| Credit card in 5 installments | 3.1 (3), 3 (3); installment-conflict caution |
| Online withdrawal | 4.1 (4), 4 (4); 7 calendar days and refund conditions retained |
| Defect and warranty | 4.2 (4), 8.1 (7), 8.2 (7); distinct 30-day exchange / 90-day legal-warranty passages |
| Campo Grande freight | 5.1 (4), 5.2 (4–5), 5 (4); threshold and fixed fee retained |
| PAC outside Campo Grande | 5.2 (4–5); 5–12 business days, no calculated freight quote |
| Black Friday plus PIX | 3 (3), 6.2 (6), 6.1 (6); non-stacking and non-live-promotion caution |
| WhatsApp contact | 7 (6), 1.2 (2), cover (1); contact-conflict caution |
| Personal data / LGPD | 9 (7–8); purposes, explicit consent and non-sharing clauses |
| Accessories | 1 (2), 7.1 (6); instruments-only restriction retained |
| Weather on Mars | No matches |

Source correction recorded without editing approved documents: the ambiguity
table describes §4.1 as pages 4–5 in one row, but the actual PDF and the plan's
probe table place it entirely on page 4. The index cites `[4]`. Multi-page
sections are §5.2 `[4,5]`, §7.2 `[6,7]`, and §9 `[7,8]`.

## Acceptance trace and security review

| AC | Evidence |
| --- | --- |
| 01–03 | Original PDF hash/pages/28 headings; complete text reconstruction; deterministic builds including renamed byte-identical inputs; unchanged PDF |
| 04 | Exact two-argument public signature/envelope; query and integer-limit bounds; boolean rejection; JSON serialization |
| 05–06 | All required real-source questions; Portuguese aliases/case/accents; every section's exact physical-page map |
| 07–08 | Numeric section-ID tie-break; stable rank/limits/counts/truncation; irrelevant-context and incidental-word regressions |
| 09–11 | Contact/installment conflicts; separate exchange/warranty; historical promotions and PIX rule; cautions retained at limit 1 and for lexical-only matches |
| 12 | Malformed PDFs/indexes, missing mandatory sections, wrong metadata/schema/provenance, encrypted/empty sources, sanitized exceptions, atomic-replace failure and prior-artifact preservation |
| 13 | Query/source injection text stays data; runtime tests block network, subprocess, shell, SQLite and access to any file except the configured read-only index |
| 14 | Controlled small PDF/page fixtures and corrupted-index cases, plus original-source smoke checks |
| 15 | All 114 original F-01 tests pass; catalog code/tests unchanged |

Reviewed implementation, tests, dependency diff and generated output. Only the
approved pypdf dependency was added. Runtime retrieval imports standard-library
code; pypdf is loaded lazily during extraction. The tool does not write files,
execute excerpts/queries, make API calls, access private datasets, process
refunds/complaints, or perform handoff actions. Public failures use fixed
sanitized envelopes without paths, exception text or source bytes. New text
files also undergo `git diff --no-index --check` because untracked files are
absent from ordinary `git diff`.

## Limitations and handoff

- Retrieval is a conservative lexical prototype with a finite alias map;
  unfamiliar phrasing can return no match. It does not perform semantic inference.
- The June 2025 manual is dated and contains unresolved contact/installment
  contradictions. Cautions preserve these uncertainties; no active campaigns,
  live inventory, shipment status or operational SLA is asserted.
- The generated JSON is a local artifact validated structurally and against the
  approved PDF identity; it is not a signed artifact. Retrieved text remains
  untrusted data for future F-03 composition.
- No commit, push, PR, deployment, publication, submission or paid/model use
  occurred. Gate V remains pending human review; there are no implementation
  blockers.


**Gate V:** APPROVED — technical evidence reviewed; owner authorized PR lifecycle on November 2, 2026.
