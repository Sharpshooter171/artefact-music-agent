# F-03 — Verification Evidence

**Date:** 2026-11-02 (BRT)
**Branch / HEAD:** `main` / `90af5a3db4eeec346fc4172b25431070a090e1bd`
**Authorization:** owner explicitly approved spec v1.0 including AC-15 and plan
v1.0 with the OpenRouter free-only amendment, followed by explicit approvals
of the `openrouter/free` integration fix and the exact Nemotron free-model
correction.
**Gates:** C/S/P approved; I implemented; **V READY FOR HUMAN REVIEW**. All four
authorized Nemotron live scenarios now have HTTP 200 evidence: catalog
(`search_products`), policy (`search_store_policies`), combined (both tools) and
out-of-scope (no store tool). Historical HTTP 404/429 evidence remains below.
AC-14 and live AC-15 are verified; Gate V still requires the human decision.

This report records execution evidence, not self-approval or successful delivery.

## Implementation and changed files

- `app/agent/{__init__,config,prompt,llm_client,tool_registry,orchestrator,cli}.py`:
  literal local configuration, standard-library HTTPS Chat Completions, four
  validated read-only tools, bounded context/tool loop, grounded replies and CLI.
- `app/__main__.py`: `python -m app` entry point.
- `.env.example`: placeholder credential and approved free endpoint/model only.
- `tests/test_agent_{client,tools,orchestrator,cli}.py`: mocked transport,
  protocol, abuse/failure, real local tool integration and CLI tests.
- F-03 spec/plan: record human S/P approval and free-only amendment.
- This verification report. No README/F-04, dependency or F-01/F-02 changes.

Protected pre-existing modifications to `AGENTS.md` and the constitution remain
byte-identical to preflight. `.vscode/settings.json` was already untracked and was
not edited. No commit, staging, push, PR, merge, publication or submission occurred.

## RED → GREEN → REFACTOR

Each new test module was exercised before its implementation existed; collection
failed with the corresponding missing `app.agent` module. Focused GREEN runs
followed. Independent review identified additional regressions before handoff:

- Eight failing cases reproduced unhashable tool names, an incorrect 429 code
  mapping, prices borrowing product IDs/policy numbers, and evidence-free model
  prose smuggling factual claims/tutorials. All were fixed and passed.
- Six failing cases reproduced corrupt successful tool envelopes causing crashes
  or being treated as evidence. Minimal source-envelope checks now reject them.
- Client tests separately reproduced and fixed secret echoes involving quotes
  and backslashes. No real credentials were used in test fixtures.

Intent selection remains the LLM's responsibility. For evidence-free intents,
the host renders a safe greeting, clarification or scope redirect from the model's
validated label; it never routes by customer keywords. Factual replies use model
composition with current-turn source checks, exact BRL value checks and retained
policy cautions. Contact/installment conflicts suppress definitive model prose.

## Offline verification

Environment: existing `.venv`, Python 3.14.4; no dependencies installed or changed.

```bash
.venv/bin/python -m pytest -q
```

**Final result: 448 passed in 7.87s; 0 failed; 0 skipped.** Breakdown: 265
existing F-01/F-02 tests, 71 client/config, 43 registry, 49 orchestrator and 20
CLI tests. The previous implementation baseline was 432 passing tests; the
approved integration fix added 13 cases and the Nemotron correction added three,
with no original test removed.

An earlier full execution through `pytest.main(['-q'])` installed a process audit
hook rejecting `socket.connect`, `socket.getaddrinfo` and `socket.sendto`.
**445 passed in 7.51s** with real network operations forbidden before the three
Nemotron-specific cases were added. The only child interpreter invoked by the
CLI tests runs `--help`, which performs no API work.

Separate unchanged F-01/F-02 regression command:

```bash
.venv/bin/python -m pytest -q \
  --ignore=tests/test_agent_client.py --ignore=tests/test_agent_tools.py \
  --ignore=tests/test_agent_orchestrator.py --ignore=tests/test_agent_cli.py
```

**265 passed in 5.56s.** No original tool interfaces or tests were modified.

```bash
.venv/bin/python -m pip check
git diff --check
.venv/bin/python -m app --help
printf 'sair\n' | .venv/bin/python -m app --debug-tools
```

Observed: no broken requirements; no tracked whitespace errors; help exit 0;
actual CLI startup and exit 0 using the local artifacts/config, with no model call.
New/untracked text files were also checked with
`git diff --no-index --check /dev/null <file>`; ordinary `git diff` omits them.

