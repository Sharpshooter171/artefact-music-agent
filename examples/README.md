# Authentic conversations

These four single-turn conversations use the real OpenRouter model `nvidia/nemotron-3-ultra-550b-a55b:free`. Customer messages and final application responses are copied verbatim from execution artifacts. They are not hand-written demonstrations or mock results. Engineering notes are separate from the Portuguese dialogue.

| Example | Origin | Actual outcome |
| --- | --- | --- |
| [Catalog](01-catalog.md) | One additional F-04 conversation, 2026-11-02 | Tool succeeded; final response rejected by grounding checks; safe fallback |
| [Policy](02-policy.md) | Earlier F-03 execution, 2026-11-02 | PIX policy answer with PDF evidence |
| [Combined catalog and policy](03-combined.md) | Earlier F-03 execution, 2026-11-02 | Catalog prices and PIX policy; known unsupported checkout wording preserved and annotated |
| [Out of scope](04-out-of-scope.md) | Earlier F-03 execution, 2026-11-02 | Model classification followed by the host's tool-free scope redirect |

Each example records model identity, observed HTTP statuses, tool arguments/result metadata, and the SHA-256 of its ignored source artifact. Tool evidence is a selected extract, not a fabricated replacement result. Full raw provider messages, credentials, customer records, and internal policy dumps are excluded. The local source artifacts are not part of Git; [F-03 verification](../docs/verification/F-03-verification.md) records the historical execution context.

The set contains three successful historical scenarios and one new failed catalog-answer scenario. It demonstrates both useful responses and a real limitation. The combined scenario provides successful catalog coverage; the new catalog-only run must not be counted as a successful factual answer. Original F-03 catalog success is summarized in its verification report, but its full dialogue was not retained and has not been reconstructed here.

F-04 used exactly **one additional real conversation**, comprising **two HTTP requests**, with no retry or paid fallback. Both returned the pinned Nemotron model and reported cost `0`; account billing was not independently audited. These recordings do not establish future endpoint availability or semantic correctness for arbitrary questions.
