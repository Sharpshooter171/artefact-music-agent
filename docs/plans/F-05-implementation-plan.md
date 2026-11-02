# F-05 — Implementation Plan

**Version:** 1.0 — approved with mandatory amendments
**Status:** APPROVED WITH AMENDMENTS — Gate P, owner decision 2026-11-02
**Prepared:** 2026-11-02
**Spec:** `docs/specs/F-05-latency-resilience.md` (APPROVED WITH AMENDMENTS; Gate S)
**Baseline:** `main` merge `2c7a7e57cb9eba566df9a75705eb2ed667e9fa5c` (F-04 PR #4)
**Scope:** latency deadlines, sanitized diagnostics, same-model provider failover
evaluation, free-model candidate evaluation protocol, semantic tool-selection
guidance, benchmark, tests and documentation.

## 1. Goal and constraints

Fix the observed 106.79-second turn and 503 fallback without weakening F-01–F-04
grounding, privacy or security. The smallest defensible change is:

1. Make per-request and per-turn time budgets real.
2. Keep failures safe and observable without leaking sensitive data.
3. Evaluate, but do not silently adopt, provider failover and smaller free models.
4. Improve tool selection through prompt/schema wording, not a host keyword router.
5. Prove the changes with offline tests and a separately authorized bounded
   real-model evaluation.

No paid inference, new frameworks, new datasets, F-01/F-02 contract changes or
governance changes. Gate S/P approval with mandatory amendments is recorded below.

## 2. Preflight and unchanged boundaries

Before coding, re-check:

- `git status`, current branch and HEAD against the approved baseline.
- `AGENTS.md`, `docs/PROJECT_CONSTITUTION.md` and this spec/plan.
- Existing 448-test baseline and current agent modules.
- That `.env` is untracked and untouched.
- That no real provider call, commit, push, PR or merge is authorized by this plan.

Unchanged:

- `app/catalog/*` and `app/policy/*` public functions and schemas.
- `data/raw/*`, `resources/*`, generated data and `.env`.
- F-03/F-04 specs, plans and verification records.
- `AGENTS.md`, `docs/PROJECT_CONSTITUTION.md`, `.vscode/`.
- No new runtime dependency; Python standard library only.

## 3. File-level changes

| File | Change | Reason |
| --- | --- | --- |
| `app/agent/config.py` | Add bounded `request_deadline`, `turn_deadline`, `max_tokens`, `provider_failover`; validate request <= turn; preserve all existing model/price checks | AC-01/02/04/05/09 |
| `app/agent/deadline.py` (new) | Small monotonic deadline helper with injectable clock; no I/O | AC-01/02/08 |
| `app/agent/http_worker.py` (new) | Temporary stdlib subprocess for one request; bounded stdin/stdout IPC, TLS and redirect refusal; sanitized failures | AC-01/08/09 |
| `app/agent/llm_client.py` | Supervise isolated request worker with hard deadline, kill/reap on expiry/interruption, bounded IPC/response, sanitized latency/status/model metadata, optional same-model provider failover; keep redirects, size limits, auth and zero-cost checks | AC-01/03/04/08 |
| `app/agent/orchestrator.py` | Turn deadline, deadline checks around model/tool calls, new sanitized error codes, request/turn diagnostics, no post-expiry request | AC-02/03/06/08 |
| `app/agent/prompt.py` | Prompt guidance for budgets, comparisons, availability, details, policies and when not to start with `list_categories` | AC-06 |
| `app/agent/tool_registry.py` | Tool descriptions and private deadline dispatch adapter; no parameter/schema or public-contract changes | AC-02/06/09 |
| `app/agent/tool_worker.py` (new) | Short-lived read-only tool dispatch process, bounded input/output, no inherited credentials; kill/reap within remaining turn budget, including C-extension blocking | AC-02/09 |
| `app/agent/worker_process.py` (new) | Shared stdlib bounded pipe supervision; signal-safe spawn/kill/reap ownership | AC-01/02/09 |
| `app/agent/cli.py` | Sanitized `--debug-tools` metadata rendering; accept new error codes; no body/key/customer-text output | AC-03/08 |
| `.env.example` | Document new optional settings with placeholders only | AC-09 |
| `README.md` | Document deadlines, failover flag, candidate status, benchmark and limitations after verification | AC-05/07/09 |
| `scripts/f05_benchmark.py` (new) | Offline-capable scenario runner and separate metrics report; real mode requires explicit authorization and stops on 429 | AC-07 |
| `tests/test_agent_deadline.py` (new) | Deterministic deadline helper tests | AC-01/02/08 |
| `tests/test_agent_client.py` | Extend for total request deadline, 503/429, failover payload, identity and cost checks | AC-01/03/04/08 |
| `tests/test_agent_hard_deadline.py`, `tests/test_agent_worker_io.py`, `tests/test_agent_tool_deadline.py` (new) | Actual cancellation, reaping, spawn interruption, loopback stalled/dribbling I/O, bounded IPC and real isolated read-only tool compatibility | AC-01/02/08/09 |
| `tests/test_agent_orchestrator.py` | Extend for turn deadline, no post-expiry request, safe diagnostics and prompt protocol | AC-02/03/06/08 |
| `tests/test_agent_cli.py` | Extend for sanitized debug output and new error codes | AC-03/08 |
| `tests/test_f05_benchmark.py` (new) | Metrics separation, sanitization and network refusal | AC-07/08 |
| `docs/verification/F-05-verification.md` (later) | Evidence, actual commands/results, failures and limitations | Gate V |

No changes to `pyproject.toml` are expected. If a new dependency appears necessary,
stop and request a separate decision; do not add it silently.

## 4. Implementation sequence — test first

### Step 0 — Confirm gates and baseline

- Re-read the approved spec and plan.
- Confirm Gate S and Gate P approvals are recorded.
- Run `pytest -q` and record the 448-test baseline.
- Confirm `/home/igor-caldas/artefact-music-agent` branch/HEAD and clean worktree.

### Step 1 — RED: deadline and configuration tests

Add failing tests for:

- Deadline remaining time, expiry and clock injection.
- Request and turn deadline bounds; request <= turn.
- Malformed boolean/integer settings rejected without echoing values.
- Existing model/price validations unchanged.
- `max_tokens` bounds.

Expected failure: new settings/helper do not exist yet.

### Step 2 — GREEN: config and deadline helper

- Implement `Deadline` with `monotonic` injection and no I/O.
- Add settings with the proposed defaults from the spec.
- Keep sanitized `ConfigError` messages.
- Refactor only if both new and existing config tests pass.

### Step 3 — RED: client transport tests

Add failing tests for:

- A server that connects and then dribbles bytes past the request deadline.
- DNS/connect/read time counted toward the same request budget.
- Expiry maps to `REQUEST_DEADLINE_EXCEEDED`, closes the transport and leaves no
  running background request.
- HTTP 503 maps to `PROVIDER_UNAVAILABLE`; HTTP 429 to `PROVIDER_RATE_LIMIT`;
  neither retries automatically.
- `max_tokens` sent as an integer and bounded.
- Provider failover disabled by default; enabled payload keeps the exact model,
  `allow_fallbacks=true`, zero price caps and `require_parameters=true`.
- Explicit model response identity remains exact; router alias requires a
  concrete free returned model.
- Nonzero cost, paid model, mismatched model and oversized body are rejected.

Expected failure: transport is still socket-timeout-only and has no diagnostics.

### Step 4 — GREEN: deadline-aware client transport

- Run each production HTTP request in a short-lived isolated subprocess.
- Supervise bounded IPC using the absolute remaining budget; kill and reap on
  timeout/interruption, including blocked DNS/connect/read. Never use argv for keys.
- Retain socket timeouts as an additional operation cap, not proof of hard deadline.
- Test actual worker termination and no abandoned requests, not only fake clocks.
- Preserve HTTPS verification, redirect refusal, auth header, body-size limit,
  JSON parsing and existing exception mapping.
- Add sanitized observation fields; do not store body/headers/prompt/key.
- Add provider-failover payload only behind the approved default-off flag.
- Run focused client tests, then the whole suite.

### Step 5 — RED: orchestrator deadline and diagnostics tests

Add failing tests for:

- A fake client that sleeps past the turn deadline on request 1; request 2 must
  never start.
- Expiry before a tool call and after a tool call.
- Safe pt-BR fallback on `REQUEST_DEADLINE_EXCEEDED` and
  `TURN_DEADLINE_EXCEEDED`.
- HTTP 503/429 propagation and safe fallback.
- Diagnostics contain only approved metadata and no synthetic customer text,
  prompt text, API key or raw body.
- Existing max-request/tool-call limits and grounding checks still apply.

Expected failure: no turn budget or diagnostics exist.

### Step 6 — GREEN: orchestrator budget and diagnostics

- Create one monotonic turn deadline at the start of `reply()`.
- Check before each model request, before/after each tool call, and before
  accepting a final answer.
- Pass remaining request budget to the client.
- Use a temporary isolated tool-dispatch subprocess for the real ToolRegistry,
  sharing bounded kill/reap supervision. This bounds SQLite/C-extension blocking
  that a Python signal alone cannot reliably interrupt. Preserve injected offline
  registry doubles and existing dispatch contracts. The synchronous POSIX main-thread
  turn alarm covers remaining Python work; unsupported contexts fail closed.
- Mask SIGALRM/SIGINT only during subprocess ownership establishment and cleanup,
  restoring the original mask before I/O; queued cancellation must reap the child.
- Add sanitized turn/request/tool observations; do not log message contents.
- Keep existing evidence validation and safe fallback behavior.
- Run focused orchestrator tests, then the whole suite.

### Step 7 — RED/GREEN: prompt and tool-selection guidance

RED: tests assert the prompt/description guidance covers:

- Budget recommendation: prefer `search_products` with `price_max_cents` and
  optional exact category/availability; do not start with `list_categories`.
- Availability and price comparison: `search_products`.
- Details/specifications: `get_product_details`.
- Category discovery: `list_categories` only when appropriate.
- Policy/payment/PIX/hours/shipping/returns/warranty: `search_store_policies`.
- Mixed questions: both domains.
- No host keyword routing or model-result rewriting.

GREEN: update prompt text and tool descriptions only. Keep parameter names,
types, enum values and public tool results unchanged. Run all F-01/F-02/F-03
tests to prove contracts are intact.

### Step 8 — RED/GREEN: benchmark harness

RED: tests for separate metrics:

- Tool selection accuracy.
- Grounded reply success.
- Safe fallback correctness.
- Latency P50/P95 (including failed/slow requests).
- HTTP completion reliability, separately from final JSON compliance.

Also test deterministic aggregation, sanitized output, and refusal to use the
network unless an explicit real-mode authorization flag is supplied. The default
mode must be offline/fixture-based.

GREEN: add `scripts/f05_benchmark.py` with:

- A small scenario set: budget recommendation, availability, comparison, policy,
  combined, out-of-scope, and follow-up.
- A hard HTTP-request cap and stop-on-429 behavior.
- Sanitized JSON output under an ignored generated path.
- No retries beyond the approved request budget.

### Step 9 — REFACTOR and documentation

- Remove duplicated deadline checks and keep one source of truth.
- Document new settings in `.env.example` and `README.md` only after behavior is
  proven, including free-only limits and fallback semantics.
- State that candidate models are not yet authorized runtime defaults.
- Do not modify F-03/F-04 historical records.

## 5. Tests to add

| Test file | Focused tests |
| --- | --- |
| `tests/test_agent_deadline.py` | `test_remaining_and_expiry`, `test_expired_budget`, `test_injected_clock` |
| `tests/test_agent_client.py` | `test_request_deadline_bounds_total_time`, `test_request_deadline_closes_socket`, `test_http_503_maps_to_provider_unavailable_without_retry`, `test_http_429_maps_to_rate_limit_without_retry`, `test_provider_failover_payload_is_same_model_and_zero_cost`, `test_provider_failover_off_by_default`, `test_explicit_model_identity_still_exact`, `test_router_alias_requires_concrete_free_model`, `test_max_tokens_bounded` |
| `tests/test_agent_orchestrator.py` | `test_turn_deadline_stops_second_request`, `test_turn_deadline_after_tool_call`, `test_request_deadline_maps_to_safe_fallback`, `test_diagnostics_are_sanitized`, `test_prompt_covers_budget_and_policy_selection`, `test_no_post_expiry_request` |
| `tests/test_agent_cli.py` | `test_debug_tools_prints_safe_latency_status_model`, `test_debug_tools_never_prints_body_key_or_customer_text`, `test_new_deadline_codes_render_safe_message` |
| `tests/test_f05_benchmark.py` | `test_metrics_are_separate`, `test_latency_includes_failures`, `test_report_is_sanitized`, `test_network_requires_explicit_authorization` |

Tests use synthetic credentials and fake transports/clocks plus actual short-lived
worker cancellation and loopback-only blocked/dribbling transport fixtures. No
external network/provider access in the default pytest run.

## 6. Bounded real-model evaluation protocol

This phase requires a separate explicit owner authorization for provider usage.
Planning assumes **no** such authorization.

1. Re-verify model IDs/capabilities and free limits immediately before execution.
2. Evaluate the current explicit model as baseline. Evaluate candidates only if
   the owner adds them to the local allowlist for the evaluation.
3. Use the same scenario set and prompts for each model.
4. Hard cap: 12 HTTP requests TOTAL, no automatic retries, stop immediately on
   HTTP 429, authentication errors, any non-free routing or a daily-limit response. Record partial results honestly.
5. Record only sanitized fields: model ID, HTTP status, latency, request count,
   selected tool names, tool success, final-envelope validity, grounded-completion
   score and safe-fallback score.
6. Do not record prompts, API keys, headers, raw bodies or customer text.
7. Report latency and task quality separately; do not declare a winner from one
   metric.
8. Candidate selection/default change is a separate owner decision after reviewing
   the evidence. No automatic model-layer fallback is enabled by the benchmark.

## 7. Rollback and compatibility

- No commits are authorized. Keep local file changes reviewable on a separate F-05
  branch; reverse only task-owned edits if rollback is needed. Preserve user changes.
- The new settings have safe defaults and no data migration.
- Existing `EMPORIO_LLM_TIMEOUT`, model allowlist and price checks remain valid.
- If the deadline is too aggressive for normal product answers, tune only with
  recorded evidence and owner approval; do not remove the bound.
- If provider failover causes identity/cost ambiguity, keep it disabled; safe
  fallback is preferable to unverified routing.
- If a candidate model fails tool calling or final JSON compliance, reject it;
  do not add a model-specific factual workaround.

## 8. Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Isolated worker transport breaks response parsing | High | Actual cancellation/reaping and loopback dribbling tests, preserve size/JSON checks, full regression suite |
| Deadline too low causes more safe fallbacks | Medium | Proposed 20 s/45 s defaults; tune with bounded evaluation |
| Provider failover routes unexpectedly | High | Same model ID only, zero price caps, exact response validation, default off |
| Candidate model ignores tools or text-JSON contract | High | Bounded evaluation before allowlisting; reject on evidence |
| Prompt changes alter other scenarios | Medium | Full prompt/tool tests; benchmark tool accuracy separately |
| Free limits exhausted during evaluation | Medium | Hard 12-request total cap; stop on 429; no retries |
| F-04 Gate D remains pending | Delivery risk | F-05 does not modify F-04; final submission requires separate approval |
| Secret/customer data in diagnostics | High | Allowlist metadata fields; sanitization tests; no raw bodies/prompts |

## 9. Verification and stop conditions

After implementation, run and record:

```bash
pytest -q
pip check
git diff --check
git status
```

Also:

- Map AC-01–AC-09 to test/evidence results.
- Run the offline benchmark tests and, only if authorized, the bounded real-model
  evaluation.
- Review the diff for secrets, raw data exposure, dependency changes and scope
  creep.
- Write `docs/verification/F-05-verification.md` with actual results, including
  failures, skipped checks and limitations.
- Stop before commit/push/PR/merge unless the owner explicitly authorizes it.

Stop and request a decision if:

- Gate S or Gate P approval is not recorded.
- A new dependency or framework appears necessary.
- A candidate requires paid inference or paid fallback.
- Deadline behavior cannot be tested deterministically.
- The implementation would change F-01/F-02 contracts or governance.
- Real provider usage or a model allowlist change is needed but unauthorized.

## 10. Owner approval and mandatory amendments

Explicit owner decision, 2026-11-02:

- Gate S = **APPROVED WITH AMENDMENTS**.
- Gate P = **APPROVED WITH AMENDMENTS**.
- Gate I = **AUTHORIZED FOR LOCAL IMPLEMENTATION** and offline tests.
- No real LLM requests, `.env` edits, default-model changes, commits, push, PR or merge.

The mandatory amendments in spec section 16 govern this plan: genuinely hard
per-request/turn deadlines with temporary worker kill/reap, standard-library only,
bounded secret-safe IPC; **12 HTTP requests TOTAL** in a separately authorized
live evaluation with no retries and stop on 429/auth/non-free routing; synthetic
questions only and explicit free-provider retention limitations.

Metrics must separate end-to-end response time, HTTP completion reliability,
correct tool choice, grounded success, safe fallback and final JSON compliance.
Timeout enforcement alone cannot establish improved real customer experience.
Candidates must demonstrate catalog searches, policies and function calling before
selection. No candidate/default/allowlist change is approved here.

Implementation stops after offline verification and records real-model evidence
as NOT RUN. F-03/F-04 history, F-01/F-02 contracts and governance stay untouched.
