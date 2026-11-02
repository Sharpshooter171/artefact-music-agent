# F-02 — Grounded Store Policy Retrieval

**Project:** Empório da Música / Artefact AI Engineer Challenge
**Version:** 1.0 (approved)
**Status:** APPROVED — Gate S PASSED (human authorization, November 1, 2026)
**Prepared:** November 1, 2026
**Owner:** Human architect; Gate S and P approved on November 1, 2026; coding agent authorized to implement F-02 only.

## 1. Purpose

Provide deterministic, offline, **read-only retrieval of source-grounded store policies**, suitable for F-03's real LLM tool calling. An LLM can compose the customer-facing answer, but must not invent policy facts or treat retrieved policy text as instructions. This feature does **not** implement the agent, CLI, model calls, promotions/order lookup, calculations, transactions, or human handoff actions.

### Source of truth and verified observations

- Original supplied source: `políticas_da_loja.pdf` (Empório da Música, **version 2.1, June 2025**).
- Source PDF SHA-256: `b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7`.
- **8 physical pages**; cover = PDF page 1; sections numbered **1–10 with 28 total numbered sections/subsections**, on PDF pages 2–8. The pages printed in the document correspond to the same PDF page numbers.
- The manual itself is marked *“Documento interno — Uso restrito da equipe de atendimento”*. The project owner explicitly authorized public GitHub publication of this fictional PDF for this challenge on November 1, 2026.
- The policy PDF governs *policy facts*; the F-01 SQLite catalog governs *actual provided product prices, availability, and counts*. Policy text about “more than 300 instruments” is not evidence that 300 items exist in the supplied 65-row catalog.

## 2. Contract and scope

### Source and generated paths

- Expected local source: `resources/políticas_da_loja.pdf` (unchanged source bytes).
- `EMPORIO_POLICY_PDF` or `--input` overrides source path only for the index builder.
- Generated index: `data/generated/policy_index.json` (ignored by Git); `EMPORIO_POLICY_INDEX` overrides query-time location.
- Builder CLI: `python -m scripts.build_policy_index --input 'resources/políticas_da_loja.pdf' --output data/generated/policy_index.json`.
- Add **one** PDF extraction dependency (`pypdf`, pinned to a compatible major range) in `pyproject.toml`; retain existing runtime dependencies and F-01 contracts. No network/model/vector database, embeddings, LangChain, web API, or external text-extraction binary.

### Public Python tool

```python
def search_store_policies(query: str, limit: int = 3) -> dict:
    """Read-only retrieval of relevant original manual sections."""
```

- `query`: required string, 3–240 characters once trimmed, nonempty after text normalization; sanitize/validate type; literal user text is never executed.
- `limit`: integer 1–5, reject bool. No other public parameters.
- Success envelope:

```json
{
  "ok": true,
  "data": {
    "matches": [
      {
        "section_id": "4.1",
        "title": "Direito de Arrependimento (Compras Online)",
        "content": "<actual extracted policy excerpt>",
        "pages": [4]
      }
    ],
    "cautions": [
      {"code": "...", "message": "...", "pages": [2, 3]}
    ]
  },
  "meta": {
    "source_sha256": "<64-character SHA-256>",
    "document_version": "2.1",
    "returned": 1,
    "truncated": false
  }
}
```

