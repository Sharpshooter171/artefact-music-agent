# F-04 — Evaluation and Delivery Verification

**Date:** 2026-11-02 (BRT), before the owner-stated 23:59 BRT deadline.\
**Observed branch / HEAD:** `main` / `7baac223dd86ad51b0c28513210727dc4ad474a2`.\
**Authorization:** owner explicitly approved F-04 v1.0 S/P and authorized local
implementation, offline verification, temporary clean clones and at most four
additional real free-model conversations. No commit, push, PR, merge or submission.

**Result:** documentation, four authentic transcripts, offline verification and
baseline clean-clone reproduction completed. The official matrix remains **10
PASS, 2 BLOCKED**: AC-02 and AC-10 await the post-merge final-F-04-HEAD
reproduction required by the plan. **Gate V: CONDITIONALLY APPROVED for PR
preparation by the 2026-11-02 human review; Gate D remains PENDING.** The review
required approval metadata and whitespace corrections, now applied. This is
execution evidence, not self-approval or delivery.

## Approval and traceability boundary

The requested [F-04 specification](../specs/F-04-evaluation-delivery.md) and
[implementation plan](../plans/F-04-implementation-plan.md) were absent at the
first preflight and subsequently supplied by the owner. Both v1.0 files have now
been read and the matrix below uses their actual AC definitions. The original
missing-document blocker is resolved. `docs/decisions/` contains no files.

The owner's explicit approval of F-04 v1.0 S/P in the execution request is the
approval authority. No renewed approval is required or inferred. During the
2026-11-02 human review, Gate V was conditionally approved for PR preparation and
two documentation corrections were required. The spec header now records **Gate
S APPROVED** and the plan header records **Gate P APPROVED**, both dated
2026-11-02. Eight trailing-whitespace findings in header lines 3–6 of the two
files were also removed. No acceptance criteria, technical requirements or
approved implementation scope were changed. These two files are therefore no
longer byte-identical to their original arrival versions; all other protected
files remain unchanged apart from the intentional `.gitignore` edit.
The plan requires public-origin baseline reproduction and a separate clean
clone at the final F-04 HEAD after a separately authorized merge. A baseline
clone or local document overlay cannot satisfy that future final-HEAD check.

## Changes and preservation

- `README.md`: independent **Music Store AI Agent** identity; problem/solution,
  architecture, four tool contracts, setup, exact free-model configuration,
  validation evidence, decisions, limitations and ChatGPT/Codex disclosure.
- `examples/README.md`, `01-catalog.md`, `02-policy.md`, `03-combined.md`,
  `04-out-of-scope.md`: four actual Portuguese single-turn conversations with
  provenance, observed tool metadata and honest outcome notes.
- `.gitignore`: ignore `*.egg-info/`, which editable installation generated in
  the initial clean clone. No runtime/dependency change.
- This report.

Pre-existing changes to `AGENTS.md`, `docs/PROJECT_CONSTITUTION.md` and
`.vscode/settings.json` were preserved. The private `.env`, all six supplied
CSVs, original PDF, application, scripts, tests, `.env.example` and
`pyproject.toml` remain unchanged. Integrity comparison uses a preflight
SHA-256 manifest of 61 existing files: **60 unchanged**, with only the intentional
`.gitignore` change observed. No TDD cycle was needed for documentation and the
ignore rule; no application contract or historical verification file was modified.
The supplied F-04 spec/plan were added by the owner, not generated in this run;
they were later edited only for the owner-requested approval metadata and header
whitespace corrections.

## Full offline results

Existing local environment: **Python 3.14.4**, `pytest 8.4.2`, `pypdf 6.21.4`.
The entire suite ran with this audit hook installed before pytest execution:

```bash
.venv/bin/python - <<'PY'
import sys
import pytest

def offline(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise RuntimeError("F-04 offline verification forbids network access")

sys.addaudithook(offline)
raise SystemExit(pytest.main(["-q"]))
PY
.venv/bin/python -m pip check
.venv/bin/python -m app --help
```

