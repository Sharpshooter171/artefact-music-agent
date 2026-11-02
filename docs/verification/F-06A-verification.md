# F-06A — Catalog Retrieval & Grounding Reliability Verification

**Date:** 2026-11-02 (BRT)\
**Branch / HEAD:** `main @ 6d83c45484d31284fc6653b72d5b77c07ed6a888`\
**Authorization:** explicit owner request approves F-06A v0.1 Gates S/P and local
implementation/offline verification. **Gate V: PENDING HUMAN REVIEW.**

Local implementation and offline verification are complete: **736 tests passed,
0 failed, 0 skipped**, including all 633 unchanged pre-existing tests and 103
additive F-06A regressions. No external LLM/provider request, paid inference,
provider/model change, commit, push, PR, merge or submission occurred.

## Preflight and approval provenance

Read `AGENTS.md`, the approved constitution, F-05 spec/plan and verification,
the tool-failure record, proposed F-06 roadmap and relevant contracts before
runtime edits. `docs/decisions/` was empty. F-06A spec/plan files were absent;
the new v0.1 documents record the supplied explicit owner authorization and
requirements, without pretending to reproduce unseen prior wording.

Actual baseline matched the owner-specified branch/HEAD. Initial `git status`
showed only pre-existing untracked `.vscode/`. The private `.env` and `.vscode/`
were not edited. Supplied CSVs/PDF, existing generated artifacts, governance,
dependencies, existing tests, F-01/F-02 schemas/SQL, provider configuration,
workers, deadlines and diagnostics contracts remain unchanged.

## Changes and confirmed behavior

| File | Result |
| --- | --- |
| `app/agent/orchestrator.py` | Integer-cent monetary boundaries; bounded current-turn budget provenance and exact product/price pairs; private validated search parameters; complete scoped minimum validation |
| `app/agent/prompt.py` | Semantic retrieval guidance for completeness, exact scope and budget/price separation; no host intent router |
| `tests/test_f06a_reliability.py` | 103 additive offline positive/adversarial regressions |
| `README.md` | Verified outcome and explicit local/model/language limitations |
| `docs/specs/F-06A-catalog-retrieval-grounding.md` | Supplied approved v0.1 requirements and authorization provenance |
| `docs/plans/F-06A-implementation-plan.md` | Supplied approved scope, minimal design, test sequence and rollback |
| This record | Actual verification evidence and remaining limitations |

**R-01:** The previous currency regex consumed a trailing comma and stripped
only periods. Supported amounts now accept ordinary trailing punctuation while
retaining exact cents and thousands validation. Fabricated amounts, one-cent
differences, malformed continuations, signs and arithmetic expressions fail.

**R-02:** Customer amounts never join the product-price whitelist. A budget
quote requires a complete affirmative declaration in the current customer
message and the exact standalone answer prefix `Seu orçamento é R$ AMOUNT.`.
Any following content must consist of full retrieved product names with their
own exact prices. This rejects explicit and implicit budget-to-price reuse,
including "the product costs that amount", wrong product-price pairs, stale
budgets, alternatives, retractions and recognized unsupported budget paraphrases.
Only selected current-turn catalog sources establish the following product pairs.

**R-03:** A minimum needs one complete current-turn search, preserved validated
parameters, an exact stated lexical-query/category scope, available products,
no price bounds, a nonempty snapshot identifier, `truncated is False`, a correct
integer returned count, unique IDs and a count within the requested limit.
Category records must agree with the category scope. The exact claimed name and
integer price must attain that search's minimum. Details-only, historical,
partial-union, malformed metadata, wrong availability/scope and wrong-winner
claims fail closed. Original tool envelopes are sent to the model unchanged.

## Actual test evidence

All commands used the existing local environment. Tests use scripted model
messages and synthetic data; production model methods and socket connections
are blocked in the new regression file. Existing deadline tests retain their
offline loopback/process coverage. No provider credentials are needed.

| Stage / command | Observed result |
| --- | --- |
| Baseline `.venv/bin/python -m pytest -q` before edits | **633 passed in 15.10s** |
| Initial RED `.venv/bin/python -m pytest -q tests/test_f06a_reliability.py` before runtime edits | **37 failed, 38 passed in 0.59s** |
| Initial GREEN, same targeted command | **75 passed in 0.53s** |
| Expanded monetary/provenance/comparison review RED, targeted `--tb=no` | **16 failed, 76 passed in 0.46s** |
| GREEN after those corrections | **92 passed in 0.42s** |
| Budget-anaphora/paraphrase review RED, targeted `--tb=no` | **4 failed, 95 passed in 0.43s** |
| Final `.venv/bin/python -m pytest -q tests/test_f06a_reliability.py` | **103 passed in 0.46s** |
| Final targeted file plus `tests/test_agent_orchestrator.py tests/test_agent_tool_diagnostics.py tests/test_agent_cli_tool_path.py` | **198 passed in 3.33s** |
| Final `.venv/bin/python -m pytest -q` | **736 passed in 15.64s** |
| `.venv/bin/python -m pip check` | **No broken requirements found** |
| `git diff --check` | **Clean; exit 0** |

Intermediate full runs observed 708 and 727 passing tests before additional
review regressions were added. A review test fixture initially reused shared
product dictionaries; copying the fixture products removed cross-test mutation
before the recorded expanded RED run. No pre-existing test was changed, removed
or weakened. No final test failed or skipped.

