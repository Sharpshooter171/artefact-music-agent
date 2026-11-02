# F-03 — Implementation Plan: Real LLM Orchestration & CLI

**Version:** 1.0 with owner-approved provider amendment (2026-11-02)
**Status:** APPROVED — Gate P passed by explicit owner authorization (2026-11-02)
**Prepared:** 2026-11-02
**Spec:** `docs/specs/F-03-llm-orchestration-cli.md` v1.0 plus approved provider amendment

## 1. Goal, baseline and prerequisites

Keep F-01/F-02 implementations and public contracts unchanged. Local
`main` is expected at merge `90af5a3` with existing user modifications to
`AGENTS.md` and `docs/PROJECT_CONSTITUTION.md` left untouched. The coding
agent must inspect its actual HEAD/status and stop if drift affects scope.
Developer-provided LLM key is **never** included in prompts, logs or commits.
Do not initiate external model calls without separate approval.

## 2. Minimal file-level plan

| File | Work |
| --- | --- |
| `app/agent/__init__.py` | package marker |
| `app/agent/config.py` | env validation, bounded settings, model endpoint, no secrets in error |
| `app/agent/prompt.py` | fixed pt-BR persona, evidence and injection rules |
| `app/agent/llm_client.py` | stdlib HTTPS Chat Completions client, timeout/error handling; injectable fake transport |
| `app/agent/tool_registry.py` | static four-tool JSON schemas and allowlisted validated dispatch |
| `app/agent/orchestrator.py` | bounded model/tool loop, protocol, history, grounding/failure behavior |
| `app/agent/cli.py` | terminal interface and exit; no API work on module import |
| `app/__main__.py` | `python -m app` entry point |
| `.env.example` | placeholders only and documented env keys |
| `tests/test_agent_client.py` | HTTP request shape, error and secret-sanitization tests |
| `tests/test_agent_tools.py` | allowlist/invalid args/failure and source dispatch tests |
| `tests/test_agent_orchestrator.py` | fake LLM traffic, call protocol, combined tools, grounding and bounds |
| `tests/test_agent_cli.py` | text loop, exit and startup failure, no live network |
| `docs/verification/F-03-verification.md` | **short evidence only**, after test execution |

Prefer fewer files if that reduces complexity while preserving testable
seams. Do not touch or regenerate F-01/F-02 docs or source.

## 3. Sequence

1. **Preflight:** read governance and approved documents, `git status`,
   inspect only relevant F-01/F-02 contracts; verify baseline and artifacts.
2. **RED:** create focused pytest tests with mock HTTP/model and tool registry
   before implementation. Record the actual RED failures.
3. **GREEN:** implement safe config, provider-agnostic Chat Completions transport,
   tool schema/dispatch, orchestrator, pt-BR prompt, CLI. No network in tests.
4. **REFACTOR:** preserve public contracts, prevent excessive layers.
5. **VERIFY OFFLINE:** entire pytest suite, F-01/F-02 regressions, boundary
   tests, policy conflict flow, test malformed and unavailable provider,
   syntax/import, `pip check`, `git diff --check`, no secrets.
6. **VERIFY LIVE (separately authorized):** build source artifacts using
   `python -m scripts.build_catalog --data-dir data/raw --output data/generated/catalog.sqlite`
   and `python -m scripts.build_policy_index --input resources/políticas_da_loja.pdf
   --output data/generated/policy_index.json`; configure a real API key
   privately, run exactly 4 scenarios (catalog/policy/mixed/out-of-scope), inspect actual
   called functions and source correctness. Do not invent transcripts.
7. **EVIDENCE/HANDOFF:** concise log of environment, commands, passed counts,
   live/model status and known gaps; stop for human Gate V and Git authorization.

## 4. Configuration contract

- `EMPORIO_LLM_API_KEY`: required only for live provider calls.
- `EMPORIO_LLM_MODEL`: `openrouter/free` default plus the explicitly authorized
  `nvidia/nemotron-3-ultra-550b-a55b:free` under section 12; reject all other
  paid/alternate request models. No secret.
