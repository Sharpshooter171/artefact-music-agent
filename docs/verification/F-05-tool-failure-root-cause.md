# F-05 — Production Tool Failure Trace and Offline Verification

**Date:** 2026-11-02 (BRT)\
**Branch / HEAD:** `feature/f05-latency-resilience` / `2c7a7e5`\
**Authorization:** owner-requested production tool-path diagnosis and correction,
safe error classification and offline regression tests only.\
**Gate V:** PENDING OWNER REVIEW. No real LLM request, `.env` edit, commit, push,
PR or merge occurred in this round.

## Root cause or remaining uncertainty

The owner supplied a real observation: HTTP 200, 3648 ms, selected
`search_products`, tool duration 61 ms, final `TOOL_FAILURE`. The original
invocation was not repeated. Those observations cannot distinguish invalid tool
arguments, an unknown category, catalog availability or a worker protocol failure.
No unique historical root cause is claimed.

Two defects were reproduced offline:

1. The orchestrator discarded every failed tool result's code and recorded
   `TOOL_FAILURE` in both tool trace and duration diagnostics. The worker adapter
   also collapsed nonzero exit, invalid JSON/output and invalid envelopes into
   `TOOL_FAILURE`. This conclusively explains the lost diagnostic classification.
2. The worker forced its working directory to the repository root. Direct catalog
   calls and CLI preflight resolved relative artifact paths from the caller's
   directory. A temporary fixture catalog accessed through a relative path worked
   directly but returned `CATALOG_UNAVAILABLE` through the actual worker. This is
   a demonstrated possible cause of direct/worker disagreement; the original
   user's working directory and artifact configuration are not established here.

The worker now inherits caller cwd. Its absolute script path, isolated Python
mode and explicit absolute application import root are preserved. This fixes
artifact resolution without changing F-01/F-02 retrieval or deadline enforcement.

## Verified production call path

| Stage | Actual code evidence |
| --- | --- |
| Entry point | `app/__main__.py` invokes `app.agent.cli.main()` |
| CLI | `app/agent/cli.py:122` constructs `Orchestrator(ChatClient(config))`, with no registry injection |
| Default registry | `app/agent/orchestrator.py:52` constructs `ToolRegistry()` |
| Parent dispatch | `app/agent/orchestrator.py:169` selects callable `dispatch_with_deadline`; direct fallback applies to injected registries without that method |
| Worker adapter | `app/agent/tool_registry.py:179` implements deadline dispatch; `_run_tool_worker` launches the actual isolated worker at line 204 |
| Child execution | `app/agent/tool_worker.py:57` invokes child `ToolRegistry().dispatch(name, arguments)` |
| Retrieval | `ToolRegistry.dispatch` validates arguments and invokes one of the four fixed read-only catalog/policy functions |

Eight CLI integration cases use actual CLI preflight, the real default registry
and real spawned/reaped workers. Parent direct dispatch is patched to fail the
test if called; the child imports the unchanged dispatch implementation in its
separate interpreter. Only the model/configuration are synthetic. Tests assert
the actual `python -I tool_worker.py` command and cover absolute/relative artifact
paths, valid/unknown categories and debug/normal modes. The worker file's mere
existence is not used as execution evidence.

## Safe error classification

| Fixed code | Verified condition |
| --- | --- |
| `INVALID_ARGUMENT` | Existing registry validation rejects malformed JSON or invalid argument types/ranges |
| `CATEGORY_NOT_FOUND` | Existing catalog query cannot find the supplied category |
| `CATALOG_UNAVAILABLE` | Existing catalog open/schema/query checks fail |
| `WORKER_PROTOCOL_ERROR` | Invalid IPC input/output, malformed failure envelope, nonzero child exit, worker launch or pipe failure |
| `TOOL_FAILURE` | Unexpected tool exception or unrecognized/untrusted error code |

