# F-04 — Evaluation, Reproducibility & Portfolio Delivery

**Version:** 1.0 — approved 2026-11-02
**Status:** APPROVED — Gate S passed by explicit owner authorization (2026-11-02)
**Prepared:** 2026-11-02
**Baseline:** `main` merge `7baac223dd86ad51b0c28513210727dc4ad474a2` (F-03 PR #3)
**Product:** Music Store AI Agent — fictional Empório da Música demonstration

## 1. Mission and source of truth

Produce a complete, independently reproducible public-portfolio submission for the existing CLI chatbot. Preserve the F-01 catalog, F-02 policy and F-03 real Nemotron integration. The source-of-truth hierarchy in the approved constitution remains authoritative. This feature is documentation, reproducibility, acceptance evaluation, modest *evidence-driven* response hardening, and packaging; not a new product architecture.

**Current verified baseline:** F-01/F-02/F-03 merged; 448 pytest tests passed; four real Nemotron scenarios reported PASS, with one unsupported phrase ("aplicado no checkout") in a combined answer. There is no `README.md` on current remote `main`. Prior user changes to `AGENTS.md`, `docs/PROJECT_CONSTITUTION.md` and untracked `.vscode/` are outside F-04 scope and must be preserved exactly.

## 2. In scope

1. Public-facing English `README.md` using **Music Store AI Agent** branding; concise problem, architecture, flow, CLI demonstration, function-call list, data/policy provenance, verified results, system limitations, installation, runtime configuration, and AI-assistance disclosure.
2. Exact quick-start from a **fresh checkout**: Python 3.11+, virtualenv, `pip install -e '.[dev]'`, build catalog, build policy index, private environment configuration and `python -m app`. Include no-secret offline test and `--debug-tools` examples; mark that real OpenRouter API calls require a user-provided key and free availability.
3. Three to five **genuine** pt-BR conversation transcripts recorded from actual real-model execution. At least one catalog, one policy, one mixed-source/tool scenario and one explicitly out-of-scope; a fifth follow-up is optional. Each transcript includes actual user/assistant utterances, model ID, observed allowed tool names and minimal source references. If prior F-03 machine evidence includes actual complete text, reuse it after validating provenance; otherwise execute limited real cases with approved free model. **Never author simulated dialogue as actual runtime evidence.**
4. An end-to-end acceptance matrix tracing required functionality to tests, live calls and authentic transcripts. Record gaps, warnings, and environment/setup details accurately, including the unsupported checkout wording and free-provider limitations.
5. Read-only final security/publication audit: no `.env`, keys, credentials, local indices/databases, personal information, or private data in newly committed files. Original fictional source materials were previously authorized for publication; do not expand to new datasets.
6. Final clean-checkout reproducibility test in a temporary clone outside the active worktree; verify install, both generators, pytest and CLI `--help` without credentials and without a paid API call. Keep temp artifacts out of Git and do not modify the user's working copy.
7. A short `docs/verification/F-04-verification.md` and a delivery checklist with actual repository URL, reviewed HEAD, and submission-status placeholder pending user's explicit action. Confirm **actual recruiter instructions** before claiming any channel, filename, deadline or format. Do not auto-submit.
8. Targeted patch+regression test **only if required by concrete acceptance failures** (e.g. false checkout claim); preserve existing public interfaces and all 448 F-03 baseline tests. No speculative changes.
9. Prefer neutral **portfolio branding** across newly authored public-facing materials; never present the work as official/unaffiliated endorsement. Accurately describe it as a prototype built using a provided fictional challenge dataset and manual, not as invented original company records.

## 3. Out of scope

Flask, FastAPI, web UI, production hosting, Docker, database migration, multi-user services, CRM, order access, actual payments, promotions calculation, new LLM providers, paid APIs, network deployment, rewriting Git history, replacing existing authorized source data, or altering GitHub privacy settings. Do not modify `AGENTS.md`, constitution or historical F-01/F-02/F-03 specs to purge a recruiter name: that is a separately governed cleanup and cannot erase already published history.

## 4. Acceptance criteria

- **AC-01 README:** A first-time reader can identify purpose, differentiators, architecture, four tools, limitations and live provider; headline and pitch carry independent portfolio branding.
- **AC-02 Quick start:** Exact documented commands from clean checkout produce local artifacts, pass tests, and start the CLI with private configuration; no unstated local dependencies.
- **AC-03 Provider safety:** `.env.example` contains placeholders only; README pins `nvidia/nemotron-3-ultra-550b-a55b:free` as tested model, explicitly notes model availability/quotas and no paid fallback; no secret exposed.
- **AC-04 Genuine examples:** 3–5 real pt-BR transcripts, with source provenance and actual tool names. Out-of-scope behavior included. No fabricated responses or sanitized text misrepresented as literal output.
- **AC-05 Functional evaluation:** catalog search and availability; policy search/citations; mixed tool invocation; safe out-of-scope answer; tool failure fallback; contradictions/unknown facts represented in matrix with evidence.
- **AC-06 Regression:** full pytest >=448 passing without weakening tests; `pip check`, `git diff --check` and no API calls during offline tests.
- **AC-07 Source integrity:** original six CSVs and original PDF stay byte-identical; generated `.sqlite`/JSON remain ignored.
- **AC-08 Public/privacy audit:** no secrets, private traces, unapproved external services, or new raw personal/order disclosures in additions. Historic source publication is documented as owner-authorized.
- **AC-09 Minimalism:** no unapproved framework/backend, no existing public tool API changes, no rewriting history; preexisting local changes preserved.
- **AC-10 Delivery clarity:** explicit latest commit SHA, verification commands, limitations, GitHub URL, AI-assisted development disclosure and final exact submission instructions confirmed (or marked pending, never guessed).
- **AC-11 Genuine status:** never claim submission, clean-clone success, an actual model response or Gate D completion without observed evidence; no repository modifications after final submission.
- **AC-12 Grounding caveat:** report that the previous live combined query used unsupported “aplicado no checkout”; either show a narrowly tested fix or keep it clearly documented, without claiming all hallucinations eliminated.

## 5. Public branding and provenance

Preferred title: **Music Store AI Agent**. The company/recruiter proposing the challenge need not appear in headline, GitHub description or product pitch. Do **not** misrepresent third-party data/manual as user-authored; describe their *provided fictional challenge* origin without promotional language. Original historic Git commits and previously merged documentation may retain recruiter mentions; editing current files would not erase history. A complete historical purge requires separate approval and risk review, and is excluded before the deadline.

## 6. Verification and authorization boundaries

Gate S approves this spec; Gate P approves the linked plan. Implementation and limited real free-model examples require explicit approval. Committing, pushing, opening/merging a PR and final external submission are separate actions requiring explicit authorization. The owner supplies any private key only through ignored local `.env`; no key goes into transcripts or Codex outputs. Report `BLOCKED` rather than inventing a successful step. A demo using mocked model is not a substitute for a genuine example.