- `EMPORIO_LLM_BASE_URL`: HTTPS `/v1` compatible endpoint; default to
  `https://openrouter.ai/api/v1`; form final path `/chat/completions` exactly once.
- Optional `EMPORIO_LLM_TIMEOUT` 1–30 seconds; default 30.
- CLI command: `.venv/bin/python -m app`.
- No automatic API calls in test collection, `--help`, or module imports.
- `.env.example` is committed without real key; users set process env vars
  or a local ignored `.env`. Never `printenv`/echo the key in verification.

## 5. Chat Completions implementation notes

Use format `tools=[{"type":"function","function":{"name":...,
"description":...,"parameters":...}}]`; parse provider
`choices[0].message.tool_calls` and `function.arguments` as JSON object.
Append assistant message preserving tool calls; append one result per call
with `role="tool", tool_call_id=<original id>`. Continue until final content.

Use `parallel_tool_calls=false` where supported to simplify protocol;
still handle multiple tool calls defensively. Do not use Responses-specific
function schema in the Chat Completions request. Do not assume provider
implements `strict` mode; validate arguments locally even if it does.
Do not send unsupported model-specific sampling options.

A local mock/fake model response is not evidence of real-provider success.
The model's text is never a source of store facts; returned tool data is.
Before factual reply, check that this turn received relevant successful
tool evidence. Flag policy conflicts. If tools failed, show fallback instead
of a confident fabricated answer. Tool errors go to provider as sanitized
envelopes; do not expose file paths, raw transport errors or secret values.

## 6. Failure/abuse cases

- Invalid/missing API key/model and wrong endpoint.
- HTTP 401, 429, 5xx, timeout and malformed/non-JSON completion.
- Unsupported tool name; extra/invalid keys; oversized/malformed JSON.
- Tool exception, unavailable SQLite/policy index, and empty retrieval.
- Model tool-call loop, repeated tool calls, invalid tool call IDs.
- Prompt injection in catalog/section text or user utterance.
- User asks to reveal customer data, mutate order or ignore evidence.
- Unsupported store facts from model without successful evidence.
- CLI blank lines, `/sair`, Ctrl+C and EOF.

## 7. Verification evidence and stop conditions

- Trace each spec AC-01…AC-15 to at least one unit/integration test.
- Total F-01+F-02 baseline: 265 passing tests prior to F-03.
- Record observed count for completed offline suite, not a target asserted
  as a fact; real-provider tests must be explicitly authorized.
- Fail-closed on missing policy/catalog artifacts. Do not rewrite or
  silently alter approved F-01/F-02 contracts to make integration pass.
- `git diff --check`; inspect untracked/new files; do not stage, commit,
  push, open PR or merge until explicit authorization.
- If external provider unconfigured or paid invocation not approved,
  finish offline code+tests and report `LIVE_SMOKE=BLOCKED` accurately.
- If a live model does not support function calls, document failure and
  request provider/model decision rather than fabricating success.

## 8. PR commit boundaries (when later approved)

1. Approved F-03 spec + plan, without touching governance.
2. Code/config + deterministic mock tests.
3. Verification evidence and (later) real-smoke transcripts.
F-04 will own final README, 3–5 authentic example dialogues, and delivery.

## 9. Owner-approved scope clarification (2026-11-02)

- AC-15 out-of-scope: test "Me ensine a programar?"
  and similar unrelated requests, including a
  follow-up and an attempted prompt injection.
- The assistant should explain its customer-service
  scope in pt-BR and redirect politely.
- No store tool calls for a purely unrelated question.
- Add this scenario to live model smoke tests.
- OpenRouter endpoint: https://openrouter.ai/api/v1
- Current request models: `openrouter/free` default or the explicitly authorized
  `nvidia/nemotron-3-ultra-550b-a55b:free` (section 12). The original Qwen
  selection remains historical.
- Load the existing local .env without printing keys.
- Never route or fall back to paid models.
- Treat rate limits or unavailable free inference
  as explicit failures, not successful tests.

## 10. Original human approval record