Independent read-only reviews reproduced defects and checked the corrections.
The comparison reviewer independently observed **94 passed in 0.46s** before the
last budget regressions. The final monetary reviewer observed **61 passed,
42 deselected**, and re-executed final validation for the previously
reported budget, pairing, retraction and signed-price blockers; all were rejected.
The deselection was an intentional `-k 'ac01 or ac02 or ac03'` subset, not skipped
coverage in the final full suite. Neither reviewer made provider calls.

## Actual local catalog/worker verification

A separate offline Python invocation used a scripted model with the **default
production `ToolRegistry`**, including its isolated read-only tool worker. It
read existing local artifacts; no catalog rebuild or generated-data edit was
performed. Direct local search metadata and the complete orchestrated outcomes
were observed together:

| Search parameters | Returned / truncated | Minimum | Tool envelope bytes | Final guard |
| --- | --- | --- | --- | --- |
| `query="violão"` | 10 / true | Rozini RC-104 Nylon Estudante, 45990 cents | 2076 | Unqualified minimum rejected, `GROUNDING_FAILED` |
| `query="violão", limit=50` | 33 / false | Tagima Memphis AC-39 Nylon Natural, 42990 cents | 6481 | Exact query-scoped minimum accepted |
| `category="Violões", limit=50` | 33 / false | Same Tagima, 42990 cents | 6493 | Exact category-scoped minimum accepted |

Every worker trace recorded successful `search_products`. Both complete results
fit the unchanged 12 KiB per-turn tool-output budget. Accepted full-answer forms:

```text
Na busca por "violão", o menor preço disponível é Tagima Memphis AC-39 Nylon Natural por R$ 429,90.
Na categoria Violões, o menor preço disponível é Tagima Memphis AC-39 Nylon Natural por R$ 429,90.
```

These are scripted local verification outcomes, not authentic provider dialogue
or evidence of the LLM choosing the right query. No example transcript was
created or rewritten.

## AC-01–AC-09 evidence mapping

| AC | Offline evidence / outcome |
| --- | --- |
| AC-01 | Supported punctuation, grouped/ungrouped thousands and one-cent amounts pass using integer cents |
| AC-02 | Fabricated/malformed/signed/arithmetic prices and wrong exact cents fail; original fabricated-price tests stay green |
| AC-03 | Exact verified current-turn budget plus explicit catalog product/price pairs pass; blanket, stale, ambiguous, invented and anaphoric reuse fail |
| AC-04 | Complete matching query/category evidence accepts the actual named minimum; wrong winner/pairing and details-only evidence fail |
| AC-05 | Partial results, missing/invalid completeness metadata, narrow filters, scope expansion, partial unions and stale completeness fail for guarded comparison wording |
| AC-06 | Production registry rejects string/float cents, unknown currency fields, duplicate keys and boolean limits without repair or additional model request |
| AC-07 | Reproduced RED failures precede runtime corrections; targeted and full GREEN results recorded above |
| AC-08 | 633-test preflight passes; all pre-existing test files unchanged; final 633 + 103 = 736 passing tests |
| AC-09 | Existing policy/source/injection/current-turn/worker/deadline tests pass; new provenance and sanitized-diagnostic regressions pass; no tool, data, dependency or diagnostic contract changes |

These observations support human Gate V review. They are not owner acceptance
or a self-approved gate transition.

## Security and scope review

- Monetary arithmetic uses integer cents throughout. Only a verified budget
  clause is exempt; catalog and policy price support is otherwise retained.
- Search provenance is private, current-turn state. Tool messages, schemas,
  argument validation, catalog SQL, policy retrieval and read-only dispatch are
  unchanged. No free-form SQL, command tool or mutation capability was added.
- The LLM still chooses tools semantically. Regexes validate answer claims and
  provenance only; they do not select tools or route customer intent.
- Existing policy conflicts/cautions, warranty distinctions, source checks,
  stock restrictions, snapshot reminders and current-turn evidence remain.
- No raw arguments, customer messages, tool payloads or secrets were added to
  diagnostics. New tests assert sanitized invalid-argument metadata and forbid
  provider access. Existing diagnostic and injection suites pass.
- Diff review confines changes to the seven approved files; no dependency,
  provider, deadline, worker, supplied-data or governance edit is present.
  `.env` and `.vscode/` were preserved. No external/Git delivery action occurred.

## Remaining limitations and handoff

Budget quoting deliberately accepts only a complete standalone affirmative
customer declaration. A longer budget request can receive supported product
prices without quoting the limit. A budget-containing answer cannot include
arbitrary policy prose or implicit price references; omit the budget quote to
compose those answers. This is conservative and can reject valid paraphrases.

Minimum acceptance uses exact whole-answer query/category templates and
recognized pt-BR comparison cues. Unqualified global claims are rejected when
recognized, even with a complete narrow search. This is not an exhaustive
natural-language entailment checker: arbitrary paraphrases, implicit claims and
general source-field semantic truth remain limitations of this prototype.
A lexical-query minimum describes only that query's matches. More than 50
matches, excessive result size or missing scope/completeness prevents proof;
limits were not raised and partial searches are not merged into a proof.

No real-provider run was authorized or performed. Offline success cannot prove
model adherence, improved latency, customer experience or the cause of the
historical Nemotron invalid arguments, whose raw payloads were not retained.
Provider/model selection and all F-06 workstreams beyond F-06A remain unchanged.

**Next action:** human review of this evidence and the seven-file diff for
Gate V. Stop locally; commit and publication require explicit authorization.
