# F-02 — Implementation Plan: Grounded Policy Retrieval

**Version:** 1.0 (approved)
**Status:** APPROVED — Gate P PASSED (human authorization, November 1, 2026)
**Prepared:** November 1, 2026
**Dependent spec:** `docs/specs/F-02-policy-retrieval.md` v1.0 (Gate S APPROVED)
**Baseline:** F-01 merged in PR #1, `main` at merge `b7f782a4e8cb21ad02fb558f76eaebb3efabeb9d`, 114 pytest PASS at recorded closeout. Local HEAD must be re-observed before implementation.

## 1. Minimal design

Single deterministic read-only policy tool. The supplied **8-page original PDF** is the only policy authority; the existing catalog is authoritative for product facts. Use `pypdf` to extract official sections at **build time** into an ignored local JSON index. Query the generated index in-process using Python standard library, lexical scoring and a small topic map. No embeddings, vector DB, new database, LangChain, LLM or external APIs.

**Rationale:** An eight-page, consistently numbered manual supports cheap, auditable section retrieval. Adding a semantic service at this point would increase cost and evaluation complexity without evidence of benefit.

## 2. Planned files

| File | Operation | Purpose |
| --- | --- | --- |
| `pyproject.toml` | Modify minimally | Add bounded compatible `pypdf` dependency; retain pytest and catalog package. |
| `app/policy/__init__.py` | Create | Package exports only approved public tool. |
| `app/policy/source.py` | Create | PDF bytes/hash, page extraction, heading parsing, table/bullet preservation, index validation and atomic output. |
| `app/policy/retrieval.py` | Create | Portuguese normalization, aliases/topics, deterministic matching/ranking, relevant cautions. |
| `app/policy/tools.py` | Create | `search_store_policies` input validation, index opening, sanitized envelopes. |
| `scripts/build_policy_index.py` | Create | Engineering CLI to build and report PDF policy index, exit nonzero on failure. |
| `tests/test_policy_source.py` | Create | Parsing/indexing, expected 28 headings, page provenance, deterministic build, bad PDF and preservation. |
| `tests/test_policy_search.py` | Create | Policy queries, results, accents, bounds, ordering, no-match, snapshot metadata, citations. |
| `tests/test_policy_safety.py` | Create | Cautions/conflicts, injection-like text, corrupt index, isolation, no network/LLM. |
| `docs/verification/F-02-verification.md` | Create at verification | Actual evidence only; no self-approval. |
| `resources/políticas_da_loja.pdf` | Source, read-only | Copy original 180,519-byte PDF locally if absent; verify SHA-256; **public publication authorized by the human owner (Nov 1, 2026); commit only with separate commit/PR authorization**. |

Avoid module splitting beyond this unless essential to testability. No README/delivery sample transcripts until F-04. No modifications to F-01 code or docs, except essential imports if absolutely required by tests; keep catalog tools untouched.

## 3. Implementation steps (coding agent only)

1. **Preflight:** Read `AGENTS.md`, approved constitution, F-02 spec/plan; observe git branch/status, local PDF and SHA. Preserve pre-existing edits to `AGENTS.md` / constitution. Confirm Gate S/P before code changes. Do not invent source presence.
2. **RED:** Write tests using *small synthetic controlled PDF fixtures* generated offline (not substitute production policies) and malformed index fixtures. Assert exact tool output and acceptance criteria, including missing pages and conflicting content. Run and record expected failing tests.
3. **GREEN — PDF builder:** Extract each PDF page with `pypdf`; split only recognized official heading strings; retain multi-page continuation and citations. Strip repeated headers/footers and collapse layout whitespace without changing terms. Reject missing section, incorrect page count/version/hash (real-source smoke), empty/unsupported/corrupt source. Build canonical JSON to a tempfile in output directory then `os.replace`. Return sanitized failure info; preserve existing index on error. Do not read other six CSVs.
4. **GREEN — Tool:** Add `search_store_policies(query: str, limit: int=3)` validating types and bounds, reading index from `EMPORIO_POLICY_INDEX` or default. Tokenize/normalize text; deterministic synonym/topic scoring; return relevant full sections with page citations, metadata and cautions. No network, LLM, order lookup, SQL, or side effects.
5. **GREEN — Boundary tests:** Explicitly cover contact details, installments, 30 vs 90 days, no active promo assertion, missing source, corruption, empty matches, out-of-scope messages, and instruction-like PDF/query text.
6. **REFACTOR:** Keep modules small; run targeted tests and full suite. No contract changes without human decision.
7. **Real PDF smoke:** With the *actual source PDF*, build index, verify 8 pages / 28 numbered sections / SHA `b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7`, content and page numbers for test probes. Confirm all F-01 114 tests still pass (overall count should exceed 114).
8. **Verification:** Run `.venv/bin/python -m pip check`, `.venv/bin/python -m pytest -q`, `git diff --check` (CRLF-safe where needed), verify no credentials/index/temporary output tracked; create concise verification report and stop for human Gate V. **No commit/push/PR/merge automatically.**