## Local source builds and integrity

```bash
.venv/bin/python -m scripts.build_catalog --data-dir data/raw --output data/generated/catalog.sqlite
.venv/bin/python -m scripts.build_policy_index --input 'resources/políticas_da_loja.pdf' --output data/generated/policy_index.json
```

Both exited 0: **9 categories / 65 products**, and **8 PDF pages / 28 sections**.
Catalog snapshot: `021b88c544c06dc7aaae190149e8dd07d61fa120bf0d701b8d41eb83f6826d05`.
PDF SHA-256: `b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7`.

Preflight/postflight SHA-256 comparison found no changes to the two governance
documents, existing `.env`, six original CSVs, original PDF or catalog/policy
Python modules. The generated database, index, local integrity manifest and
sanitized smoke JSON are ignored under `data/generated/`; `.env` is ignored and
untracked. An exact credential-match scan found no key in the new deliverables.
No source/customer records or raw provider error bodies were printed in errors.

## Historical live evidence — original Qwen request ID

Exactly four scenarios were attempted, one HTTP request each, no retries.
Endpoint: `https://openrouter.ai/api/v1/chat/completions`.
Requested model: **`qwen/qwen3.8-27b:free`** in every request.

| Actual user prompt | HTTP | Returned model | Tool calls observed | Outcome |
| --- | --- | --- | --- | --- |
| Vocês têm ukuleles disponíveis? | 404 | None returned | None | Safe fallback; catalog grounding not demonstrated |
| Como funciona o desconto no PIX? | 404 | None returned | None | Safe fallback; policy grounding not demonstrated |
| Tem ukulele e desconto pagando no PIX? | 404 | None returned | None | Safe fallback; mixed routing not demonstrated |
| Me ensine a programar? | 404 | None returned | None | Safe fallback; real scope recognition not demonstrated |

Client and orchestrator both recorded `PROVIDER_HTTP_ERROR` for all four.
The actual response was:

> Não consegui confirmar essa informação com segurança agora. Posso ajudar com
> outra consulta ou você pode confirmar com a equipe da loja.

No completion succeeded, no actual inference model identity was returned and no
tool was selected by a real model. These are failed live checks, not successful
conversations. Their sanitized observations are retained locally in ignored
`data/generated/f03-live-smoke.json`; no fictitious example files were created.
The original HTTP error bodies were deliberately not read; no more specific
cause for those initial 404s was asserted. That execution stopped after four
requests. The owner later reported that the Qwen ID was absent from the account
catalog and approved the router replacement; new execution evidence follows.

