# Project Constitution — Empório da Música AI Agent

**Project:** Artefact AI Engineer Technical Challenge  
**Document:** `PROJECT_CONSTITUTION.md`  
**Version:** 1.0 — approved baseline  
**Status:** APPROVED / GATE C PASSED  
**Approved by:** Project owner (candidate), explicit approval in conversation  
**Approval date:** November 1, 2026  
**Approval scope:** All constitution-level proposals in this document are accepted. Feature specifications, implementation plans, code, external-service costs, and submission actions still require their own review/gates.  
**Language:** English for engineering documentation; Brazilian Portuguese for customer conversations.

## 1. Mission and purpose

Build a small, demonstrably functional Python AI customer-service agent for Empório da Música, a fictional music-instrument store. The agent must handle text conversations with the store's tone, decide when to retrieve operational data versus store policies, and respond accurately within an explicitly bounded scope.

The primary deliverable is a **defensible prototype** showing engineering reasoning, trustworthy retrieval, sensible trade-offs, and reproducible testing — **not** a production-ready multi-tenant platform.

## 2. Stakeholders and users

- **Customer:** A person asking about available musical instruments, prices, store hours, payment conditions, returns, and general store information.
- **Evaluator:** Artefact engineers reviewing working behavior, README, architecture, choices, tests, examples, and Git history.
- **Maintainer:** The candidate should be able to understand, reproduce, and explain every design choice.

## 3. Product scope: MVP

### Must have

- Python application that accepts and answers text messages through a CLI.
- A real LLM used for intent interpretation, tool selection, and natural-language response composition.
- Read-only tool(s) grounded in the provided product/category CSVs for catalog searches, current catalog prices, and recorded stock availability.
- Retrieval of relevant sections of the supplied store-policy PDF for business rules and store information.
- Store-aligned persona: friendly, informal but professional, helpful to musicians.
- Responsible behavior for out-of-scope questions, missing information, ambiguous queries, and tool/API failure.
- Three to five **genuine** example conversations recorded from actual agent executions, including at least one nontrivial case.
- An accurate README describing setup, provider/model configuration, architectural decisions, limitations, test commands, and AI coding-assistant use.
- Public GitHub repository showing genuine incremental progress, with no post-deadline modifications.

### Optional, only after MVP acceptance

- Promotion rules and non-stacking discount logic, subject to validated time/status semantics.
- Order-status lookup, provided that access controls can be honestly demonstrated.
- Lightweight conversation context for a single CLI session.
- Minimal UI or API if it adds meaningful value without jeopardizing deliverables.

### Intentionally excluded

- Real WhatsApp/Meta integration, external production deployment, payments, order mutations, multi-tenant workspaces, CRM, autonomous tool execution, vector DB, full LangGraph orchestration, enterprise auth, and production SLAs.

## 4. Technology decisions: approved baseline

- **Primary language:** Python 3.11+.
- **Interaction:** CLI first.
- **LLM:** A **real, provider-configurable LLM with tool/function-calling support** is approved. The concrete provider/model, API costs (if any), and credentials remain implementation choices to be proposed in F-03 planning and recorded in the README; no paid service is authorized by this document.
- **Data:** Keep supplied CSVs unchanged as raw inputs. Validate fields, types, identifiers, and relevant relations. **SQLite is the preferred local query layer**, generated from the source CSVs; use safe, read-only deterministic parameterized queries. The precise import schema, library choices, and migrations belong to F-01 planning.
- **Policies:** Extract/document sections from the supplied PDF and retrieve by business topic; avoid embeddings until there is evidence they improve retrieval quality.
- **Quality:** pytest with mocked LLM/tool transport for deterministic tests, plus separate real-model smoke runs.
- **Secrets:** `.env` for local config, `.env.example` with placeholders, no credentials in Git or logs.
- **Version control:** Public Git repository with meaningful commits and no history rewriting after submission.

## 5. Product and engineering invariants

1. **Evidence before answer:** Prices, stock, discounts, order status, store hours, and policy conditions must be grounded in source data or explicit policy text; never invented by the LLM.
2. **Structured data is authoritative for operational values:** The LLM can select a tool but not overwrite verified tool results.
3. **Policies are authoritative for business rules:** When the manual is contradictory or unclear, state uncertainty and refer to a human rather than fabricating a definitive rule.
4. **Safe by default:** No write/mutation tools; no leakage of customer PII, private order details, provider credentials, or full internal data dumps.
5. **Snapshot honesty:** CSVs are a provided data snapshot, not a live inventory API. Do not imply real-time external synchronization.
6. **No overengineering:** The smallest solution meeting acceptance criteria wins over unnecessary frameworks and infrastructure.
7. **Reproducible behavior:** Deterministic business logic is unit-testable without an LLM or network.
8. **Transparent assistance:** The README must accurately describe how AI coding assistants were used and what was reviewed/tested by the candidate.
9. **Documented assumptions:** Contradictions or missing requirements become explicit assumptions or limitations, not invented facts.
10. **Separation of responsibilities:** The human sets scope, requirements, security boundaries, and acceptance criteria; the coding agent proposes low-level plans and implementations, subject to verification.

## 6. Source-of-truth hierarchy

1. Artefact's technical challenge and delivery instructions.
2. The supplied store-policy PDF for store policies, with ambiguities documented.
3. The relevant supplied CSV records for catalog and operational facts.
4. Approved project constitution and approved feature specs for implementation contracts.
5. Implementation and runtime outputs as evidence, never as a substitute for requirements.

When sources conflict, do not silently resolve it: report it in the decision log and specify safe runtime behavior.

