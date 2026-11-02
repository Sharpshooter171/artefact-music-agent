# F-01 — Verification Evidence

**Feature:** F-01 — Data Foundation & Catalog Tools\
**Date:** November 1, 2026\
**Branch:** `main`\
**HEAD observed before verification:** `32e4c0450de05bac2e756bb6edd3f9a88525dc07`\
**Spec baseline:** `docs/specs/F-01-data-foundation-catalog.md`, v0.3, Gate S APPROVED\
**Plan baseline:** `docs/plans/F-01-implementation-plan.md`, v0.2, approved by the human owner\
**Verification status:** APPROVED / GATE V PASSED (human review, November 1, 2026)

This document records executed commands and observed results. It is not a
self-approval of Gate V.

## 1. Environment

| Item | Observed |
| --- | --- |
| Python | `3.14.4` |
| SQLite | `3.46.1` |
| pytest | `8.4.2` inside `.venv` |
| `python` command | Not available; `.venv/bin/python` used |
| Virtual environment | `.venv/`, created for this run |
| Network use during tests | None |

Project environment setup:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

The editable install resolved `pytest 8.4.2`, satisfying the declared
`pytest>=8,<9` constraint. `.venv/` is ignored by Git. The root-level
`*.egg-info` build artifact produced by the editable install was removed after
installation, and the suite still passed.

### 1.1 RED evidence

Before the catalog modules existed, the harness and tests were created and
`pytest -q` was executed. The run failed at collection with nine
`ModuleNotFoundError` errors, one for each test module importing a not-yet-built
catalog module. Examples: `No module named 'app.catalog.database'`,
`'app.catalog.tools'`, `'app.catalog.normalization'`, `'app.catalog.rules'`.
This is the recorded RED state; implementation then proceeded through
GREEN/REFACTOR without weakening the tests.

## 2. Source integrity

All six supplied CSV files are present under `data/raw/`. Only the products and
categories files were passed to the importer.

| File | Size (bytes) | SHA-256 |
| --- | ---: | --- |
| `desafio_tecnico_ai_eng - categories.csv` | 756 | `7a7901e16c8c6357a956031ada45a6fd6a4cc9bd7bc1edc05448cc55b01b0a9e` |
| `desafio_tecnico_ai_eng - products.csv` | 22399 | `78d911d96ee891abb163b6c858e895025aa530ab27d0290540f05d5098377c12` |
| `desafio_tecnico_ai_eng - customers.csv` | 3756 | `1cd724dc86eac6258913cc890abf23d3893c57a99c9325ebfb91dfad3c7b0f37` |
| `desafio_tecnico_ai_eng - order_items.csv` | 230 | `7656eb681821d48e0c932f61d3188309b955c25446578235f2d8e69604b0f0bc` |
| `desafio_tecnico_ai_eng - orders.csv` | 1324 | `deb9c2480605d8d22117d569f0045fd156c5e9a58ffeebb847ff61b3b9512fd5` |
| `desafio_tecnico_ai_eng - promotions.csv` | 839 | `cbe08c7e91b00437c0c00a7ef1486deba73de52d23e3f97f51a7dbd557d759e0` |

The two catalog hashes match the plan baseline. `sha256sum data/raw/*.csv`
after import produced the same values, confirming the importer did not modify
the sources. Synthetic tests also assert that source bytes are unchanged and
that an extra out-of-scope CSV is not read.

## 3. Import command and report

Command:

```bash
.venv/bin/python -m scripts.build_catalog \
  --data-dir data/raw \
  --output data/generated/catalog.sqlite
```

Observed exit code: `0`.

Report summary:

```json
{
  "status": "ok",
  "snapshot_id": "021b88c544c06dc7aaae190149e8dd07d61fa120bf0d701b8d41eb83f6826d05",
  "rows_read": 74,
  "canonical_rows_loaded": 74,
  "counts": {
    "categories": 9,
    "products": 65,
    "by_status": {
      "active": 62,
      "discontinued": 2,
      "coming_soon": 1
    },
    "by_availability": {
      "available": 61,
      "out_of_stock": 1,
      "coming_soon": 1,
      "discontinued": 2
    }
  }
}
```

Source report entries:

```json
[
  {
    "name": "desafio_tecnico_ai_eng - categories.csv",
    "size_bytes": 756,
    "sha256": "7a7901e16c8c6357a956031ada45a6fd6a4cc9bd7bc1edc05448cc55b01b0a9e",
    "rows_read": 9
  },
  {
    "name": "desafio_tecnico_ai_eng - products.csv",
    "size_bytes": 22399,
    "sha256": "78d911d96ee891abb163b6c858e895025aa530ab27d0290540f05d5098377c12",
    "rows_read": 65
  }
]
```

Rejected rows: `0`. Warnings: `0`.

The generated SQLite file is under `data/generated/` and is ignored by Git:

```text
.gitignore:15:data/generated/	data/generated/catalog.sqlite
```

## 4. Real-data tool checks

Executed checks passed:

