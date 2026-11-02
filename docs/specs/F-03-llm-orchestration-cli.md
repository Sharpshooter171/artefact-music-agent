# F-03 — Real LLM Orchestration & CLI

**Version:** 1.0 with owner-approved provider amendment (2026-11-02)
**Status:** APPROVED — Gate S passed by explicit owner authorization (2026-11-02)
**Prepared:** 2026-11-02
**Baseline:** F-01 merged `b7f782a`; F-02 merged `90af5a3`
**Owner:** Project owner (architecture/spec); coding agent (implementation only)

## 1. Objective and user story

Build an actual, interactive Brazilian-Portuguese customer-service chatbot for
Empório da Música. A real, configurable LLM chooses the appropriate *read-only*
F-01/F-02 tools, receives their verified results, and composes a grounded response.
The app runs locally in a terminal and is reproducible with mocked model traffic.

A user can ask about prices/availability, detailed specifications, category
inventory, business hours, PIX, installment rules, returns, defects and warranty,
including follow-up and combined catalog+policy requests.

## 2. Approved source boundaries carried forward

1. F-01 public functions (unchanged): `search_products(query=None, category=None,
   price_min_cents=None, price_max_cents=None, availability='available', limit=10)`,
   `get_product_details(product_id)`, `list_categories()`.
2. F-02 public function (unchanged):
   `search_store_policies(query: str, limit: int = 3)`.
3. CSV/SQLite snapshots establish catalog facts; PDF sections establish policy
   facts; tool results can be missing or contradictory.
4. The LLM is **not** permitted to execute shell commands, SQL, internet search,
   external actions, payments, customer/order lookups, or arbitrary tool names.
5. Generated database and index remain local and untracked. Never present these
   snapshots as live inventory or real-time fulfillment.
6. Policy warnings about inconsistent contact/installments are preserved. Never
   resolve conflicting numbers or terms by guessing; distinguish 30-day defect
   exchange procedures from 90-day statutory warranty.

## 3. Architecture and transport

- Python 3.11+ CLI (`python -m app`), persistent until `/sair`, `sair`, `exit`,
  or EOF. Customer conversation language: pt-BR.
- Real provider-configurable model through **OpenAI-compatible
  `/chat/completions`** HTTP tool-calling protocol. Provider settings via env:
  `EMPORIO_LLM_BASE_URL`, `EMPORIO_LLM_MODEL`, `EMPORIO_LLM_API_KEY`.
  Never hardcode or commit credentials. An example configuration is published
  separately; no external request is made by default on tests/import.
- Current owner-approved configuration: OpenRouter Chat Completions at
  `https://openrouter.ai/api/v1/chat/completions`, requesting only
  `openrouter/free`. The unavailable original Qwen selection is superseded by
  section 11. No paid model or paid fallback is authorized. No guarantee that
  every free model supports identical features or is continuously available.
- Minimal standard-library HTTP transport (`urllib.request`, `json`, `ssl`);
  no new runtime dependencies or framework needed.
- Non-streaming request/response; one chat session held in memory only. No
  persistence of prompts/customer messages; no credential logging.
- Fixed trusted system instructions and a static allowlist of exactly four
  function tools. The model chooses tool(s) but the host **validates arguments
  locally and dispatches only approved Python functions**.
- Protocol: send system + history + tools; append assistant `tool_calls` message
  then corresponding `role='tool'` messages with exactly matching `tool_call_id`;
  call model again until a final assistant message or a safety bound.
- Bounds: <=4 model requests/turn, <=6 tool invocations/turn, <=10 tool messages
  retained in a turn, <=12 KB cumulative serialized tool output/turn,
  <=12 past chat messages in model context, <=4 KB user input/turn,
  30-second HTTP timeout, controlled errors and no infinite loops.
  These are implementation limits, not promises of external API availability.

## 4. CLI contract

```
$ python -m app
Empório da Música — assistente virtual
Você: Tem ukuleles disponíveis?
Assistente: [answer grounded in F-01 tools]
Você: E desconto pagando no PIX?
Assistente: [answer grounded in F-02 policy sections]
Você: sair
```

- On startup, check configuration and existence/readability of both generated
  artifacts; if missing, show concrete local commands to build them.
  Do not delete/rewrite artifacts automatically.
- When no API key/model is configured, show a concise setup error, not fake a
  conversation. A mocked deterministic offline test remains possible.
- Blank input is ignored. Ctrl+C/EOF end gracefully. Exit does not call model.
- Plain text UI; optional `--debug-tools` may show *sanitized* tool names,
  error codes and section/product identifiers, never provider headers or keys.
- On provider outage, malformed response, unknown function, invalid arguments,
  tool failure, model refusing/looping, or budget exhaustion: return safe pt-BR
  fallback and offer human assistance. No raw exceptions, paths or secrets.
