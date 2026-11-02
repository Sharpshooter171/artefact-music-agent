# F-04 — Implementation & Delivery Plan

**Version:** 1.0 — approved 2026-11-02
**Status:** APPROVED — Gate P passed by explicit owner authorization (2026-11-02)
**Prepared:** 2026-11-02
**Spec:** `docs/specs/F-04-evaluation-delivery.md` v1.0
**Baseline:** `main@7baac223dd86ad51b0c28513210727dc4ad474a2`

## 1. Execution priority (deadline 2026-11-02 23:59 BRT)

This is the final minimum viable delivery. **README and clean-checkout come before polish.** Do not ask the coding agent to produce a new planning round. Avoid extra provider calls; reuse previously observed full, authentic F-03 outputs if available, otherwise capture only the missing real conversations using the approved free-only Nemotron and stop immediately on HTTP 429. Do not install any new application framework.

## 2. File changes

| Path | Responsibility |
| --- | --- |
| `README.md` | Create public portfolio entry with installation/run/test, architecture, legitimate technical provenance, live model config, limitations and AI-assistant disclosure. |
| `examples/README.md` and `examples/real-conversations.md` | 3–5 *authentic* user/assistant examples, tool trace summaries and source evidence, sanitized before committing. May use another similarly concise layout. |
| `docs/verification/F-04-verification.md` | Measured acceptance matrix AC-01…AC-12, clean-clone build/test transcript, full pytest, sanitization audit and pending delivery items. |
| `app/agent/*`, `tests/test_agent_*.py` | **Only** minimal patch/test if concrete grounded-response failure warrants it, notably unsupported 'checkout' language; do not proactively refactor. |
| `.env.example`, `pyproject.toml` | Audit only; change if reproducibility proves a real defect. |

Do **not** modify `AGENTS.md`, `docs/PROJECT_CONSTITUTION.md`, `.vscode/`, F-01/F-02 or F-03 historical docs, private `.env`, original PDF/CSVs, ignored `data/generated/`, or any Git history. No source material beyond previously authorized fictional sources may be published.

## 3. Verify working environment and read sources

1. Read `AGENTS.md`, constitution, F-04 approved spec/plan, current `README.md` if any, F-03 verification and code entrypoints; inspect `git branch`, HEAD, status, upstream before writes.
2. Expected local `main` matches remote `7baac22`, aside from preexisting modified governance files and untracked `.vscode/`.
3. Build the existing deterministic sources (if missing) with:
   ```sh
   .venv/bin/python -m scripts.build_catalog --data-dir data/raw --output data/generated/catalog.sqlite
   .venv/bin/python -m scripts.build_policy_index --input 'resources/políticas_da_loja.pdf' --output data/generated/policy_index.json
   ```
4. Never print provider keys. `.env` remains ignored and untouched.

## 4. Create README and authentic examples

1. README English title **Music Store AI Agent**. Cover: project goal, concise visual architecture text, all four tool names, CLI UX/pt-BR, read-only/static source semantics, model/backend selection, dependencies (Python 3.11+, pypdf), setup (`python -m venv .venv`, `.venv/bin/python -m pip install -e '.[dev]'`), two builder commands, `.env` private configuration, `.venv/bin/python -m app --debug-tools`, how to exit, pytest, limitations, project structure, use of ChatGPT/Codex, technical ownership. Avoid promotional recruiter branding.
2. Include an accurate portfolioworthy GitHub About text suggestion separately; no repository-setting mutation unless owner instructs.
3. Inspect ignored `data/generated/f03-router-live-smoke-final-bcd.json` and F-03 verification: use only actual *full* responses if they are available and provenance defensible. Do not quote example imagined outputs from a summary report as genuine transcripts. If missing, use real `python -m app --debug-tools` prompts against authorized free Nemotron, capture final assistant responses, tool names, model identity, redacting sensitive strings. Avoid logging whole provider request/headers.
4. Required genuine cases: available ukuleles; PIX policy with discount/non-stacking; combined catalog+PIX; out of scope (“Me ensine a programar?”). At most 4 fresh scenarios if prior trace insufficient and owner authorizes them. Optionally one follow-up only if headroom. Stop on 429 or 401/404 and mark absent examples as pending; never simulate.
5. Report what the model actually said; source/citation checks remain independently verified. Distinguish authentic response lines from explanatory editorial notes.

## 5. Clean-checkout reproduction

- First test `pip check`, `pytest -q` in current repo.
- With owner-approved temp directory, clone the *public* repository at approved F-03 baseline (F-04 is not yet committed), install into clean venv, build database/index, run all tests and `python -m app --help`; `--help` must work without key and no network. This proves the baseline. After PR merge, **repeat clean clone at F-04 final HEAD** (required for AC-02/AC-10), using the correct current repository URL `https://github.com/Sharpshooter171/music-store-ai-agent`.
- Any actual install failure: minimum corrective dependency/package fix, rerun tests; do not invent success. Do not make live LLM calls in clean clone; private `.env` stays in original machine.
- For local demo, private config must match approved OpenRouter endpoint and explicit free Nemotron; exact `model` availability cannot be guaranteed over time.

## 6. Safety and credibility checks

- Verify ignored `.env`, SQLite and JSON outputs; perform credential-pattern scan on newly staged deliverables, without printing actual secret values.
- Confirm no order/customer data tool exposed, no real customer records dumped; avoid hardcoding full sensitive data in examples.
- Verify CSV and PDF source hashes against F-01/F-02 verification, and ensure original source files unchanged.
- Inspect `git diff --check`, full scope, tool errors, model use disclaimers. Compare key numeric claims against catalog and policy; mark any unsupported wording or fix only with narrow test.
- Accurate AI assistance credit: spec/architecture and reviews assisted by ChatGPT; implementation/test work assisted by Codex; owner approved and reviewed. No statement claiming wholly manual coding.
- Keep the existing history, including the recruiting company mentions in earlier docs, unchanged; no advertising in new public headline or README. After the deadline a separately authorized clean portfolio fork is an option, not part of F-04.

## 7. Evidence and stop gates

- Run all tests, `pip check`, `git diff --check`, clean-clone checks, real example evidence and record exact outputs.
- Fill F-04 AC-01…AC-12 matrix PASS/FAIL/BLOCKED; document limitations and full original project URL.
- Stop for **human Gate V** review with changed-file inventory and evidence. **No commits, pushes, PR, merges, tagging, final application submission or email** under implementation-only authorization.
- After separately authorized PR/merge, re-run clean clone at final HEAD and explicitly ask owner to confirm exact recruiter delivery instructions and authorize submission. Deadline is based on user's current stated goal; confirm source instructions rather than assume a delivery channel.

## 8. Proposed commit boundaries after Gate V and separate Git authorization

1. `docs(f04): approve evaluation and delivery specification`
2. `docs(f04): document reproducible setup and architecture`
3. `test(f04): add authentic real-model examples and acceptance evidence`
4. Optional narrow `fix(f04)` with focused regression test only if necessary.

No fake history and no force pushes. Freeze repository after owner confirms submission.
