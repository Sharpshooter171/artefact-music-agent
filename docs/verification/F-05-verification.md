# F-05 — Latency and Provider Resilience Verification

**Date:** 2026-11-02 (BRT)\
**Observed branch / HEAD:** `feature/f05-latency-resilience` / `2c7a7e5` (baseline `main` merge of F-04 PR #4)\
**Authorization:** owner explicitly approved F-05 spec v1.0 (Gate S) and plan v1.0
(Gate P) **with mandatory amendments**, and authorized local implementation plus
offline tests only. No real LLM request, `.env` edit, default-model change, commit,
push, PR or merge was performed.

**Result:** local implementation and offline verification completed. **555 tests
pass** (448 pre-existing baseline tests plus 107 F-05 tests), including actual
process kill/reap, blocked DNS/connect/read, loopback stalled/dribbling responses,
SQLite lock-wait cancellation, sanitized diagnostics and the offline benchmark.
Real-model latency, quality and benchmark evidence is **NOT RUN** and is not
claimed. **Gate V recommendation: READY FOR OWNER REVIEW; Gate V has not been
self-approved.**

## Gate record

- Gate S = **APPROVED WITH AMENDMENTS** (owner decision, 2026-11-02).
- Gate P = **APPROVED WITH AMENDMENTS** (owner decision, 2026-11-02).
- Gate I = **AUTHORIZED FOR LOCAL IMPLEMENTATION** and offline tests only.
- Gate V = **PENDING OWNER REVIEW**.
- Gate D = **PENDING**; F-04 history and delivery status were not modified.

The approved spec and plan were amended before code changes to record the three
mandatory amendments: true hard request/turn deadlines, a **12 HTTP request
TOTAL** live cap, and separate quality/privacy metrics plus free-provider
retention limitations.

## Preflight and preservation

- Baseline verified at `main` / `2c7a7e57cb9eba566df9a75705eb2ed667e9fa5c`.
- A detached baseline worktree at that commit ran **448 passed** before F-05
  verification, preserving the pre-existing suite count.
- `.env` was not edited or read into the verification artifacts.
- `.vscode/`, pre-existing `AGENTS.md` and `docs/PROJECT_CONSTITUTION.md` edits,
  supplied CSVs, PDF, generated artifacts, F-01/F-02 public contracts and
  F-03/F-04 historical records were left unchanged.
- No runtime dependency was added; `pyproject.toml` is unchanged.
- No commit, push, PR, merge or delivery action occurred.

## Files changed or added

Modified application/configuration/documentation:

- `app/agent/config.py` — bounded request/turn deadlines, `max_tokens`, default-off
  same-model provider failover.
- `app/agent/llm_client.py` — supervised isolated HTTP worker, hard request
  deadline, kill/reap, bounded IPC, sanitized observation metadata.
- `app/agent/orchestrator.py` — turn deadline, main-thread alarm guard, killable
  tool path, request/turn/tool diagnostics, final-JSON compliance marker.
- `app/agent/prompt.py` and `app/agent/tool_registry.py` — semantic tool-selection
  guidance only; no keyword router or schema-contract change.
- `app/agent/cli.py` — bounded sanitized `--debug-tools` rendering.
- `.env.example`, `README.md` — settings, benchmark, candidate and retention
  limitations.
- `docs/specs/F-05-latency-resilience.md`,
  `docs/plans/F-05-implementation-plan.md` — approval metadata and amendments.
- `tests/test_agent_client.py`, `tests/test_agent_orchestrator.py`,
  `tests/test_agent_cli.py` — additive F-05 tests only; no removed assertions.

Added:

- `app/agent/deadline.py` — monotonic deadline arithmetic with injectable clock.
- `app/agent/http_worker.py` — one-request temporary HTTP worker with default TLS
  verification, redirect refusal, bounded request/response and sanitized errors.
- `app/agent/tool_worker.py` — one-call read-only tool worker with bounded IPC and
  no inherited provider credentials.
- `app/agent/worker_process.py` — shared signal-safe spawn masking, bounded pipe
  supervision and kill/reap helpers.
- `scripts/f05_benchmark.py` — offline-default synthetic benchmark with separate
  metrics, 12-request live cap and stop conditions.
- `tests/test_agent_deadline.py`, `tests/test_agent_hard_deadline.py`,
  `tests/test_agent_worker_io.py`, `tests/test_agent_tool_deadline.py`,
  `tests/test_f05_benchmark.py` — F-05 deterministic and process-level tests.
- This verification record.

## Hard-deadline evidence

The implementation does not treat monotonic checks between blocking urllib calls as
a hard deadline. Production model requests run in a short-lived isolated Python
subprocess (`python -I app/agent/http_worker.py`). The caller supervises a bounded
stdin/stdout pipe against one absolute monotonic deadline, then kills and reaps the
worker on every exit path. The same pattern protects real tool dispatch, including
SQLite/C-extension waits that a Python signal cannot interrupt.

Observed offline evidence:

- `tests/test_agent_hard_deadline.py` — real blocked worker is killed/reaped,
  cannot write its post-sleep marker, IPC stdout is bounded, argv/environment do not
  contain the key, and an alarm delivered during process creation does not abandon
  the child.
- `tests/test_agent_worker_io.py` — actual blocked DNS and connect hooks inside the
  worker are terminated; loopback stalled and dribbling response reads are
  cancelled with HTTP status preserved and socket closed; redirect is refused
  without a second request; oversized bodies are rejected; TLS verification flags
  are enabled and exception text cannot echo the key.
- `tests/test_agent_tool_deadline.py` — isolated catalog/policy results match the
  unchanged direct contracts; an actual SQLite `BEGIN EXCLUSIVE` lock wait is
  cancelled within the remaining budget; blocked and output-flooding tool workers
  are killed/reaped and do not inherit provider keys.
- Focused command: `.venv/bin/python -m pytest -q tests/test_agent_tool_deadline.py tests/test_agent_hard_deadline.py tests/test_agent_worker_io.py`
  observed **21 passed in 5.04s**.

A fake clock is used only for deterministic budget arithmetic; cancellation
evidence comes from real processes, real pipes, actual loopback sockets and a real
SQLite lock.

## Offline test results

Baseline (detached worktree at `2c7a7e5`):

```text
448 passed in 7.70s
```

Current branch:

```text
555 passed in 13.01s
```

Other checks:

```text
.venv/bin/python -m pip check
No broken requirements found.

git diff --check
(no output; clean)

.venv/bin/python -m app --help
exit 0

.venv/bin/python -m compileall -q app scripts
exit 0

555 tests collected
```

A scripts-only scan of all 27 changed/untracked files found **0 trailing-whitespace
findings**. No code was changed after this final full-suite run.

The 107 F-05 tests are additive. The existing 448 tests were not weakened,
removed or rewritten.

## Benchmark readiness

Offline command:

```bash
.venv/bin/python -m scripts.f05_benchmark
```

Observed summary (synthetic scripted fixtures, **not real latency or quality**):

```json
{
  "mode": "offline_scripted",
  "live_http_requests": 0,
  "scripted_requests": 15,
  "http_request_cap": 12,
  "metrics": {
    "end_to_end_ms": {"p50": 0.498, "p95": 1.519, "count": 8},
    "http_completion_reliability": {"passed": 15, "evaluated": 15, "rate": 1.0},
    "correct_tool_choice": {"passed": 8, "evaluated": 8, "rate": 1.0},
    "grounded_answer_success": {"passed": 7, "evaluated": 7, "rate": 1.0},
    "safe_fallback_behavior": {"passed": 0, "evaluated": 0, "rate": null},
    "final_json_compliance": {"passed": 8, "evaluated": 8, "rate": 1.0}
  }
}
```

Metrics are reported separately: end-to-end time, HTTP completion reliability,
correct tool choice, grounded answer success, safe fallback behavior and final JSON
compliance. P50/P95 include failed requests. A healthy HTTP response can still be
ungrounded or invalid JSON. The full eight-turn scripted set needs 15 requests, so
a future live run under the 12-request cap can end with partial coverage.

Real mode requires `--real --authorize-real`, separate owner authorization, the
configured approved model, provider failover OFF, no retries, no paid fallback and
the shared **12 HTTP requests TOTAL** cap. It stops on HTTP 429, authentication
errors or non-free routing/cost evidence. **Real mode was NOT executed.**

## Security review

- API key is sent to the HTTP worker through private stdin IPC only; it is never in
  command arguments, inherited worker environment, diagnostics, exception text,
  logs or verification artifacts.
- Worker stderr is discarded; provider error bodies/headers are not read for
  diagnostics. Diagnostics allow only HTTP status, validated free-model identity,
  bounded latency, sanitized error code and tool name/outcome.
- Request, response, IPC input/output and diagnostic sizes are bounded.
- HTTPS certificate/hostname verification and redirect refusal remain enforced.
- Tool worker inherits only artifact-path and harmless process environment values,
  never provider credentials; it remains read-only and uses the unchanged F-01/F-02
  functions.
- Prompt injection, grounding, evidence and F-03 security boundaries are unchanged.
- Secret-pattern scan over application, scripts, tests, docs, `.env.example` and
  README found no credential-like literals. `.env` remains untracked and untouched.
- No new dependency, external service, customer record or persistent background
  service was introduced.

## Owner-observed real Nemotron outcomes (2026-11-02)

These observations are owner-reported and are not raw provider transcripts. No raw
provider payloads, tool arguments, prompts or customer text were retained for
this review, so they are not reconstructed here. They are real-provider outcomes
only; they do not override the offline test evidence above.

Observed successes:

- Greeting: 9.39 seconds.
- Product search and price: 6.42 seconds.
- Policy retrieval and answer: 18.72 seconds.

Observed failures:

- Budget recommendation: `INVALID_ARGUMENT`.
- Category listing: `GROUNDING_FAILED`.

Classification:

- Offline verified behavior: all 633 tests pass, including request/turn deadline
  cancellation, sanitized diagnostics, tool-path integration and benchmark
  protocol checks.
- Observed real-provider outcomes: three scenarios completed with Nemotron; two
  scenarios failed with the codes above.
- Unmeasured claims: no comparative latency improvement, no before/after F-05
  live completion improvement, no candidate-model quality and no claim that all
  real scenarios passed.
- Known limitations: budget recommendations can fail when the model emits invalid
  tool arguments; category-listing answers can fail the host grounding guard.
  These remain documented and are not fixed by speculative runtime changes in
  this release candidate.

## Known limitations and unverified claims

- **No real-model evidence.** Latency, tool-selection accuracy, grounded completion,
  final JSON compliance, 429 behavior and customer-service improvement remain
  unmeasured against a live provider. Mock/loopback success does not prove them.
- A strict deadline can increase safe fallbacks for slow models; the 20 s request /
  45 s turn defaults require live evidence before tuning.
- The POSIX main-thread turn alarm fails closed on unsupported contexts; the HTTP
  request path remains hard-bounded by its worker, but arbitrary non-main-thread
  tool execution is not claimed as supported.
- Signal masking during spawn is POSIX-specific; the project runtime is Linux.
- Free providers may retain/log inputs and outputs for provider improvement. Zero
  price does not imply zero retention or training exclusion; terms must be checked
  before any separately authorized run.
- Candidate models remain documentation-only and non-allowlisted runtime defaults.
- Process creation, OS scheduling and cleanup add a small tolerance to observed
  wall-clock duration.
- F-04 Gate D remains pending; F-05 does not claim delivery completion.

## Acceptance mapping

| AC | Offline evidence |
| --- | --- |
| AC-01 | `test_agent_hard_deadline.py`, `test_agent_worker_io.py` actual kill/reap, blocked DNS/connect/read, loopback stalled/dribbling, bounded IPC |
| AC-02 | `test_agent_orchestrator.py`, `test_agent_tool_deadline.py` turn expiry, no second request, real tool cancellation, alarm preservation |
| AC-03 | `test_agent_cli.py`, client/orchestrator sanitization tests, bounded metadata |
| AC-04 | `test_agent_client.py` failover OFF/ON payload, exact model, zero price, response identity/cost checks |
| AC-05 | Spec/README candidate documentation only; no candidate selected or allowlisted |
| AC-06 | Prompt/schema guidance tests; no host keyword router |
| AC-07 | `test_f05_benchmark.py`, offline report with separate metrics, refusal without authorization, 12-request cap, stop conditions |
| AC-08 | Baseline **448 passed**; current **555 passed**; additive tests only |
| AC-09 | No contracts/governance/history modified; `.env`/data untouched; stdlib only; security review recorded |

## Gate V recommendation

The implementation is ready for owner review against the approved amended F-05
scope. Recommend **Gate V review**, not automatic approval. No commit should be
made until the owner explicitly authorizes it. A separately authorized live
evaluation is required before any claim of real latency or quality improvement,
candidate selection or default-model change.

## Gate V Delta — Benchmark Review Fix (2026-11-02)

**Result:** targeted offline checks pass; **Gate V remains PENDING OWNER REVIEW**.
The branch and HEAD remain `feature/f05-latency-resilience` / `2c7a7e5`.

### Behavior and review findings

- The working tree already contained shared argument validation and selectable
  scenario fixes when this review began. Initial benchmark verification observed
  **43 passed in 0.26s**. No approval or prior test result was inferred from that
  existing implementation.
- `SyntheticRegistry` reuses `parse_and_validate_arguments`, the production
  `ToolRegistry` contract. Expanded tests compare invalid-call error codes with
  production dispatch, cover valid arguments for all four tools, and verify that
  invalid calls produce no data evidence and stop the turn before a final reply.
  Valid envelopes remain labelled `meta.source = synthetic_fixture`; the catalog
  fixture's returned count now correctly reports its two products.
- Live mode defaults to six named scenarios with **11 scripted request estimates**:
  budget, policy, combined, out-of-scope and the two follow-up turns. Explicit
  `--scenarios` selections execute in canonical order. A details follow-up now
  requires its preceding catalog turn; incomplete/reversed follow-up cases fail
  before configuration loading or client creation.
- The shared **12 HTTP requests TOTAL** hard cap is unchanged. Tests exercise the
  real `ChatClient` with an injected, network-free HTTP opener and count transport
  invocations at caps 1 and 12, including a failed 503 request. Another test makes
  the bounded subset require extra model requests and confirms it still stops at
  12, independent of its 11-request estimate. No actual provider was contacted.
- Reports list selected and skipped scenarios with reasons. A turn interrupted
  by the cap is marked `execution_status: interrupted`; selected but unstarted
  scenarios carry `HTTP_REQUEST_CAP`, while omitted scenarios carry `not_selected`.
- Every benchmark pytest test now has an autouse guard that blocks environment
  configuration loading, production client construction, DNS/socket connections
  and subprocess creation. Explicit injected transports remain available for
  offline client integration tests. The full suite retains existing loopback-only
  deadline tests; no external network or real LLM request was made.

### Files changed in this review

- `scripts/f05_benchmark.py` — follow-up prerequisite check before configuration
  loading; corrected synthetic catalog metadata.
- `tests/test_f05_benchmark.py` — validation parity, valid/invalid evidence,
  injected HTTP cap checks, extra-request cap checks, scenario/CLI reporting,
  follow-up prerequisites and per-test network guards.
- `README.md` — interrupted status, prerequisite selection and request-estimate
  limitations.
- `docs/verification/F-05-verification.md` — this delta.

All other existing working-tree edits were preserved. SHA-256 comparison of 98
other project files found no changes during this review, including application
code, deadline implementation, model configuration/allowlist, F-01/F-02 source,
governance, spec/plan, F-04 history, supplied data and dependency metadata. `.env`
was not edited. No commit, push, PR, merge or real-model run occurred.

### Actual verification

```text
RED: benchmark tests after adding regressions, before implementation
3 failed, 63 passed in 0.44s
(missing follow-up prerequisite refusals and incorrect fixture count)

.venv/bin/python -m pytest -q tests/test_f05_benchmark.py tests/test_agent_tools.py
112 passed in 1.05s

.venv/bin/python -m pytest -q
603 passed in 19.55s

.venv/bin/python -m pip check
No broken requirements found.

git diff --check
(no output; clean)
```

Offline CLI execution of `--list-scenarios` reported all eight scenarios (15
scripted requests) and the six-scenario bounded default. Executing
`--scenarios policy,budget` reported canonical selection `[budget, policy]`, four
scripted requests, zero live requests and all six omitted scenarios with reasons.
Independent read-only review found no blocking findings. These checks support
AC-07/08/09; other F-05 evidence above remains historical and unchanged.

### Remaining limitations and live readiness

- Real latency, tool selection, final JSON quality and customer experience remain
  **NOT RUN**. Fixed fixtures test the argument/protocol contract; they do not run
  CSV/PDF retrieval or prove arbitrary semantic correctness.
- Live behavior can consume more requests than the scripted estimate and finish
  with partial coverage. The cap reserves a slot before each client invocation,
  including failures; pre-transport rejection can conservatively consume a slot.
- The cap is per invocation. A separately authorized evaluation must stay within
  **12 total across all scenarios/models**, without restarting to reset the budget.
- The benchmark is ready for a **separately authorized bounded live test** after
  the owner reviews this delta and verifies model identity, free routing and
  provider terms. The current default/allowlist and disabled provider failover
  remain unchanged. No candidate selection or model change is justified by these
  offline results.
