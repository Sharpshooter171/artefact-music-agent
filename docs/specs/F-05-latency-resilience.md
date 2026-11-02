# F-05 — Latency, Provider Resilience & Tool Selection

**Version:** 1.0 — approved with mandatory amendments
**Status:** APPROVED WITH AMENDMENTS — Gate S, owner decision 2026-11-02
**Prepared:** 2026-11-02
**Baseline:** `main` merge `2c7a7e57cb9eba566df9a75705eb2ed667e9fa5c` (F-04 PR #4)
**Owner:** Project owner (architecture/spec); coding agent (local implementation)

## 1. Problem and objective

A production-like diagnostic exposed a latency and resilience failure:

```text
Customer: "Estou começando a tocar violão e tenho no máximo R$ 500.
           Quais modelos você me recomenda?"

Request 1: nvidia/nemotron-3-ultra-550b-a55b:free, HTTP 200, 106.01 s
Tool:      list_categories, local result OK

Request 2: HTTP 503, 0.78 s, PROVIDER_UNAVAILABLE

Total:     106.79 s
Response:  safe generic fallback
```

An independent local query with `search_products(category="Violões",
price_max_cents=50000, availability="available")` returned two suitable models:

- Tagima Memphis AC-39 — R$ 429,90
- Rozini RC-104 — R$ 459,90

The catalog is healthy. The failure is in the model/provider interaction:
latency was not bounded end to end, the first tool choice did not directly
answer the budget question, and a provider outage turned the turn into a generic
fallback.

F-05 must improve latency and reliability without weakening the evidence,
security and grounding guarantees established by F-01 through F-04.

## 2. Observed baseline from the existing implementation

- `Config.timeout` is a per-socket/transport timeout (1–30 seconds), not a total
  wall-clock budget for DNS, connection, request, response headers and body.
- `ChatClient.complete()` performs one HTTP request per invocation, maps HTTP
  429 to `PROVIDER_RATE_LIMIT` and 5xx/503 to `PROVIDER_UNAVAILABLE`, and does
  not retry automatically.
- `Orchestrator.reply()` allows at most four model requests and six tool calls
  per customer turn, with bounded history and tool-output size.
- The prompt tells the model to use the four read-only tools, but the observed
  model selected `list_categories` instead of a direct budget-constrained
  `search_products` call.
- The current explicit production model is
  `nvidia/nemotron-3-ultra-550b-a55b:free`. The `openrouter/free` router alias is
  also approved. Both are free and remain subject to strict response-model and
  zero-cost checks.
- Offline baseline: 448 pytest tests pass. No real model call is part of this
  planning round.

## 3. In scope

1. A genuine end-to-end deadline for each model request.
2. A bounded total wall-clock budget for each customer turn.
3. Sanitized diagnostics for HTTP status, latency, returned model, request count
   and tool metadata, without logging keys, headers, bodies, prompts or customer
   text.
4. Evaluation of same-model provider failover, keeping the requested free model,
   zero price caps, strict response identity and no paid route.
5. Documentation-level verification of two smaller free-model candidates and a
   bounded evaluation protocol. Candidate allowlisting and selection require
   explicit owner approval after execution data exists.
6. Prompt and tool-description improvements for semantic tool selection covering
   budgets, comparisons, availability, details and policies, without replacing
   model intent selection with a host keyword router.
7. A latency/reliability benchmark that reports tool selection accuracy, grounded
   completion and safe fallback as separate metrics.
8. Focused tests and preservation of all 448 existing tests.

## 4. Out of scope

- Paid inference, paid provider fallback or spending API credits.
- Automatic model-layer fallback to a different model without explicit owner
  approval and a verified free allowlist.
- Keyword- or regex-based host routing that overrides the LLM's intent choice.
- Changes to F-01/F-02 public tool signatures, schemas, data semantics or tests.
- New frameworks, vector databases, queues, persistent background services, caches,
  deployment infrastructure or non-standard dependencies.
- New customer/order data, promotions, payments or mutation tools.
- Rewriting F-03/F-04 history, governance files or committed evidence.
- Real provider calls during this local implementation/offline verification round.
- Commits, pushes, PRs, merges or delivery actions.

## 5. Definitions and resilience boundaries

**Provider-layer failover.** The request keeps the same model ID. OpenRouter may
route that model to another compatible provider (for example, another host of
`nvidia/nemotron-3-ultra-550b-a55b:free`). This is a routing decision, not a
different model. It remains subject to the same free-model ID, zero price caps,
`require_parameters`, response-model validation and nonzero-cost rejection.

**Model-layer fallback.** The application changes the requested model ID, for
example from Nemotron to Gemma or to another free candidate. F-05 evaluates
candidates but does **not** enable automatic cross-model fallback in the initial
implementation. A future model-layer fallback would require a separately
approved allowlist, explicit free identity checks and owner authorization.

**Free-only boundary.** No paid model, no paid fallback, no API-credit spending,
no `models` array that can select a different model, and no weakening of
`provider.max_price` or response cost checks.

## 6. Proposed configuration contract

These defaults are owner-approved with amendments. Existing `.env` values remain untouched.

| Setting | Proposed default | Bounds | Meaning |
| --- | --- | --- | --- |
| `EMPORIO_LLM_TIMEOUT` | 30 s | 1–30 s | Existing socket/transport operation cap, retained for compatibility |
| `EMPORIO_LLM_REQUEST_DEADLINE` | 20 s | 1–30 s | Absolute deadline for one model request, from before DNS/connect through the complete response body |
| `EMPORIO_LLM_TURN_DEADLINE` | 45 s | 5–120 s | Absolute deadline for one customer turn, including all model requests and local tool calls |
| `EMPORIO_LLM_MAX_TOKENS` | 768 | 128–2048 | Requested completion cap; must remain sufficient for bounded multi-product answers |
| `EMPORIO_LLM_PROVIDER_FAILOVER` | false | `true`/`false` | Enables same-model provider fallback only; never cross-model fallback |

Validation requirements:

- Request deadline must not exceed the turn deadline.
- Deadlines and token limits are finite numbers/integers; booleans and malformed
  values are rejected with sanitized configuration errors.
- Existing endpoint, API-key, authorized-model and zero-price validations remain.
- Configuration errors must not include secrets, URLs with credentials or values.

## 7. Diagnostics contract

The application may expose only sanitized operational metadata:

```text
turn: duration_ms, request_count, deadline_state, error_code
request: http_status, returned_model, latency_ms, error_code
tool: name, ok, error_code
```

It must never expose Authorization headers, API keys, HTTP bodies, raw provider
error text, prompts, customer text, local file paths or full tool payloads.
`--debug-tools` may render the sanitized metadata; normal mode remains unchanged.

## 8. Candidate model verification

Verified from public OpenRouter model documentation on 2026-11-02. This is
documentation evidence only; no inference was executed. IDs must be re-verified
immediately before any authorized evaluation.

| Model ID | Status | Documented context | Tool calling | Structured output | Notes |
| --- | --- | --- | --- | --- | --- |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | Current explicit model | 1M | Yes | No `response_format` | Current baseline; final JSON is text validated by the host |
| `nvidia/nemotron-3.5-lightning:free` | Candidate | 1M | Yes | No `response_format` | 30B total/3B active MoE; free endpoint may log use for provider improvement |
| `google/gemma-4-26b-a4b-it:free` | Candidate | 262K | Yes | `response_format` without JSON-schema enforcement | 25.2B total/3.8B active MoE; free endpoint |

Free-model limits apply per OpenRouter account: 20 requests/minute and normally
50 requests/day, rising to 1,000/day after sufficient lifetime credit purchase.
Failed attempts count toward the daily limit. Benchmarking must respect these
limits and stop on HTTP 429.

Candidate rules:

1. The two candidate IDs are not automatically authorized runtime models.
2. Adding a candidate to `AUTHORIZED_MODELS` requires an explicit owner decision
   and a focused configuration change.
3. No candidate becomes the default until execution evidence covers tool
   selection, final JSON compliance, latency and grounded completion.
4. A model that cannot reliably call tools or return the required final JSON
   envelope must be rejected, not patched with fabricated facts.

## 9. Tool-selection requirements

The LLM remains responsible for semantic intent and tool selection. F-05 may
improve prompt and schema wording, but must not add a host keyword router.

Required behavior to target:

- Budget/recommendation requests should prefer `search_products` with
  `price_max_cents`, optional exact category and availability, rather than
  starting with `list_categories`.
- Availability and price comparisons should use `search_products`.
- A product description/specification request after identification should use
  `get_product_details`.
- `list_categories` is for category discovery/inventory overview, not as a
  mandatory first step for every catalog question.
- Policy, payment, PIX, hours, shipping, returns and warranty questions should
  use `search_store_policies`.
- Mixed catalog/policy questions should call both domains when needed.
- The host must not replace the model's semantic choice with customer-keyword
  matching. Evidence and grounding checks remain host-controlled.

## 10. Acceptance criteria

- **AC-01 Deadline:** The client enforces a genuine end-to-end per-request
  deadline using monotonic time across DNS, connection, send, headers and body.
  Expiry raises a sanitized `REQUEST_DEADLINE_EXCEEDED` error, closes the
  transport and does not leave a background request running. Tested with a slow
  or dribbling local transport and actual blocked-operation cancellation/reaping;
  fake clocks alone are insufficient.
- **AC-02 Turn budget:** The orchestrator enforces a bounded total turn duration,
  checks the deadline before every model request and after tool execution, and
  never starts a new model request after expiry. The fallback is safe and
  evidence-free. Total observed duration remains within the configured bound plus
  a small scheduling tolerance, with no abandoned background network request.
  Real read-only tool dispatch is also killable in a temporary subprocess because
  Python signal delivery alone cannot bound C-extension blocking. A main-thread
  POSIX turn alarm covers remaining Python work; unsupported contexts fail closed.
- **AC-03 Diagnostics:** Sanitized diagnostics record HTTP status, request
  latency, returned model, request count, deadline outcome and tool name/outcome.
  They never expose keys, headers, HTTP bodies, prompts, customer text or raw
  provider errors. CLI debug output is bounded and sanitized.
- **AC-04 Provider failover:** Same-model provider failover is an explicit,
  default-off option. When enabled, the request keeps the exact requested model,
  sets same-model provider fallback, preserves zero price caps and strict response
  checks, and rejects paid, unqualified, mismatched or nonzero-cost responses.
  No cross-model `models` array or paid fallback is added.
- **AC-05 Candidate evaluation:** The two candidate IDs are documented and
  verified before use; they require explicit local allowlisting and a bounded
  evaluation. No candidate is selected as a winner without execution data for
  tool calling, final JSON compliance, latency, grounded replies and fallback.
- **AC-06 Semantic tool selection:** Prompt/schema changes improve selection for
  budgets, comparisons, availability, details and policies. Tests verify the
  approved guidance and protocol; real-model accuracy is measured separately.
  No host keyword router is introduced.
- **AC-07 Benchmark:** Latency, completion reliability, tool selection accuracy,
  grounded reply success, safe fallback and final JSON compliance are reported
  as separate metrics. End-to-end response time and HTTP completion reliability
  are measured separately. The initial live cap is 12 HTTP requests TOTAL.
  The benchmark is offline-testable, refuses unauthorized network use, records
  HTTP status/model/tool observations, and stops on HTTP 429, authentication errors or any non-free routing.
- **AC-08 Regression:** All 448 existing tests remain passing, with focused new
  tests for request/turn deadlines, HTTP 503, HTTP 429, model identity and tool
  selection. No test is weakened or removed to make F-05 pass.
- **AC-09 Scope and security:** No new infrastructure, paid inference, real
  customer data, frameworks, dependencies, F-01/F-02 contract changes or
  governance changes. Supplier data, generated artifacts and `.env` remain
  untouched.

## 11. Test strategy

- Offline `pytest` with fake clocks, fake transports and synthetic credentials.
- Unit tests for deadline arithmetic, configuration bounds and error sanitization.
- Client tests for total request deadlines, 503/429 mapping, no automatic retry,
  same-model provider-failover payloads, exact model identity and zero-cost checks.
- Orchestrator tests for total turn deadlines, no request after expiry, safe
  fallback and sanitized diagnostics.
- Prompt/schema tests for required budget/comparison/availability/policy guidance
  without keyword routing.
- Benchmark tests for separate metrics, deterministic aggregation, sanitization
  and network refusal by default.
- Real-model evaluation only after explicit execution authorization, with a
  bounded HTTP-request cap and stop-on-429 behavior.
- Full suite plus `pip check`, `git diff --check`, secret scan and source-integrity
  review before Gate V.

## 12. Failure behavior

- Request deadline: sanitized `REQUEST_DEADLINE_EXCEEDED`, safe pt-BR fallback,
  no partial model text accepted as evidence.
- Turn deadline: sanitized `TURN_DEADLINE_EXCEEDED`, safe fallback, no new request.
- HTTP 429: `PROVIDER_RATE_LIMIT`, rate-limit fallback, stop the benchmark.
- HTTP 503/5xx: `PROVIDER_UNAVAILABLE`, safe fallback, no fabricated answer.
- HTTP 401/403: `PROVIDER_AUTH`, setup-safe message, no key echo.
- Launched request after expiry, tool failure or missing evidence: fail closed as
  in F-03; never guess prices, stock, discounts or policy rules.

## 13. Security, privacy and source integrity

- No credential, HTTP body, header, prompt or customer data in diagnostics or
  verification artifacts.
- Provider and tool responses remain untrusted data; F-03 injection boundaries
  remain unchanged.
- No new external service, dataset or customer record is introduced.
- The supplied CSVs, PDF, `.env`, generated artifacts and governance files remain
  unchanged.
- Benchmarks use synthetic customer questions only, never real customer data.
- Free providers can retain/log submitted inputs and outputs for provider improvement;
  zero price does not imply zero retention or training exclusion. No retention
  guarantee is asserted. Recheck provider terms before any separately authorized run.

## 14. Assumptions, dependencies and risks

- The observed diagnostic is owner-supplied context; F-05 planning did not
  reproduce it and made no provider calls.
- Public model documentation can change. Candidate IDs and capabilities must be
  re-verified before execution and before allowlisting.
- Free inference is rate-limited and not guaranteed; provider failover may not
  help when the same model has only one available provider.
- A strict per-request deadline can increase safe fallbacks for slow models. The
  default must be tuned with execution evidence, not optimism.
- An isolated per-request subprocess supervised by the CLI process is a real
  transport change; redirect, TLS, auth-header and size-limit behavior must be
  regression-tested.
- Reducing `max_tokens` can truncate long multi-product answers; the benchmark
  must include the largest expected catalog answer.
- Prompt improvements can change model behavior; only bounded evaluation can
  establish tool-selection accuracy.
- F-04 Gate D is still pending. F-05 is an owner-requested engineering round and
  does not modify or claim completion of F-04.

## 15. Gate notes

- Gate S = **APPROVED WITH AMENDMENTS** (explicit owner decision, 2026-11-02).
- Gate P = **APPROVED WITH AMENDMENTS** (same decision).
- Gate I = **AUTHORIZED FOR LOCAL IMPLEMENTATION** and offline tests only.
- Real inference, candidate runtime defaults, commits, push, PR and merge remain unauthorized.

## 16. Mandatory owner amendments (part of v1.0)

1. Hard deadlines: monotonic checks between blocking urllib operations are insufficient.
   Use one short-lived isolated subprocess per HTTP inference request (or a demonstrably
   equivalent mechanism), supervised by the caller. Enforce a wall-clock deadline
   across DNS/connect/send/headers/read; kill and reap on timeout and on interruption.
   No abandoned background thread/request and no persistent service. Preserve HTTPS
   validation, redirect refusal and ChatClient public behavior. API keys must never
   appear in argv, logs, exceptions or diagnostics. Bound request/response and IPC
   sizes. Standard-library Python only. Test actual cancellation, including blocked
   DNS/connect/read, beyond fake-clock arithmetic. If this cannot be safe, stop.
2. Live benchmark: maximum **12 HTTP requests TOTAL**, including failures and all
   scenarios/models; no retries or paid fallback. Separate owner authorization is
   required. Stop on 429, auth errors or non-free routing. Candidate models remain
   unauthorized runtime defaults; do not edit `.env` or select a default model.
3. Quality/privacy: synthetic customer questions only; document free-provider
   retention limitations. Report end-to-end time, HTTP completion reliability,
   correct tool choice, grounded success, safe fallback and final JSON compliance
   separately. A 20-second timeout alone proves no customer-experience improvement.
   A candidate must demonstrate catalog search, policy lookup and function calling
   before selection; offline mocks cannot establish real quality or latency.