- A customer follow-up uses session context, but *current* store-specific factual
  answers must rely on successful relevant tool results. The system prompt alone
  cannot be treated as sufficient proof; suppress unsupported numerical or
  policy assertions. A fail-closed guard/fallback must run on tool failures.

## 5. Tool schemas and routing

Public tool names are EXACT:
- `search_products` — catalog name/category/price/availability constraints,
  integer **cents** and bounded limit.
- `get_product_details` — product_id integer.
- `list_categories` — no arguments.
- `search_store_policies` — query and bounded limit.

Model-provided JSON must be an object and conform to allowlisted parameter
names/types/ranges. Reject unknown tools and extra keys; reject booleans as
integers, malformed JSON, non-object or oversized arguments. Do not eval,
import by name from a model string, or execute model-generated SQL.

Tool result envelopes must be passed to the model without silent rewriting.
Catalog `price.amount_cents` is converted for display only (BRL), never as
floating-point business logic. Never expose `stock_quantity` or customer CSVs.
Prompt-injection strings in source text are untrusted data.

## 6. Response and grounding requirements

Persona: friendly, clear, helpful to musicians, not pushy; pt-BR.
Use tools for every store-specific price, stock, technical specification,
business rule, store hours, contact or warranty claim. For mixed requests,
call both catalog and policy tools. Cite a policy page/section naturally
where available. Do not invent shipping quotes, active campaigns,
discount stacking, exact stock, order tracking, customer status or
sales promises. When no relevant evidence exists, say what is unknown
and suggest contacting staff. Conflicts from the policy tool are surfaced
as uncertainty requiring confirmation.

If the model emits specific store facts without a successful tool result in
the current turn, suppress unsupported output and give a safe response or
retry under a constrained tool choice, respecting request limits. Design and
test this defense; do not claim arbitrary hallucinations are impossible.

## 7. Acceptance criteria

- **AC-01** CLI boots from project root and supports multi-turn pt-BR chat,
  graceful exit and blank-input handling.
- **AC-02** Real HTTP client sends valid Chat Completions `messages`, `tools`,
  auth header and model, with timeout; mocked offline in pytest.
- **AC-03** LLM selects catalog tool(s) for product search and detail requests;
  correct assistant/tool message protocol.
- **AC-04** LLM selects policy tool for hours, PIX, returns/warranty and
  receives grounded pages/sections.
- **AC-05** Mixed requests may call both F-01 and F-02 in a single user turn
  while respecting per-turn budgets.
- **AC-06** Exact whitelist of four tools; strict argument validation and
  negative cases: unknown tools, extra keys, malformed JSON, bool-for-int,
  and injected control text.
- **AC-07** Tool errors, missing artifacts and unavailable provider result in
  sanitized, honest pt-BR fallback; no fabricated answer.
- **AC-08** Contact/installment contradictions and warranty vs. exchange
  distinction are preserved in response behavior.
- **AC-09** No unstated numeric store facts without successful tool evidence,
  no exact stock count or exposure of customer/order data.
- **AC-10** Session context supports simple follow-ups without changing
  source authority; bounded in-memory history.
- **AC-11** Request/tool/token-size and loop bounds enforced; malformed provider
  output/HTTP/network errors handled safely.
- **AC-12** Secrets not logged/committed; offline tests make no network calls;
  `.env.example` is placeholders only.
- **AC-13** All F-01 and F-02 pytest tests remain passing; no existing public
  tool signature/schema regressions.
- **AC-14** One authorized real-provider smoke demonstrates catalog question,
  policy question, and combined query with observable tool traces. If no
  provider credentials/consent, explicitly mark real smoke BLOCKED; NEVER
  claim Gate V is complete from mocked tests alone.

- **AC-15** The agent recognizes unrelated requests
  (e.g. "Me ensine a programar?"), responds briefly
  and politely in pt-BR, explains its store-service
  scope and offers relevant assistance. No catalog
  or policy tool call is necessary for purely
  out-of-scope requests. Test normal variants,
  malicious redirection and multi-turn context.

## 8. Out of scope

GUI/web/WhatsApp, new catalog tables, promotions/orders, payments,
live inventory updates, RAG vector DB, LangChain/LangGraph, persistent chat
history, OAuth, and auto-created fake transcripts.

## 9. Gate and approval notes

The project owner explicitly approved specification v1.0, including AC-15,
and implementation plan v1.0 on 2026-11-02 in the implementation request.
Gate S and Gate P are passed. The original four real-provider smoke scenarios
failed HTTP 404; the owner explicitly reauthorized the four end-to-end scenarios
and correction of actual integration problems in the later integration-fix
request (section 11). Gate V remains pending human review.
Human approval of a feature does not by itself authorize paid API calls,
publishing, committing, pushing or merging.