The shared allowlist also retains verified existing `UNKNOWN_TOOL`,
`PRODUCT_NOT_FOUND`, `POLICY_UNAVAILABLE` and `TOOL_OUTPUT_TOO_LARGE` codes.
Worker failure envelopes returned to the parent are reduced to the fixed code,
generic message and empty details/meta. Arbitrary error strings never become
debug codes. Tool trace and duration diagnostics retain the safe cause; the
turn-level error remains `TOOL_FAILURE`, and the customer receives the existing
generic pt-BR fallback. A failed tool never triggers another model request for
repair. Grounding remains required for successful factual replies.

Observed tool-only offline debug output (synthetic model, real local worker):

```text
[ferramenta: search_products]
[erro: CATEGORY_NOT_FOUND]
[ferramenta: search_products, duration_ms=148.191]
[requisição: latency_ms=0.147]
[turno: duration_ms=148.674, request_count=1, deadline=within_budget]
[erro: TOOL_FAILURE]
```

The last line is the generic turn outcome; the preceding tool code identifies
the safe debugging cause. This example contains no live-provider HTTP claim.
No raw arguments, queries, customer messages, prompts, product payloads, HTTP
bodies, credentials, exception text, tracebacks or filesystem paths are printed.

## Files changed in this round

- `app/agent/tool_registry.py` — inherit caller cwd; shared safe-code allowlist;
  classify protocol failures and sanitize failed worker envelopes.
- `app/agent/orchestrator.py` — preserve safe tool cause in diagnostic metadata;
  generic turn error and customer fallback remain intact.
- `app/agent/cli.py` — use the shared verified tool-code allowlist.
- `app/agent/tool_worker.py` — distinguish malformed IPC from tool execution
  failures; retain bounded fixed failure output.
- `tests/test_agent_tool_diagnostics.py` — 22 new offline tests for actual worker
  argument/category/catalog failures, relative path parity, protocol failures,
  allowlisted diagnostics, redaction and grounding.
- `tests/test_agent_cli_tool_path.py` — eight actual CLI/worker integration cases.
- This verification record.

No benchmark refinement was performed. SHA-256 comparison of 103 other project
files found no changes during this round, including the benchmark/tests, README,
model/default/allowlist configuration, deadline modules, worker supervision,
F-01/F-02 source, governance, approved spec/plan, prior verification/F-04 history,
supplied/generated data and dependencies. The public schema-definition block in
`tool_registry.py` was compared with its start-of-round contents and is identical.
`.env` was not edited. Existing unrelated worktree changes were preserved.

## Actual test results

RED, before runtime changes:

```text
.venv/bin/python -m pytest -q tests/test_agent_tool_diagnostics.py
15 failed, 7 passed in 1.52s

.venv/bin/python -m pytest -q tests/test_agent_cli_tool_path.py
4 failed, 4 passed in 6.86s
```

GREEN, final runtime changes:

```text
.venv/bin/python -m pytest -q tests/test_agent_tool_diagnostics.py tests/test_agent_tool_deadline.py tests/test_agent_cli_tool_path.py
38 passed in 5.90s

.venv/bin/python -m pytest -q
633 passed in 23.02s

.venv/bin/python -m pip check
No broken requirements found.

git diff --check
(no output; clean)
```

Independent read-only review found no blocking findings and reran the 30 new
tests: **30 passed in 3.49s**. The existing grounding, fail-closed and real local
deadline/cancellation tests pass in the full suite. New tests prohibit provider
access and use synthetic credentials/model messages with real temporary local
catalog/policy artifacts and child processes. Existing full-suite loopback-only
HTTP tests remain offline with respect to external providers.

## Gate V recommendation

The scoped correction and diagnostic evidence are ready for owner review.
**Keep Gate V PENDING**: the historical real failure cannot be assigned a unique
cause from the available evidence, and no live request or performance claim is
made. Work stops after this offline verification. Further real-provider testing
requires separate owner authorization.