## 7. Development workflow — constitution → specs → plan/implement/verify

### Gate C: Constitution approved — PASSED (2026-11-01)
- **DONE:** Human reviewed and approved mission, scope, constraints, technical direction, roadmap, workflow, and delivery strategy as constitution V1.0.
- **NEXT:** Place/version this approved `PROJECT_CONSTITUTION.md` in the local Git repository before feature implementation (not yet evidenced by this document).
- **NEXT:** Create `AGENTS.md` consistent with this constitution to guide coding agents (not a replacement for the constitution).
- **Boundary:** Gate C approval does **not** pass Gate S, P, I, or V automatically.

### Gate S: Feature spec approved
Each feature spec must state user need, in/out of scope, source of truth, interface/tool contract, acceptance criteria, errors/edge cases, security considerations, and test strategy. The human approves the spec before implementation.

### Gate P: Plan reviewed
The coding agent proposes file-level steps, dependencies, test cases, risks, and commit boundaries; human reviews the proposed plan.

### Gate I: Implement
Prefer red → green → refactor: create tests for approved acceptance criteria, implement the minimum, preserve contracts, and keep changes within the feature scope.

### Gate V: Verify
Run deterministic tests, targeted manual checks, real-model smoke checks, diff/security review, and record concrete evidence. Reject undocumented scope creep. Commit only after passing the required gates.

## 8. Feature roadmap and delivery order

1. **F-01 — Data foundation & catalog tools:** inspect source tables, validate them, build read-only catalog retrieval with pricing and stock checks.
2. **F-02 — Policy retrieval:** extract and organize policy content, define topic lookup and safe ambiguity behavior.
3. **F-03 — LLM orchestration & CLI:** tool calling, persona, multi-message loop, fallback and error handling.
4. **F-04 — Evaluation & documentation:** acceptance matrix, tests, 3–5 actual conversations, README, clean-start reproduction, final delivery.
5. **Optional F-05:** promotions, order access with privacy safeguards, or minimal UX improvements, only if F-01–F-04 are accepted and time permits.

## 9. Acceptance criteria for final delivery

- A clean checkout can install dependencies and run the agent using the documented steps.
- A real model can answer both a catalog question and a store-policy question by calling appropriate tools.
- Catalog queries do not present zero-stock/discontinued products as available.
- Unsupported requests and missing facts produce honest, polite, non-fabricated responses.
- Guardrails prevent revealing customer order details without validated authorization (or no order lookup is exposed at all).
- Core automated tests pass without network access.
- 3–5 actual run transcripts, including at least one policy application or multi-constraint data query, are in the repository.
- README covers decisions, limitations, setup, test/run commands, and coding assistant workflow.
- Public repository has credible incremental commits, no secrets, and is frozen after submission.

## 10. Critical known ambiguities

- Store manual provides inconsistent contact numbers in different sections; explicitly select/flag a safe policy rather than guessing.
- Store manual separates a 30-day defect-exchange process from a 90-day statutory warranty; avoid presenting them as interchangeable.
- Source CSVs are static snapshots, not live external records.
- Email and challenge PDF mention differing submission channels/formats; verify and satisfy the definitive recruiting instructions before submission.
- Due date is relative to a recruiter email; avoid assuming a holiday/business-day interpretation without confirmation.
- The PDF is labelled internal-use; decide how to package the supplied materials in a public repository without improperly exposing actual private information. In this fictional exercise, document the assumption and minimize copied data where possible.

## 11. Ownership and change control

- The candidate owns the architecture, scope, decision log, and acceptance criteria.
- Coding assistants may propose and implement changes only against approved specs.
- New dependencies, external services, sensitive-data exposure, and feature-scope changes require an explicit updated spec/decision.
- A code change cannot override this constitution. Revise the constitution/spec with a documented reason first.
- Final repository state must be reviewed, tagged or marked with a commit SHA, and not modified after submission.

## 12. Immediate next actions (after Gate C approval)

1. **DONE — Constitution approved:** V1.0 is the accepted baseline; no outstanding constitution-level approval remains.
2. **NEXT — Initialize/version documents:** Create the independent local Git repository, initial README, `AGENTS.md`, decision log, and approved constitution; review and create the first genuine documentation commit.
3. **NEXT — F-01 spec:** Draft and review the data-foundation feature spec, fixtures, tool contracts, and acceptance tests; approval is still required at Gate S.
4. **NEXT — Plan only:** Request a coding-agent implementation plan against the approved F-01 spec; review at Gate P before code changes.
5. **NEXT — Implement and verify:** After the corresponding gates pass, carry out red → green → refactor → verify and document evidence at Gate V.

## 13. Approval record and remaining decision boundaries

- **Constitution approval:** Approved by the project owner on November 1, 2026, following review of version 0.1.
- **Approved choices:** Python 3.11+, CLI-first, real LLM with function calling, read-only structured catalog lookup with SQLite as the preferred local layer, PDF policy retrieval without mandatory embeddings, pytest plus real-model smoke tests, no unnecessary infrastructure, and the F-01–F-04 roadmap with optional F-05.
- **No pending constitution-level decisions:** This document is approved for use as the project baseline.
- **Deferred, not pre-approved:** Concrete model/provider and spending; F-01 table/import design; feature specs; implementation plans; coding changes; publication of third-party-provided documents or personal data; and final submission. These follow their respective gates.
- **Change control:** Any material change to scope, source-of-truth rules, security guarantees, or workflow requires a documented constitution revision approved by the project owner.
- **Evidence boundary:** Approval here records the candidate's decision, not proof that Git has been initialized, any commit has been made, a feature has been implemented, or a delivery has occurred.