Observed: **448 passed in 7.35s; 0 failed, 0 skipped**, exit 0.
`pip check`: **No broken requirements found**, exit 0. CLI help: exit 0.
After the owner-requested metadata and whitespace corrections, the final
preflight rerun observed **448 passed in 7.87s**, `pip check` clean, **19 relative
Markdown links resolved**, and **0 trailing-whitespace findings** in the nine new
F-04 files.
All unchanged F-01/F-02/F-03 tests were included. The audit hook blocks those
network operations in the pytest interpreter; CLI help subprocesses perform
no API work. Mock tests establish deterministic behavior, not real-model intent
accuracy. No tests were added, removed or rewritten.

After the official criteria became available, local CLI startup/exit was also
executed using the unchanged private configuration and input `sair`:
`.venv/bin/python -m app --debug-tools`, exit **0**, no configuration error,
no key in output and no tool/model request. The key was never copied to a clone.

## Fresh-clone reproduction

An independent local Git clone was created using Git transport, without copying
the working tree, `.env`, generated database/index or private traces:

```bash
git clone --no-local /home/igor-caldas/artefact-music-agent \
  /tmp/music-agent-f04-d79rx8v8/checkout
cd /tmp/music-agent-f04-d79rx8v8/checkout
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m scripts.build_catalog \
  --data-dir data/raw --output data/generated/catalog.sqlite
.venv/bin/python -m scripts.build_policy_index \
  --input 'resources/políticas_da_loja.pdf' \
  --output data/generated/policy_index.json
# Run the identical network-blocking pytest wrapper shown above.
.venv/bin/python -m pip check
.venv/bin/python -m app --help
```

The subprocess environment was restricted to basic path/home/locale and TLS
certificate settings; provider keys and artifact overrides were excluded.
Both `.env` and `data/generated/` were confirmed absent before the build.
Observed on **Python 3.12.12**:

| Step | Actual result |
| --- | --- |
| Independent clone at baseline HEAD | Exit 0 |
| New venv and editable dependency installation | Exit 0; pypdf 6.21.4, pytest 8.4.2 |
| Catalog build | Exit 0; 9 categories, 65 products; 61 available, 1 out of stock, 1 coming soon, 2 discontinued |
| Policy build | Exit 0; version 2.1, 8 pages, 28 sections |
| Complete network-blocked pytest suite | **448 passed in 7.22s; 0 failed, 0 skipped**, exit 0 |
| `pip check` | No broken requirements found; exit 0 |
| CLI `--help` | Exit 0; no key required or model request |

Catalog snapshot:
`021b88c544c06dc7aaae190149e8dd07d61fa120bf0d701b8d41eb83f6826d05`.
PDF SHA-256:
`b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7`.
Initial clone status exposed only editable-install `*.egg-info/` metadata;
the new ignore rule addresses this. Since F-04 files are deliberately
uncommitted, the Git clone tests baseline runtime code. At that time, the F-04
documents and ignore rule were separately overlaid from an explicit eight-file
allowlist: all copies matched byte-for-byte, all eight whitespace checks were
clean and all 16 relative Markdown links resolved. That byte-for-byte state was
later superseded only by the owner-requested approval-metadata and
trailing-whitespace corrections to the spec and plan. After the ignore rule, the clone status
contains only the intended F-04 files. This is not represented as a committed
F-04 checkout. No real-model
conversation is required for clean reproduction, and no private key is copied.
Local detailed output is ignored at `data/generated/f04-clean-reproduction.json`.

### Public-origin baseline check after plan reconciliation

The public origin was independently cloned into
`/tmp/music-agent-f04-public-ck8s61_5/checkout`, without the private `.env` or
generated files. Its detached HEAD was verified as the full baseline SHA above:

```bash
git -c credential.helper= clone \
  https://github.com/Sharpshooter171/music-store-ai-agent.git \
  /tmp/music-agent-f04-public-ck8s61_5/checkout
cd /tmp/music-agent-f04-public-ck8s61_5/checkout
git checkout --detach 7baac223dd86ad51b0c28513210727dc4ad474a2
git rev-parse HEAD
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m scripts.build_catalog \
  --data-dir data/raw --output data/generated/catalog.sqlite
.venv/bin/python -m scripts.build_policy_index \
  --input 'resources/políticas_da_loja.pdf' \
  --output data/generated/policy_index.json
# Run the identical network-blocking pytest wrapper shown above.
.venv/bin/python -m pip check
.venv/bin/python -m app --help
```