`content` is **original-source extracted text** with only whitespace/layout cleanup, not an LLM-generated paraphrase or a hard-coded answer. Preserve numbers, currency, periods, conditions, and negations. Page citations are mandatory. `truncated` refers to additional matching sections beyond the limit (never silently cut a returned section's text). No-match returns `ok=true`, `matches=[]`, `returned=0`, with no fabricated substitute policy. A relevance threshold prevents generic/out-of-domain queries from matching a section by incidental words.

- Error envelope mirrors F-01: `{"ok": false, "error": {"code": "...", "message": "...", "details": {}}, "meta": {"source_sha256": null}}`.
- Error codes: `INVALID_ARGUMENT`, `POLICY_UNAVAILABLE` (missing/corrupt/unreadable index or unsupported index schema), `INTERNAL_ERROR`. No stack traces, raw system paths, file bytes, credentials, or exception messages in public errors.
- No policy excerpt from a failed build or an index with missing mandatory sections is served.

### Internal index format

Deterministically extracted from the **original PDF**, not authored synthetic policy data. Store: `schema_version=1`, `document_version=2.1`, `source_filename`, `source_sha256`, `page_count=8`, ordered `sections` with `section_id`, `title`, `content`, `pages`. A separate optional `cover` entry may carry page 1 contact/metadata text. Validate unique IDs, logical order, nonblank text, source provenance and all 28 expected section IDs. Reject unsupported version, empty PDF, missing headings, wrong page count or unexpected document identity. Serialize JSON deterministically (`sort_keys`, UTF-8, stable whitespace) and replace the existing index atomically only after complete validation. Repeated builds from identical source bytes yield the same canonical index bytes. Do not write artifacts into `resources/`.

## 3. Extraction and retrieval rules

1. Extract by physical PDF page with `pypdf` in a deterministic local builder, retaining page-to-text provenance.
2. Recognize **only** the observed 28 policy headings, not numbered list items such as the five steps under §7.2. Sections may span page boundaries (§5.2, §7.2, §9). Preserve contiguous continuation text and both page numbers.
3. Remove repeating page headers/footers and normalize incidental whitespace, but never alter policy terms, amounts, dates, punctuation, or negations. Validate table text and bullets are represented (payments, hours, freight).
4. Retrieval is deterministic and bounded: normalize case/accents/spacing; tokenize with Portuguese stopword filtering; match section titles, exact content tokens and a **small explicit topic/synonym map**. Suggested topic families: hours; address/contact/WhatsApp; PIX/payment/installments; return/exchange/defect/withdrawal; freight/shipping/tracking; promotions; customer service; warranty; privacy/LGPD; instrument-only catalog. Keep ranking stable with a section-ID tie-breaker. Never use dynamic SQL or run arbitrary text as instructions.
5. Multi-policy requests can return multiple sections up to the caller's limit; critical cautions must **not** disappear because a matched section was truncated by the limit. Include pagination metadata and `truncated`.
6. Treat customer query, PDF text and returned excerpts as **untrusted data**, not as assistant/system instructions. F-03 receives excerpts as tool results, with citations; it must not re-interpret source text as commands.
7. This source is a dated June 2025 manual. Seasonal campaigns are **descriptions of possible promotions**, not evidence of active November 2026 discounts. No freight quote, current inventory, order status, refund action, complaint registration or SLA should be asserted without a matching implemented source/capability.

## 4. Mandatory ambiguity and boundary handling

The source has material tensions; make them visible using deterministic `cautions`, keyed by the user's topic, with relevant physical page references (not a fabricated corrected value):

| Topic / caution code | Observed PDF passages | Safe behavior |
| --- | --- | --- |
| `CONTACT_CONFLICT` | Cover page 1 and §1.2 page 2 use phone/WhatsApp `(67) 3341-4444`; §7 page 6 calls `(67) 3321-4500` the WhatsApp number. Cover email and §1.2 email differ in spelling/accent. | Return the relevant source sections and flag conflicting contact details. F-03 must not present a single definitive WhatsApp or email without confirmation. |
| `INSTALLMENT_CONFLICT` | Payment table on page 3 states credit-card minimum installment `R$ 100`; §3.1 on the same page has differing thresholds for installments 1–3, 4–6, 7–12. | Return §3 and §3.1 together when applicable; flag inconsistency rather than invent a single threshold. |
| `WARRANTY_PROCEDURE_DISTINCTION` | §4.2 page 4 describes exchange for manufacturing defects within 30 days after purchase; §8.1 page 7 states a 90-day legal warranty from receipt. | Distinguish store exchange procedure from legal warranty, never represent 30 days as the total warranty. This is a distinction, not proof that either clause cancels the other. |
| `PROMOTION_NOT_LIVE` | §6 page 6 lists example/seasonal campaigns; §6.2 forbids stacking PIX with promotion. | Do not imply any named promotion is currently active or provide live promotional prices. |
| `ACTION_NOT_IMPLEMENTED` | §7.3 page 7 addresses complaints and escalation; §4.1 pages 4–5 address refund; §5.3 page 5 describes tracking codes. | F-02 only provides policy knowledge. No claims that a complaint, refund, shipment or human handoff has actually been processed. |

Do **not** silently reconcile these with outside legal advice or common sense. Explicitly mention in future README that the manual may be outdated and contains contradictions.

## 5. Acceptance criteria

- **AC-01** — Reproducibly index the original 8-page PDF and verify source SHA-256, document version, all 28 numbered sections, and physical page provenance.
- **AC-02** — Preserve original PDF bytes and produce deterministic index output across repeated builds.
- **AC-03** — Extract/retain multi-page continuations, bullet lists, currency, percentages, tables and meaningful negations without missing essential clauses.
- **AC-04** — Public `search_store_policies` signature, envelope, types and bounded result contract are exact.
- **AC-05** — Relevant accent/case-insensitive Brazilian Portuguese questions retrieve the correct policy sections (at least hours §2, payment §§3/3.1, online withdrawal §4.1, defective exchange §4.2, local shipping §5.1, other-city freight §5.2, promo-stacking §6.2, warranty §8.1, privacy §9).
- **AC-06** — Correct page citations for every retrieved section, including multi-page §§5.2, 7.2 and 9.
- **AC-07** — Deterministic rank, tie-break, `limit`, `returned`, `truncated`, and stable results for repeated queries; no unbounded document dump.
- **AC-08** — Irrelevant/out-of-scope questions return empty matches, not inferred policy facts.
- **AC-09** — Known phone/email and installment contradictions trigger relevant cautions with correct page numbers and no invented resolution.
- **AC-10** — Defect exchange and legal warranty both retrievable; distinguish 30-day and 90-day rules, and never replace one with the other.
- **AC-11** — Historical promotion descriptions never become live pricing/active-campaign claims; non-stack rule retained.
- **AC-12** — Missing/corrupt/unsupported index and malformed source fail closed with sanitized errors; an existing valid index survives a failed rebuild.
- **AC-13** — No PDF or query string is executed as code/instructions; no network/LLM calls, SQL, private order access, or customer data processing.
- **AC-14** — `pytest` offline synthetic/controlled fixtures include malformed PDFs or index cases; real-source smoke suite demonstrates policy accuracy and reports no fabricated content.
- **AC-15** — F-01's 114 baseline tests and all three catalog tool contracts continue to pass unchanged.

## 6. Human decisions / gates

- **Gate S — APPROVED** — Retrieval contract and ambiguity strategy approved by the human owner on November 1, 2026.
- **Gate P — APPROVED** — One bounded `pypdf` dependency, file-level implementation plan, and publication of the original fictional policy PDF authorized by the human owner on November 1, 2026. The source PDF must remain byte-identical.
- **Gate I/V** — Coding agent implements TDD, returns real test/smoke evidence and stops without commit/push until human review.
- No paid services or LLM calls are authorized for F-02.