| Check | Observed |
| --- | --- |
| Default `Ukuleles` search | 10 returned, truncated |
| `Ukuleles` with `available`, limit 50 | 14 returned |
| `Ukuleles` with `any`, limit 50 | 15 returned |
| `coming_soon` product included only with `any` | Product 130 present |
| Zero-product category search | Successful empty list |
| `list_categories` | 9 categories |
| `Ukuleles.product_count` | 15 |
| Product 81 price `599.9` | `59990` cents |
| Product 96 | `out_of_stock` |
| Product 130 | `coming_soon` |
| Product 136 | `discontinued` |
| Stock exposure | No `stock_quantity` in tool payloads |
| Snapshot consistency | Report and all checked tool responses returned `021b88c5...826d05` |

Zero-product categories observed: `Cordas Orquestrais`,
`Instrumentos de Sopro (Madeiras)`, `Instrumentos de Sopro (Metais)`.

`get_product_details` success metadata:

```json
{
  "snapshot_id": "021b88c544c06dc7aaae190149e8dd07d61fa120bf0d701b8d41eb83f6826d05",
  "returned": 1,
  "truncated": false
}
```

## 5. Database and scope checks

Observed tables in the generated database:

```text
catalog_meta, categories, products
```

Observed metadata:

```json
{
  "categories_sha256": "7a7901e16c8c6357a956031ada45a6fd6a4cc9bd7bc1edc05448cc55b01b0a9e",
  "products_sha256": "78d911d96ee891abb163b6c858e895025aa530ab27d0290540f05d5098377c12",
  "schema_version": "1",
  "snapshot_id": "021b88c544c06dc7aaae190149e8dd07d61fa120bf0d701b8d41eb83f6826d05"
}
```

`stock_quantity` is present internally in `products` and absent from public tool
payloads. No customer, order, order-item, promotion, user, brand, or model
tables/columns exist in the catalog schema.

## 6. Test suite

Command:

```bash
.venv/bin/python -m pytest -q
```

Observed result:

```text
103 passed in 0.34s
```

Acceptance coverage:

| AC | Evidence |
| --- | --- |
| AC-01 | `test_importer.py`, `test_security_boundaries.py`; real report shows only two sources and unchanged hashes |
| AC-02 | `test_reproducibility.py`; identical canonical rows, counts, and snapshot IDs |
| AC-03 | `test_validation.py`, `test_importer.py`; fail-closed validation and old-database preservation |
| AC-04 | `test_importer.py`; all fields, provenance, relationships, descriptions, and specs loaded |
| AC-05 | `test_normalization.py`, `test_search_products.py`; case/accent/whitespace and multi-token matching |
| AC-06 | `test_search_products.py`; real-data Ukuleles `10/14/15`, zero-category empty, unknown-category error |
| AC-07 | `test_search_products.py`; price, availability, ordering, truncation, and unfiltered-dump rejection |
| AC-08 | `test_product_details.py`; descriptions/specs, availability, unknown ID, no stock |
| AC-09 | `test_rules.py`, `test_search_products.py`; status mapping and default `available` search |
| AC-10 | `test_rules.py`, `test_validation.py`; exact cents, invalid/over-precision rejection, BRL currency |
| AC-11 | `test_search_products.py`; description/spec search without brand/model extraction |
| AC-12 | `test_list_categories.py`; real-data 9 categories, empty categories, counts, order, no hierarchy |
| AC-13 | `test_importer.py`, `test_database.py`; report/database/tool snapshot consistency |
| AC-14 | `test_security_boundaries.py`, `test_product_details.py`; codes, sanitized messages, no paths/SQL/traces |
| AC-15 | `test_database.py`, `test_search_products.py`; read-only enforcement, literal wildcard/injection-like text |
| AC-16 | `pyproject.toml`; offline synthetic suite independent of versioned datasets |
| AC-17 | `test_security_boundaries.py`; no out-of-scope tables or public stock exposure |

## 7. Repository state

`git diff --check` completed with no output.

`git status --porcelain` observed:

```text
 M AGENTS.md
 M docs/PROJECT_CONSTITUTION.md
?? app/
?? data/
?? docs/plans/
?? docs/specs/
?? docs/verification/
?? pyproject.toml
?? scripts/
?? tests/
```

`AGENTS.md` and `docs/PROJECT_CONSTITUTION.md` modifications are pre-existing
and were not changed by this implementation. All six source CSVs remain under
the untracked `data/` entry, pending an authorized commit. No `.env`,
credentials, generated database, cache, or temporary artifact is tracked.

Ignored generated/cache paths observed:

```text
.venv/
.pytest_cache/
app/__pycache__/
app/catalog/__pycache__/
data/generated/
scripts/__pycache__/
tests/__pycache__/
```

## 8. Known limitations and follow-ups

- The plan file still displays `Status: DRAFT / GATE P PENDING`; Gate P approval
  was given by the human outside the file. The plan was not rewritten during
  implementation.
- `unshare -n ... pytest` could not be used because this environment denied the
  network namespace operation (`Operação não permitida`). The suite imports no
  network libraries, makes no network calls, and uses only local fixtures and
  `tmp_path`.
- No commit, push, PR, tag, or external publication was performed.
- Real-data evidence was produced locally from the six supplied CSVs; the
  generated database must not be committed.
- F-01 intentionally does not implement LLM orchestration, customer CLI, policy
  retrieval, orders, payments, promotions, auth, or brand/model extraction.