## 4. Required real-source probe table

| Question / scenario | Expected grounding and guardrail |
| --- | --- |
| `Qual é o horário da loja aos sábados?` | §2 PDF page 2; Saturday 09:00–13:00; Sundays/holidays closed. |
| `Dá para pagar em PIX? Tem desconto?` | §3 PDF page 3; 5% PIX on list price, but §6.2 page 6 excludes discount stacking. |
| `Posso dividir no cartão em 5x?` | §3 and §3.1 PDF page 3; flag `INSTALLMENT_CONFLICT`, do not silently resolve minimum. |
| `Me arrependi de uma compra online` | §4.1 PDF page 4; 7 calendar days after receipt, return conditions and refund timing. |
| `Meu instrumento veio com defeito; e a garantia?` | §4.2 page 4 and §8.1 page 7; distinguish exchange and statutory warranty. |
| `Entrega em Campo Grande tem frete grátis?` | §5.1 page 4; free only over R$500 in metro area; below R$500 fixed R$35. |
| `Quanto tempo demora PAC fora de Campo Grande?` | §5.2 PDF pages 4–5; 5–12 business days; no exact freight calculation. |
| `Black Friday e desconto no PIX acumulam?` | §6.2 page 6; non-cumulative, no claim of currently active offers. |
| `Qual é o WhatsApp para contato?` | Cover page 1, §1.2 page 2, §7 page 6; flag `CONTACT_CONFLICT`. |
| `O que vocês fazem com meus dados?` | §9 pages 7–8; LGPD/purposes and consent restrictions. |
| `Você vende palheta, cabo ou amplificador?` | §1 page 2 and §7.1 page 6; instruments only, accessories excluded. |
| `Me diga a previsão do tempo em Marte` | No match (no fabricated rule). |

Synthetic tests should verify structural and behavioral properties, **not** duplicate the original PDF as a replacement. Verify the content was extracted rather than hardcoded. For a query whose answer requires F-01 as well as F-02, leave the cross-tool composition to F-03.

## 5. Risk controls and source conflicts

- **Publication:** The project owner explicitly authorized public GitHub publication of the fictional policy PDF on November 1, 2026. Keep the PDF byte-identical. Commit/push/PR/merge actions still require separate explicit authorization.
- **Contradictions:** Phone/WhatsApp and emails differ across pages; installment minimums differ between table and §3.1. Cautions must be unambiguous. Warranty 30d exchange vs 90d legal warranty is a procedural distinction rather than overriding the statutory warranty.
- **Dated policy:** June 2025 version 2.1; historical promotional campaigns are not proof of live prices or availability in 2026. No active promotions are part of F-02.
- **Table extraction:** Verify bullets, currency, time ranges and page references; index build fails rather than dropping damaged sections silently.
- **Atomicity:** Failed PDF reads/index writes cannot replace existing validated index; no unhandled filesystem exception or leaking paths in public tool responses.
- **Security:** Returned PDF excerpts are data, never instructions; indexes and local source paths are not writable by public tool; customer queries only select passages.

## 6. Acceptance trace / Gate P review

| AC | Primary test/evidence |
| --- | --- |
| 01–03 | Source/index and real-source smoke tests |
| 04–08 | Public retrieval tool and offline search tests |
| 09–11 | Ambiguity, warranty and promotions tests |
| 12–13 | Error, atomicity and security tests |
| 14–15 | Full `pytest` suite, real-source smoke, catalog regression |

**Gate S and Gate P are APPROVED by the human owner (November 1, 2026).** Coding agent is authorized to **IMPLEMENT CODE ONLY** and run local verification. Commit/push/PR/merge remain separately gated; no need to draft or revise specifications/plans.