**All commands exited 0.** Python 3.12.12, pypdf 6.21.4 and pytest 8.4.2;
**448 passed in 6.89s**, zero failures/skips. Both source builders reproduced
the counts and hashes above. `pip check` reported no broken requirements;
help exited 0. `.env` was absent before and after execution. The child environment
contained only basic path/home/locale settings, Git noninteractive/config
controls and pip's version-check setting; no provider configuration was copied.
The baseline still produces untracked editable-install metadata, addressed by
the local F-04 ignore rule. Detailed logs are confined to that temporary root.
This fulfills the public-baseline check; **the final post-merge F-04 clone is
still BLOCKED**, since no F-04 commit or merge is authorized or present.

## Authentic conversations and real-model budget

**Four** recordings are retained under `examples/`. The three historical
recordings are copied from full F-03 source text, not reconstructed from the
shortened verification quotations. The historical combined prompt is exactly
`Tem ukulele e desconto pagando no PIX?`; a longer wording in the F-03 summary
table differs, so the raw execution artifact controls the transcript.

| Recording | Actual result |
| --- | --- |
| Catalog, one new F-04 conversation | `search_products` ok; HTTP 200 twice; final host `GROUNDING_FAILED`; honest safe fallback, **not** a successful factual answer |
| Policy, prior F-03 | `search_store_policies` ok; PIX 5% rule, non-stacking and dated-promotion caution |
| Combined, prior F-03 | Both catalog and policy tools ok; ten catalog prices and PIX rules; known unsupported checkout wording retained |
| Out of scope, prior F-03 | No tool; model selects `out_of_scope`, host renders canonical pt-BR redirect |

F-04 used **exactly one additional conversation / two HTTP requests**. Both
returned the pinned `nvidia/nemotron-3-ultra-550b-a55b:free` and reported cost `0`.
No retry, model substitution, paid route or paid fallback occurred. Existing
zero provider price caps and disabled fallback remained in force. Billing was
not independently audited. The new conversation ran at
`2026-11-02T05:19:11.200589+00:00` through `05:19:29.510744+00:00`
(02:19 BRT); no further real calls were made.

**4/4** exact user/final-response blocks and source artifact hashes were checked.
An additional deterministic comparison found **10/10** combined-answer product
names and BRL prices matching current catalog results, with all ten available
and the same recorded snapshot ID. This does not validate arbitrary model prose.
The selected tool metadata is explicitly labelled as an extract, not a full raw
trace. New artifact SHA-256:
`44cad9d54197c8fe00e86b9c9e3acec07c9e7c06717ae181f53ed3d620f8031b`.
Historical artifact SHA-256:
`4847a941a485b6fa8982c08b80dd90b39ce31bbb63493f0da45fa3542bf62c02`.
The ignored files `f04-catalog-live.json`,
`f03-router-live-smoke-final-bcd.json` and `f04-examples-check.json` remain local.

## Security, source integrity and diff review

- Preflight audit examined **68 tracked files and 80 reachable Git blobs**.
  The configured API key had **0 exact matches** in tracked files or reachable
  history. Recognizable provider/GitHub token patterns and private-key markers
  yielded **0 candidates**. No remote URL contained detected embedded credentials.
- No tracked/historical `.env`, generated database/index or log paths were
  found; `.env.example` is intentional. `.env` and generated artifacts are
  ignored. The first scan covered **75 files** (68 tracked working files plus
  seven new documents): **0** configured-key matches, token/private-key
  candidates, forbidden tracked artifacts or exact copied fictional customer
  name/phone/email values in the new documents. Evidence is ignored at
  `data/generated/f04-security-final.json`.
- After the owner supplied the spec/plan, scanning covered **77 files** (the
  same 75 plus both supplied files): **0** configured-key matches, recognizable
  token/private-key candidates or copied customer name/phone/email values in
  the nine new documents. The two supplied files were subsequently edited only
  for the owner-requested approval metadata and header whitespace; they no longer
  match their original arrival hashes. All other protected files remain unchanged
  apart from the intentional ignore rule among the original 61. All newly
  authored F-04 files are whitespace-clean; **19 relative Markdown links resolve**
  and were revalidated after the metadata edits. Existing ignored evidence was preserved.
- All six original CSVs and the PDF match HEAD byte-for-byte. The generated
  catalog contains only `catalog_meta`, `categories` and `products`.