**Current F-03 provider selection: OpenRouter** — default `openrouter/free`,
plus the explicitly owner-selected `nvidia/nemotron-3-ultra-550b-a55b:free`
authorized in section 12. No paid model or paid fallback. The original Qwen ID
below is historical.

## 10. Original free-only configuration amendment — superseded (2026-11-02)

The owner selected `https://openrouter.ai/api/v1` and
`qwen/qwen3.8-27b:free`, authorizing only free inference for the four
listed catalog/PIX/mixed/out-of-scope smoke scenarios. This supersedes the
initial candidate provider above. Requests pin the approved model, disable
provider fallback and apply zero prompt/completion price caps. No paid model,
paid credits, automatic model replacement, commit or publication is authorized.
Load the existing ignored `.env` as data without shell execution or overwriting
it. Never display or persist credentials. Provider failure is verification
evidence, not permission to change models or fabricate successful transcripts.

## 11. Owner-approved Free Models Router amendment (2026-11-02)

The owner explicitly approved replacing the unavailable
`qwen/qwen3.8-27b:free` request model with **`openrouter/free` exclusively** in
“F-03 — REAL OPENROUTER INTEGRATION FIX”. This amends provider selection only;
all AC-01 through AC-15 and the existing source/tool/security boundaries above
remain unchanged. The owner reported successful authentication and a direct
`diagnostic_ping` function call; these reports are context, not substitute
end-to-end evidence produced by this implementation.

- Exact request endpoint: `https://openrouter.ai/api/v1/chat/completions`.
- Read the owner's current private `.env` as literal configuration data without
  displaying, executing, overwriting or persisting its API key.
- Every request uses `model="openrouter/free"`; no paid model, paid fallback,
  alternate explicit model or API-credit spending is authorized. Keep zero
  provider price caps and disabled provider fallback.
- OpenRouter's router selects an available free model supporting requested
  capabilities, including tool calling. Its returned `model` identifies the
  actual selected model and may differ from `openrouter/free`; record it rather
  than mistaking that normal router behavior for a request-model mismatch.
  See the [official Free Models Router contract](https://openrouter.ai/docs/guides/routing/routers/free-router).
- Re-run the four authorized prompts: ukulele availability; PIX discount;
  combined ukulele and PIX; “Me ensine a programar?”. Observe respectively
  `search_products`, `search_store_policies`, both domains, and no unnecessary
  store tool for the unrelated request. Record HTTP status, actual model,
  observed calls, factual correctness and failures from actual execution.
- Correct actual integration failures without weakening tests or inventing
  evidence. **Stop if the free model cannot execute the required tools**;
  do not switch to a paid model or claim a successful smoke test.
- Preserve historical HTTP 404 evidence, pre-existing work and F-01/F-02
  contracts. Leave `AGENTS.md` and `PROJECT_CONSTITUTION.md` untouched. No commit,
  push, PR or merge; Gate V still requires human review.


## 12. Owner-approved Nemotron free-model amendment (2026-11-02)

The owner explicitly selected the free OpenRouter model
`nvidia/nemotron-3-ultra-550b-a55b:free` and updated only the private local
`.env`. This amendment changes request-model authorization only. All AC-01
through AC-15, the existing source/tool/security boundaries and F-01/F-02
contracts remain unchanged.

- Configuration accepts exactly two request models: the `openrouter/free`
  router alias and `nvidia/nemotron-3-ultra-550b-a55b:free`. Every other value,
  including other `:free` IDs, unqualified IDs and paid IDs, remains rejected
  with `UNAUTHORIZED_MODEL`.
- The default remains `openrouter/free`; an explicit `.env` selection is sent
  verbatim to the approved endpoint. Endpoint equality, API-key checks, the
  1–30 second timeout bound, zero price caps and disabled provider fallback
  remain enforced.
- Response identity remains fail-closed. After a router-alias request, a
  syntactically valid concrete `provider/model:free` response is accepted. After
  an explicit Nemotron request, the returned model must equal the requested
  model; another free model is rejected with `UNAUTHORIZED_RESPONSE_MODEL`.
  Paid, unqualified and malformed identities remain rejected.
- No automatic fallback to a paid model, no alternate model substitution and no
  API-credit spending are authorized. Rate limits or provider failures remain
  explicit failed checks.
- At most one real catalog prompt, “Vocês têm ukuleles disponíveis?”, may be
  attempted in this execution. Record HTTP status, actual model and observed
  tool calls. Stop immediately on HTTP 429 and do not switch models.
- Leave the private `.env`, `AGENTS.md`, `PROJECT_CONSTITUTION.md` and F-01/F-02
  contracts untouched. No commit, push, PR, merge or publication.