Every request pinned the approved `:free` model and included
`provider.allow_fallbacks=false`, `require_parameters=true` and zero
`max_price` caps for prompt/completion/request/image. There was no model switch,
paid route or successful inference. HTTP failures returned no cost metadata;
account billing was not independently inspected. Nonzero reported costs or an
unexpected returned model were rejected in that original pinned-model implementation.
The approved router-specific identity handling below supersedes exact equality. Redirects cannot forward authorization.
The existing `.env` was read as literal data, never sourced/executed/overwritten.
Routing fields follow the [official OpenRouter provider-routing contract](https://openrouter.ai/docs/guides/routing/provider-selection).

## Reauthorized `openrouter/free` integration fix

The owner reported a new key authenticating with HTTP 200 and a direct
`diagnostic_ping` call succeeding. Those are owner-reported diagnostics, not
end-to-end successes observed by this agent. The existing private `.env` was
loaded without revealing/overwriting its key; there were no process key overrides.

Implemented changes, with RED/GREEN tests:

- Outgoing requests now exclusively use `openrouter/free` at
  `https://openrouter.ai/api/v1/chat/completions`. Other request model IDs,
  including the old free Qwen ID, remain rejected.
- The response identifies the concrete model selected by the free router. The
  client accepts syntactically valid `provider/model:free` IDs (or the router
  alias), records the returned ID and continues rejecting paid/invalid IDs and
  nonzero reported costs. A synthetic credential reflected in model metadata
  is rejected before recording it. Client suite: **68 passed**.
- A replay of scenario A initially returned HTTP 404 again. One bounded
  diagnostic request of the same scenario safely read/redacted the error:
  `No endpoints found that can handle the requested parameters.` No headers,
  credential or unfiltered metadata were exposed.
- Removed the optional `parallel_tool_calls=false` field. The approved plan
  specified using it only where supported; with `require_parameters=true` it
  was unnecessarily constraining compatible endpoints. Required tools and
  `tool_choice=auto`, zero price caps, disabled fallback and host validation
  remain enforced. The next observed response changed from HTTP 404 to 429;
  successful inference has not been demonstrated.
- Fixed a separate demonstrated stock-guard false positive: a grounded price
  such as `R$ 599,90 em estoque` was mistaken for an exact unit count. The guard
  now distinguishes decimal cents from quantities while still rejecting
  `81 unidades em estoque`. Orchestrator suite: **49 passed**.

Three requests occurred in this reauthorized execution: initial A HTTP 404;
same-A sanitized diagnostic HTTP 404; corrected A HTTP 429. There were no
successful completions or automatic HTTP retries. After 429, the live run
stopped under the owner's condition to stop when free inference cannot execute
the required tools. No further requests, model switch or paid fallback followed.

| Required scenario | Latest actual HTTP | Returned model | Tool calls observed | Actual outcome |
| --- | --- | --- | --- | --- |
| A. Vocês têm ukuleles disponíveis? | 429 after the parameter correction | None returned | None | Failed; safe rate-limit fallback, no catalog facts asserted |
| B. Como funciona o desconto no PIX? | NOT RUN in this execution | Not observed | None observed | Stopped after A; not a successful policy check |
| C. Tem ukulele e desconto pagando no PIX? | NOT RUN in this execution | Not observed | None observed | Stopped after A; mixed routing not demonstrated |
| D. Me ensine a programar? | NOT RUN in this execution | Not observed | None observed | Stopped after A; real scope classification unverified |

The actual final A response was:

> O serviço de atendimento está temporariamente no limite de consultas. Tente
> novamente mais tarde ou confirme com a equipe da loja.

Both client and orchestrator recorded `PROVIDER_RATE_LIMIT`. HTTP errors did not
return an actual model identity or cost metadata. No claim of factual correctness
for a model-generated catalog/policy answer can be made: none was generated.
There was no successful or paid inference observed; the request model and
server price caps prohibit paid routing. Account billing was not inspected.

Actual local evidence is ignored under `data/generated/`:
`f03-router-live-smoke-round1.json`, `f03-router-diagnostic.json`,
`f03-router-live-smoke-round2.json`. The previous four failed scenarios remain
in `f03-live-smoke.json`. An ignored local runner captures only these known
smoke prompts, model/status/tool observations and their bounded source results;
it contains no credential. No fictitious conversation or example was created.

Free-router response handling follows the [official Free Models Router contract](https://openrouter.ai/docs/guides/routing/routers/free-router).
Parameter compatibility follows the [official provider-routing documentation](https://openrouter.ai/docs/guides/routing/provider-selection).

## Nemotron free-model correction (2026-11-02)

The owner explicitly selected `nvidia/nemotron-3-ultra-550b-a55b:free` and
updated only the private `.env`. Local startup previously failed because
`Config.__post_init__` required exact equality with `openrouter/free`; the
resulting `UNAUTHORIZED_MODEL` surfaced as the generic CLI configuration error.

Implemented correction:

- `app/agent/config.py`: exact allowlist now contains only `openrouter/free`
  and `nvidia/nemotron-3-ultra-550b-a55b:free`. Other free IDs, unqualified IDs
  and paid IDs remain rejected. Endpoint, API-key, timeout and sanitized-error
  validations are unchanged.
- `app/agent/llm_client.py`: request payload uses the configured exact model.
  Zero price caps and `allow_fallbacks=false` remain. The router alias keeps
  its existing concrete-free response behavior; an explicit Nemotron request
  now requires the response model to equal the requested ID. A different free
  model is rejected with `UNAUTHORIZED_RESPONSE_MODEL`, and paid identities
  remain rejected.
- `tests/test_agent_client.py`: added allowlist acceptance, exact request and
  response, and mismatched-free-response rejection tests. Client suite:
  **71 passed**.
- F-03 spec and plan section 12 record this owner-approved amendment.
- The private `.env` was not displayed, overwritten or added to Git. No
  `AGENTS.md`, constitution, F-01/F-02 or dependency changes were made.

Offline verification:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
```

**448 passed in 7.74s; 0 failed; 0 skipped.** No broken requirements. The
previous baseline was 445 passing tests; this correction adds three cases.

CLI startup was captured in a subprocess with input `sair` and compared against
the loaded key without printing it: exit `0`; no configuration-error message;
`api_key_exposed=false`. No model call occurs on startup or exit.

The one authorized real catalog prompt was executed once:

```text
Prompt: Vocês têm ukuleles disponíveis?
Requested model: nvidia/nemotron-3-ultra-550b-a55b:free
HTTP status: 200
Returned model: nvidia/nemotron-3-ultra-550b-a55b:free
Tool calls: search_products (ok)
Client/orchestrator error: none
```

The grounded answer listed 10 available ukulele models with BRL prices and
noted that availability reflects the local catalog snapshot. No credential was
included in the captured smoke data. No HTTP 429 occurred, so no stop condition
was triggered. No repeated real call was made.

## Final live acceptance — policy, combined, out-of-scope (2026-11-02)

After the catalog-only check, the remaining three authorized scenarios were sent
once each to the approved endpoint with `nvidia/nemotron-3-ultra-550b-a55b:free`.
There were no retries, model switches, paid routes, automatic fallbacks or code
changes. Actual ignored evidence is in
`data/generated/f03-router-live-smoke-final-bcd.json`; no credential was captured.

| Scenario | Prompt | HTTP | Returned model | Observed tools | Tool outcome | Expected behavior |
| --- | --- | --- | --- | --- | --- | --- |
| B. Policy | Como funciona o desconto no PIX? | 200, 200 | `nvidia/nemotron-3-ultra-550b-a55b:free` | `search_store_policies` | ok | PASS |
| C. Combined | Tem ukulele disponível e desconto pagando no PIX? | 200, 200 | `nvidia/nemotron-3-ultra-550b-a55b:free` | `search_products`, `search_store_policies` | both ok | PASS |
| D. Out of scope | Me ensine a programar? | 200 | `nvidia/nemotron-3-ultra-550b-a55b:free` | none | not applicable | PASS |

### B. Policy

`search_store_policies` was called with query `desconto PIX como funciona` and
limit 3. The returned PDF evidence covered section 3 (Formas de Pagamento, page
3), section 6.2 (Regras de Promoções, page 6) and section 6.1 (page 6). The answer
correctly stated the 5% PIX discount on the table price, its applicability to
in-person and online purchases, non-cumulation with promotional prices, and the
promotion caution. No discount rate or stacking rule was invented. Sanitized
final answer:

> O desconto no PIX é de **5% sobre o preço de tabela** para pagamentos à vista,
> válido tanto para compras presenciais quanto online (Manual, seção 3 – Formas
> de Pagamento, pág. 3). **Pontos importantes:** O desconto **não se acumula** com
> preços já promocionais (seção 6.2 – Regras de Promoções, pág. 6). Promoções estão
> sujeitas à disponibilidade de estoque e não geram direito a reserva de preço.
> *Atenção:* O manual é de junho de 2025; campanhas descritas não comprovam
> promoções ativas nem preços atuais (caution PROMOTION_NOT_LIVE). Este manual é de
> junho de 2025. Campanhas descritas não comprovam promoções ativas nem preços
> atuais; o desconto PIX não se acumula com preços promocionais.

### C. Combined

The model called both read-only tools in one turn: `search_products` with
`{"query":"ukulele"}` and `search_store_policies` with `{"query":"desconto PIX"}`;
both succeeded. The ten listed products and BRL prices match the local catalog
snapshot exactly, and the 5% non-cumulative PIX rule matches the PDF sections.
Sanitized final answer:

> Sim, temos ukuleles no catálogo e o pagamento via PIX dá 5% de desconto sobre o
> preço de tabela (não cumulativo com preços já promocionais). Ukuleles disponíveis
> no momento: Kalani KAL-300S Soprano Natural – R$ 179,90; Kala KA-15S Soprano
> Mogno – R$ 199,90; Kala KA-C Concert Mogno – R$ 349,90; Kalani KAL-700T Tenor
> Natural – R$ 359,00; Kala KA-T Tenor Mogno – R$ 449,90; Kalani KAL-500C Concert
> Elétrico Natural – R$ 479,00; Kala KA-B Barítono Mogno – R$ 599,00; Kala
> KA-SMHCE Concert Elétrico Mogno – R$ 899,00; Kala KA-SRT-CTG Tenor Elétrico
> Cedar – R$ 1.599,00; Ohana BK-35E Barítono Elétrico Natural – R$ 1.899,00. O
> desconto de 5% no PIX é aplicado no checkout sobre o preço de tabela. Se houver
> alguma promoção ativa no produto, o desconto do PIX não se acumula (conforme
> regras da loja). Quer mais detalhes sobre algum modelo ou ajuda para escolher?
> Este manual é de junho de 2025. Campanhas descritas não comprovam promoções
> ativas nem preços atuais; o desconto PIX não se acumula com preços promocionais.
> Fonte: seção 3, página(s) 3; seção 6.2, página(s) 6; seção 6.1, página(s) 6.
> Disponibilidade conforme o catálogo local, sujeito a confirmação pela equipe.

One minor unsupported wording: “aplicado no checkout” is not stated explicitly in
the supplied PDF. It does not alter the price, discount, availability or stacking
claims, all of which are source-backed.

### D. Out of scope

The model returned `kind="out_of_scope"` with no tool calls. The host rendered its
canonical pt-BR scope redirect instead of arbitrary model prose. The response
politely explains the store-service scope, does not teach programming, makes no
store-fact claims and exposes no internal prompt. Sanitized final answer:

> Meu atendimento é sobre o Empório da Música. Posso ajudar com instrumentos do
> catálogo ou políticas da loja. Qual é sua dúvida?

No HTTP 429, timeout or provider outage occurred during these three scenarios, so
no stop condition was triggered and no further real calls were needed.

## Acceptance trace

| AC | Executed evidence / status |
| --- | --- |
| 01 | CLI tests plus actual startup/help/exit; pt-BR, blanks, interrupts and persistent loop |
| 02 | Client request-shape/auth/model/timeout tests; historical HTTP 404/429 plus four authorized Nemotron scenarios with HTTP 200 |
| 03 | Mock catalog/detail/category tool protocol; registry dispatch to real local public tools; live catalog `search_products` HTTP 200 |
| 04 | Mock policy protocol and citations; real original-PDF local retrieval; live policy `search_store_policies` HTTP 200 |
| 05 | Mixed catalog/policy tool batch protocol and source checks; live combined turn called both tools |
| 06 | Exact allowlist, typed/ranged/extra-key/duplicate-JSON validation, malformed batch and injection checks |
| 07 | Safe provider/tool/empty/corrupt-result fallback; CLI missing/corrupt artifact checks |
| 08 | Contact/installment definitive-prose suppression; mandatory separate warranty/exchange caution |
| 09 | Current-turn/domain sources; unsupported facts, prices and exact-unit checks; public tools hide stock counts |
| 10 | Follow-up history and fresh-source checks; at most 12 retained complete chat messages |
| 11 | Four model requests, six tools, 12 KiB cumulative tool data, 4 KiB input, HTTP/response/token bounds |
| 12 | Literal dotenv, process precedence, no key repr/echo, safe errors/redirects and network-blocked suite |
| 13 | All 265 unchanged F-01/F-02 tests pass; protected module hashes unchanged |
| 14 | **PASS**: four authorized Nemotron scenarios with HTTP 200 — catalog (`search_products`), policy (`search_store_policies`), combined (both) and out-of-scope (no tool) |
| 15 | Mock variants, malicious redirection and multi-turn scope redirect without tools pass; live out-of-scope prompt returned a polite tool-free pt-BR scope redirect |

## Limitations and next action

- All four authorized Nemotron live scenarios completed with HTTP 200 and real
  tool traces. Historical HTTP 404/429 evidence remains for the earlier Qwen and
  router runs. Live combined evidence contains one minor unsupported wording
  (“aplicado no checkout”); all product prices, availability and discount/stacking
  claims are source-backed. Gate V is ready for human review but not self-approved;
  no paid model or fallback is authorized.
- Mock tests demonstrate protocol/host behavior, not a real model's intent
  accuracy. JSON final-envelope compliance is deliberately fail-closed.
- Source labels and numeric checks cannot prove arbitrary semantic truth or
  correct product/price pairing across several retrieved records. No claim of
  eliminating hallucinations or all prompt injection is made.
- Free model and endpoint are deliberately locked to the approved amendment.
  There is no paid fallback, autonomous customer action or persistent chat log.
- Final README, curated authentic examples and clean-checkout delivery remain
  F-04 scope. This report records the raw live acceptance runs, not polished
  example dialogues.

**NEXT: Gate V human review** of the complete four-scenario live evidence. No
commit, push, PR, merge or publication before explicit authorization.

**Human Gate V decision:** APPROVED on 2026-11-02, based on 448 offline PASS and four real Nemotron smoke scenarios. Known limitation: unsupported 'aplicado no checkout' wording in live scenario C; follow-up grounding hardening deferred to F-04.