- Customer-shaped fields exist in the supplied fictional customer/order CSVs;
  they are not copied into these deliverables or sent by catalog tools. The
  [F-01 plan](../plans/F-01-implementation-plan.md) explicitly records owner
  approval for unchanged publication of all six fictional CSVs. The
  [F-02 spec](../specs/F-02-policy-retrieval.md) records approval of the fictional
  PDF despite its internal-use label. This review does not authorize a new
  publish action or exposure of real customer data.
- `git diff --check` exited 0, and explicit untracked-file whitespace checks
  reported no errors. All eight changed/new F-04 files received review; no
  dependency, source, test, prompt or tool-contract changes occurred. Protected
  user changes are excluded from the agent's changes. Staged files: **0**.

These checks cover the configured credential, known patterns and reachable Git
objects. They cannot prove the absence of every possible secret format or
recover unreachable/deleted external artifacts.

## Official AC-01 through AC-12 acceptance matrix

Mapped to specification v1.0 and its implementation plan: **10 PASS, 2 BLOCKED**.
The blocked rows reflect the plan's required final-HEAD check, not a failure of
the observed baseline commands. PASS applies to the bounded evidence described.

| ID | Approved criterion | Status and observed evidence |
| --- | --- | --- |
| AC-01 | README | **PASS**: independent branding, purpose, architecture, four tools, provider, decisions and limitations |
| AC-02 | Quick start | **BLOCKED** for final acceptance: public-baseline install/builds/448 tests/help passed; private-config local CLI startup/exit passed; post-merge final-F-04-HEAD clone is pending under plan §5 |
| AC-03 | Provider safety | **PASS**: placeholder-only template; exact tested Nemotron in README; free availability/quotas and no paid fallback disclosed; no detected secret |
| AC-04 | Genuine examples | **PASS**: four actual pt-BR dialogues, provenance and tool names; 4/4 exact comparisons; catalog fallback clearly labelled; unrelated request included |
| AC-05 | Functional evaluation | **PASS**: catalog, availability, cited policy, mixed tools, out-of-scope, failure, contradictions and unknown facts mapped in the table below |
| AC-06 | Regression | **PASS**: unchanged 448 tests pass with network operations blocked locally and in both baseline clones; pip check and tracked/agent-authored whitespace checks clean |
| AC-07 | Source integrity | **PASS**: six CSVs and original PDF unchanged; generated SQLite/index ignored |
| AC-08 | Public/privacy audit | **PASS** within documented scan limits: no detected key/private trace/new personal record disclosure; historic fictional-material approvals verified; no new external service |
| AC-09 | Minimalism | **PASS**: no new framework, dependency, runtime/tool API change or rewritten history; pre-existing local work preserved |
| AC-10 | Delivery clarity | **BLOCKED** for final acceptance: current SHA, public URL, commands, limitations, AI disclosure and pending submission instructions documented; final-F-04-HEAD clone remains pending under plan §5 |
| AC-11 | Genuine status | **PASS**: actual observations separated from mocks, historical evidence and pending checks; submission NOT_SUBMITTED; Gate D not passed |
| AC-12 | Grounding caveat | **PASS** via explicit documentation option: unsupported `aplicado no checkout` retained and explained; no hallucination-elimination claim |

### AC-05 functional coverage

All named tests below are unchanged and included in the executed 448-test suites.
AC IDs embedded in their names belong to earlier features, not this F-04 matrix.

| Behavior | Existing executed evidence |
| --- | --- |
| Catalog and availability | `test_search_products.py::test_default_search_returns_only_available_products_in_stable_order`, `test_availability_filters_are_exact`; combined real example and 10/10 exact catalog-price comparisons |
| Policy and citations | `test_policy_search.py::test_real_source_probes_ac01_ac03_ac05_ac06_ac08`; authentic policy example with PDF sections/pages |
| Mixed-source tool invocation | `test_agent_orchestrator.py::test_mixed_policy_catalog_evidence_ac04_ac05`; authentic combined example calls both tools |
| Safe unrelated response | `test_agent_orchestrator.py::test_llm_semantic_scope_redirect_without_tools_ac15`; authentic tool-free out-of-scope example |
| Tool failure and empty evidence | `test_agent_orchestrator.py::test_failure_empty_evidence_is_safe_ac07`, `test_agent_tools.py::test_tool_exception_does_not_leak_secret_or_path`; new catalog example separately demonstrates a grounding-rejection fallback |
| Contradictions and warranty distinction | `test_agent_orchestrator.py::test_policy_conflict_suppresses_confident_resolution_ac08`, `test_warranty_procedure_caution_is_always_retained_ac08` |
| Unknown or unsupported facts | `test_agent_orchestrator.py::test_unsupported_facts_fail_closed_without_tool_ac09`, `test_product_details.py::test_unknown_product_returns_error_without_stock`, `test_policy_search.py::test_irrelevant_or_generic_requests_ac08` |