The owner explicitly approved implementation plan v1.0 and specification v1.0
including AC-15 on 2026-11-02, with the OpenRouter free-only amendment.
Implementation and four real smoke scenarios are authorized in this execution.
Only the exact approved free model and endpoint may be used; zero prompt and
completion price caps and disabled fallback enforce the free-only boundary.
The existing `.env` must remain untouched. Gates C/S/P are approved, I is
authorized, and V remains pending human review. No commit, push, PR or merge.

## 11. Approved integration-fix execution amendment (2026-11-02)

The owner's “F-03 — REAL OPENROUTER INTEGRATION FIX” explicitly authorizes
replacing the unavailable original Qwen request ID with `openrouter/free` and
re-running the four end-to-end smoke scenarios. This is an approved execution
amendment, not a new planning round. Preserve all spec acceptance criteria,
including AC-15. The earlier HTTP 404 attempts remain historical evidence.

1. Inspect existing source/configuration/evidence and preserve all local work.
   Read `.env` privately as data; never overwrite it or reveal the key. Do not
   edit `AGENTS.md`, the constitution or F-01/F-02 public contracts.
2. Update only the F-03 client/configuration, focused mocked tests and approved
   F-03 documentation as needed. Use TDD for actual integration corrections.
3. Pin outgoing `model` to `openrouter/free` and endpoint to
   `https://openrouter.ai/api/v1/chat/completions`. Preserve zero price caps,
   disabled provider fallback, bounded loops and sanitized error handling.
   The router can return a concrete free model ID different from its request
   ID; validate the free boundary and record the actual returned model.
4. Execute the four prompts: “Vocês têm ukuleles disponíveis?”, “Como funciona o
   desconto no PIX?”, “Tem ukulele e desconto pagando no PIX?” and “Me ensine a
   programar?”. Record actual HTTP/model/call/answer evidence. Check respectively
   catalog search, policy retrieval, both domains and a polite tool-free scope
   redirect. Correct demonstrated integration defects without weakening tests.
5. **Stop if the free model cannot execute the required tools.** No paid model,
   paid fallback or additional service is authorized. Record provider failures
   honestly instead of claiming success or inventing conversations.
6. Run the complete offline suite (current observed baseline: 432 passing),
   F-01/F-02 regressions, `pip check`, whitespace/diff and secret/integrity review.
   Update the F-03 verification evidence with actual results and limitations.
7. Stop for human Gate V review. Do not stage, commit, push, open PR or merge.

Router behavior follows the [official OpenRouter Free Models Router contract](https://openrouter.ai/docs/guides/routing/routers/free-router).


## 12. Approved Nemotron free-model execution amendment (2026-11-02)

The owner explicitly selected `nvidia/nemotron-3-ultra-550b-a55b:free` and
updated the private local `.env`. This is an approved execution amendment, not
a new planning round. It supersedes only the request-model exclusivity in
sections 4 and 11; all acceptance criteria and security boundaries remain.

1. Add an exact configuration allowlist containing `openrouter/free` and
   `nvidia/nemotron-3-ultra-550b-a55b:free`. Preserve exact endpoint checks,
   sanitized errors, key handling, timeout bounds and rejection of every other
   model, including other free IDs.
2. Preserve zero provider price caps and `allow_fallbacks=false`. Never add a
   paid fallback or automatic model substitution.
3. For an explicit Nemotron request, require the provider response model to
   equal that exact ID. Retain the existing concrete-free-model validation for
   the `openrouter/free` router alias.
4. Add focused offline tests for allowlist acceptance, exact request payload,
   exact response acceptance, mismatched-free-response rejection and unchanged
   paid/alternate rejection.
5. Run the complete offline suite, `pip check`, CLI startup without key exposure,
   hashes/diff checks and at most one authorized real catalog prompt:
   “Vocês têm ukuleles disponíveis?”. Stop immediately on HTTP 429.
6. Update F-03 verification with the root cause, changed files, test count,
   actual HTTP/model/tool evidence and remaining blockers. Leave `AGENTS.md`,
   the constitution, private `.env` and F-01/F-02 untouched. No commit, push,
   PR or merge.