## Delivery checklist

- **Repository:** [Sharpshooter171/music-store-ai-agent](https://github.com/Sharpshooter171/music-store-ai-agent).
- **Latest reviewed HEAD:** `7baac223dd86ad51b0c28513210727dc4ad474a2`;
  F-04 files remain uncommitted local changes.
- **Local evidence:** README, four authentic recordings, full tests, baseline
  public clone and privacy/integrity checks completed as recorded above.
- **Human Gate V decision:** CONDITIONALLY APPROVED for PR preparation on
  2026-11-02; AC-02/AC-10 and Gate D remain pending final-HEAD checks.
- **Commit/push/PR/merge:** NOT_AUTHORIZED in this execution; none performed.
- **Final merged F-04 SHA and clean public clone:** PENDING separately authorized
  Git actions. Re-run install, both builders, offline pytest, pip check and help
  at that exact final SHA. AC-02/AC-10 remain BLOCKED until observed.
- **Recruiter channel, filenames and exact format:** PENDING confirmation from
  definitive recruiter instructions; neither email nor upload format is assumed.
- **Deadline:** owner-stated **2026-11-02 23:59 BRT**; not independently confirmed
  against recruiter instructions in this execution.
- **Submission:** NOT_SUBMITTED; explicit owner authorization still required.
- **Gate D:** PENDING. Freeze repository after submission or deadline; no
  post-submission modifications.

Suggested GitHub About text, for owner use only; no setting was changed:

> Python CLI music-store assistant with real LLM tool calling, a read-only SQLite catalog, PDF policy retrieval, and reproducible tests.

## Final working-tree state

Observed `git status --short --branch`:

```text
## main...origin/main
 M .gitignore
 M AGENTS.md
 M docs/PROJECT_CONSTITUTION.md
?? .vscode/
?? README.md
?? docs/plans/F-04-implementation-plan.md
?? docs/specs/F-04-evaluation-delivery.md
?? docs/verification/F-04-verification.md
?? examples/
```

`AGENTS.md`, the constitution and `.vscode/` were already changed/untracked at
preflight and remain byte-identical to that state. `git diff --cached --name-only`
returned no files. HEAD is unchanged. Ignored execution/build evidence remains
local and is not included in the delivery files.

## Limitations, blockers and handoff

1. **Final-HEAD blocker:** the original criteria are now mapped. AC-02 and AC-10
   still require the final merged F-04 SHA and its clean public-origin clone.
   Those Git actions are outside this execution's authorization; baseline
   success cannot be represented as final-F-04-HEAD verification.
2. **Observed live limitation:** the new catalog run retrieved products but
   rejected its final model response. Rejected model prose was not retained, so
   the exact triggering guard branch is unknown. No claim that the model
   invented facts or that the guard produced a false positive is justified.
   No retries or unapproved source changes were used to improve the example.
3. The historical combined answer says `aplicado no checkout`, which the PDF
   does not explicitly support. Grounding checks do not prove every sentence
   or product/price association. Duplicated policy cautions are also visible.
4. Python 3.12.12 and 3.14.4 were exercised; Python 3.11 was not separately
   tested. Dependencies have compatible ranges rather than a lockfile. Future
   free inference availability is not guaranteed.
5. No commit, push, PR, merge, release, publication or submission was performed.
   No Git history was rewritten. Delivery channel/final submission remains
   outside this authorization.

**NEXT:** owner review of the corrected approval metadata and whitespace plus the
final preflight. PR preparation is conditionally approved, but no commit, push,
PR or merge is authorized in this execution. AC-02/AC-10 remain blocked until the
final merged HEAD can be reproduced in a clean public clone. No additional model
calls are needed; submission remains separately gated.
