# F-01 — Implementation Plan

**Project:** Empório da Música AI Agent\
**Feature:** F-01 — Data Foundation & Catalog Tools\
**Document:** `docs/plans/F-01-implementation-plan.md`\
**Version:** 0.2 — Gate P adjustment for authorized dataset publication\
**Status:** APPROVED / GATE P PASSED\
**Date:** November 1, 2026\
**Prepared by:** Coding agent, for human review\
**Spec baseline:** `docs/specs/F-01-data-foundation-catalog.md`, F-01 v0.3, Gate S APPROVED\
**Authorization:** Planning-only adjustment. The project owner has authorized versioning and publication of all six supplied fictional CSV datasets, byte-identical. This document does not authorize implementation, dependency installation, database generation, commits, pushes, PRs, or other external actions.

---

## 1. Purpose and authorization status

This plan converts the approved F-01 v0.3 specification into a minimal,
file-level implementation and test plan. It covers AC-01 through AC-17, the
database design, public tool contracts, TDD order, real-data verification,
reproducibility, privacy, rollback, and stop conditions.

Owner decision recorded for this revision: all six supplied CSV datasets are
fictional and may be versioned and published in the public GitHub repository
without byte changes. F-01 still reads and imports only the products and
categories CSVs; the other four datasets remain outside its scope.

Current gates:

| Gate | Status | Evidence |
| --- | --- | --- |
| C — Constitution | APPROVED | `docs/PROJECT_CONSTITUTION.md` |
| S — F-01 spec v0.3 | APPROVED | Approval record in `docs/specs/F-01-data-foundation-catalog.md` |
| P — This plan | PENDING | This document |
| I — Implementation | BLOCKED | Requires explicit Gate P approval |
| V — Verification | NOT_RUN | Requires implementation |

Repository baseline observed on November 1, 2026:

- Branch: `main`
- HEAD: `32e4c0450de05bac2e756bb6edd3f9a88525dc07`
- Existing modifications: `AGENTS.md`, `docs/PROJECT_CONSTITUTION.md` (pre-existing; preserve)
- Untracked: `data/` (six supplied CSVs), `docs/specs/`, `docs/plans/`
- Existing implementation directories: none. `app/`, `scripts/`, and `tests/` do not exist yet.

This plan preserves the approved spec's scope, acceptance criteria, canonical
model, and public tool contracts. It does not add brand/model extraction,
promotions, orders, customer data, LLM calls, a customer CLI, FTS, or an external
service.

## 2. Baselines, constraints, and assumptions

### 2.1 Source baseline

Only these two files are F-01 inputs:

- `data/raw/desafio_tecnico_ai_eng - categories.csv`
- `data/raw/desafio_tecnico_ai_eng - products.csv`

Observed on November 1, 2026:

| File | Rows | SHA-256 |
| --- | ---: | --- |
| categories CSV | 9 | `7a7901e16c8c6357a956031ada45a6fd6a4cc9bd7bc1edc05448cc55b01b0a9e` |
| products CSV | 65 | `78d911d96ee891abb163b6c858e895025aa530ab27d0290540f05d5098377c12` |

Expected successful real-data import: 65 products, 9 categories, and status
counts `62 active`, `2 discontinued`, `1 coming_soon`.

Owner decision: all six supplied CSV datasets are fictional and are authorized
for versioning and publication in the public GitHub repository. The six files
are the two catalog inputs above plus `customers.csv`, `orders.csv`,
`order_items.csv`, and `promotions.csv`. They must remain byte-for-byte
unchanged. F-01 still reads only the two catalog inputs; the other four remain
unread by F-01 and outside its scope.

### 2.2 Implementation constraints

- Python 3.11+.
- Runtime uses only the standard library: `csv`, `sqlite3`, `decimal`,
  `unicodedata`, `hashlib`, `json`, `pathlib`, `dataclasses`, `argparse`.
- `pytest` is the only development dependency.
- No network access during import, query, or tests.
- No ORM, FTS, vector database, web framework, HTTP API, or customer CLI.
- All SQL values are bound parameters. No caller-provided SQL.
- Catalog tools open SQLite in read-only mode.
- Generated SQLite is written only under `data/generated/` by default and is
  never committed.
- Customer-facing facts come only from the validated snapshot. Exact
  `stock_quantity` is internal.

### 2.3 Assumptions carried forward

- The supplied CSVs are a static snapshot.
- The observed status vocabulary is exhaustive for this snapshot; unknown
  values fail import.
- Product and category identifiers are stable for this snapshot.
- `created_at` is required as a header but its value is not used.
- Product/category display text is trimmed; `specs` values are preserved as
  supplied.
- `source_row` means the 1-based data-record ordinal excluding the header. The
  first data record is `1`.
- The test suite uses synthetic fixtures and must not depend on the real
  datasets. A clean checkout contains all six original CSVs; real-data
  verification is a separate integration check, not a test prerequisite.

### 2.4 Unchanged surfaces and publication status

All six original CSV datasets may be versioned and published in the public
repository, byte-identical. Only the products and categories CSVs are F-01
inputs; the other four are published source materials that F-01 must not read or
import.

These files and materials must not be modified by F-01 implementation:

- `AGENTS.md`
- `docs/PROJECT_CONSTITUTION.md`
- `docs/specs/F-01-data-foundation-catalog.md` (except future approved record updates)
- `data/raw/desafio_tecnico_ai_eng - categories.csv`
- `data/raw/desafio_tecnico_ai_eng - products.csv`
- `data/raw/customers.csv`
- `data/raw/orders.csv`
- `data/raw/order_items.csv`
- `data/raw/promotions.csv`
- `resources/` policy materials
- `examples/`
- All F-02/F-03/F-04 behavior

## 3. Minimal architecture

### 3.1 Layers and responsibilities

```text
constants/errors
      ↓
normalization/rules
      ↓
validation
      ↓
database
      ↓
importer ─────→ scripts/build_catalog.py
      ↓
tools
```

- `constants.py`: fixed filenames, schema version, statuses, availability values,
  defaults, limits, environment variable name.
- `errors.py`: typed catalog errors and sanitized error codes.
- `normalization.py`: NFKD/casefold/whitespace normalization and tokenization.
- `rules.py`: Decimal price parsing, cent conversion, and status-to-availability
  mapping.
- `validation.py`: header/row/failure/warning validation and canonical record
  construction. No SQLite writes.
- `database.py`: schema DDL, writable import connection, read-only tool
  connection, metadata lookup.
- `importer.py`: orchestration, source hashing, snapshot ID, validation report,
  temporary database, atomic replacement.
- `tools.py`: public `search_products`, `get_product_details`,
  `list_categories`, argument validation, parameterized SQL, result envelopes.
- `scripts/build_catalog.py`: engineering-only import command. It is not a
  customer CLI.

Dependency direction is one-way. `tools.py` does not import `importer.py`;
`validation.py` does not import `database.py`. This prevents circular imports.

### 3.2 Database path configuration

- Default: `data/generated/catalog.sqlite`.
- Override for tests and verification: `EMPORIO_CATALOG_DB` environment variable.
- Public tool signatures do not expose a database-path parameter.
- Tools do not auto-build the database. A missing database returns
  `CATALOG_UNAVAILABLE`.
- Read-only connections use `Path.resolve().as_uri()` plus `?mode=ro`, with
  `PRAGMA query_only=ON`, so paths containing spaces are handled safely.

### 3.3 No customer CLI

`scripts/build_catalog.py` is an internal maintenance command. F-01 adds no
customer-facing CLI, chat loop, persona, or LLM integration.

## 4. File-level changes

### 4.1 New application and tooling files

| Path | Action | Purpose | ACs |
| --- | --- | --- | --- |
| `app/__init__.py` | New | Package marker | AC-16 |
| `app/catalog/__init__.py` | New | Catalog package marker and public exports | AC-07, AC-08, AC-12 |
| `app/catalog/constants.py` | New | Fixed filenames, schema version, enums, defaults, limits | AC-01, AC-09, AC-10, AC-17 |
| `app/catalog/errors.py` | New | Typed errors, error codes, sanitized envelopes | AC-14 |
| `app/catalog/normalization.py` | New | Deterministic text normalization and tokenization | AC-05, AC-11 |
| `app/catalog/rules.py` | New | Price parsing, exact cents, availability mapping | AC-09, AC-10 |
| `app/catalog/validation.py` | New | CSV structure/value validation and canonical records | AC-03, AC-04, AC-10 |
| `app/catalog/database.py` | New | Schema, import connection, read-only connection, metadata | AC-01, AC-13, AC-15 |
| `app/catalog/importer.py` | New | Hash, validate, normalize, atomic build, report | AC-01, AC-02, AC-03, AC-04, AC-13 |
| `app/catalog/tools.py` | New | Public read-only catalog functions and envelopes | AC-06, AC-07, AC-08, AC-09, AC-11, AC-12, AC-14, AC-15 |
| `scripts/__init__.py` | New | Makes `python -m scripts.build_catalog` reliable | AC-16 |
| `scripts/build_catalog.py` | New | Engineering-only import command and JSON report | AC-01, AC-02, AC-16 |

### 4.2 Configuration and ignore rules

| Path | Action | Purpose | ACs |
| --- | --- | --- | --- |
| `pyproject.toml` | New | Python 3.11+ metadata, setuptools config, pytest config, `pytest` dev dependency | AC-16 |
| `.gitignore` | Unchanged | Existing rules keep generated SQLite, `.env` files, credentials, caches, temporary artifacts, and logs ignored. Do not add a `data/raw` ignore rule | AC-01, AC-16, AC-17 |

All six original CSV datasets may be tracked and published byte-identical. F-01
still reads only the products and categories CSVs. Generated SQLite databases,
credentials, caches, and temporary artifacts remain ignored.

### 4.3 Test files and fixtures

| Path | Action | Purpose | ACs |
| --- | --- | --- | --- |
| `tests/conftest.py` | New | Temporary catalog builder, fixture readers, malformed-fixture helpers, database-path setup | AC-03, AC-16 |
| `tests/fixtures/catalog_valid/categories.csv` | New | Small valid synthetic categories, including a zero-product category | AC-04, AC-06, AC-12 |
| `tests/fixtures/catalog_valid/products.csv` | New | Small valid synthetic products covering statuses, prices, accents, specs, and filter cases | AC-04, AC-05, AC-07, AC-09, AC-10, AC-11 |
| `tests/fixtures/catalog_edge/categories.csv` | New | Synthetic categories for normalization and duplicate-name warnings | AC-03, AC-05 |
| `tests/fixtures/catalog_edge/products.csv` | New | Synthetic products for wildcards, SQL-like literals, duplicate names, and edge prices | AC-03, AC-05, AC-10, AC-11, AC-15 |
| `tests/test_normalization.py` | New | Normalization, tokenization, search-text construction, ordering keys | AC-05, AC-11 |
| `tests/test_rules.py` | New | Price/cents acceptance and rejection, availability mapping | AC-09, AC-10 |
| `tests/test_validation.py` | New | Header, identifier, category, orphan, status, price, stock, and specs failures; warnings | AC-03, AC-04, AC-10 |
| `tests/test_importer.py` | New | Valid load, provenance, report counts, atomic failure, hashes, snapshot ID | AC-01, AC-02, AC-03, AC-04, AC-13 |
| `tests/test_database.py` | New | Schema, indexes, metadata, read-only enforcement | AC-13, AC-15 |
| `tests/test_search_products.py` | New | Text/category/price/availability/limit filters, ordering, truncation, literals | AC-05, AC-06, AC-07, AC-09, AC-11, AC-15 |
| `tests/test_product_details.py` | New | Details, specs, descriptions, no stock, unknown ID | AC-08, AC-14 |
| `tests/test_list_categories.py` | New | All categories, counts, order, no hierarchy | AC-12 |
| `tests/test_security_boundaries.py` | New | Error sanitization, missing database, read-only, no out-of-scope tables/columns | AC-01, AC-14, AC-15, AC-17 |
| `tests/test_reproducibility.py` | New | Two imports produce identical rows, order, counts, and snapshot ID | AC-02, AC-13 |
| `docs/verification/F-01-verification.md` | New at verification | Real-data report, commands, outputs, hashes, limitations | AC-01 through AC-17 |

Synthetic fixtures are isolated TDD inputs only; they are not a replacement for
the versioned datasets. No generated SQLite file is committed. Tests use
`tmp_path` for databases and never write to `data/generated/`.

## 5. Database design and import algorithm

### 5.1 Schema version 1

`app/catalog/database.py` owns this DDL:

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE catalog_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    description TEXT NOT NULL,
    specs_json TEXT NOT NULL,
    search_text TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
    status TEXT NOT NULL CHECK (status IN ('active', 'discontinued', 'coming_soon')),
    availability TEXT NOT NULL CHECK (availability IN ('available', 'out_of_stock', 'coming_soon', 'discontinued')),
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL
);

CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_products_normalized_name ON products(normalized_name);
CREATE INDEX idx_products_availability ON products(availability);
CREATE INDEX idx_products_price_cents ON products(price_cents);
```

`catalog_meta` stores at least:

- `schema_version = "1"`
- `snapshot_id = "<64 lowercase hex characters>"`
- `categories_sha256`
- `products_sha256`

No `created_at`, brand, model, customer, order, promotion, hierarchy, or stock
display columns are added.

### 5.2 Canonical record rules

- Trim category and product display fields.
- Preserve `specs` string values as supplied; canonicalize JSON only.
- `normalized_name = normalize(name)`.
- `search_text = normalize(category_name + " " + name + " " + description + " " + all spec values in sorted key order)`.
- `specs_json = json.dumps(specs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`.
- `price_cents` is an exact integer from `Decimal`.
- `availability` follows the approved status table exactly.
- `source_file` is the source basename, not an absolute path.
- `source_row` is the 1-based data-record ordinal excluding the header.

### 5.3 Snapshot ID

For deterministic metadata:

```text
payload = "\n".join(f"{basename}:{sha256}" for basename, sha256 in sorted(files))
snapshot_id = sha256(payload.encode("utf-8")).hexdigest()
```

The two basenames and their content hashes are included. Sorted ordering makes
the result independent of import argument order. No timestamp or random value is
included.

### 5.4 Import flow

1. Read only the two fixed source files from `--data-dir`.
2. Read bytes once; compute SHA-256; decode with `utf-8-sig` and `newline=""`.
3. Validate headers and all rows; collect critical issues and warnings.
4. If any critical issue exists, publish no database and return a failed report.
5. Normalize records, derive availability, and canonicalize specs JSON.
6. Create a temporary SQLite file inside the output directory.
7. Insert categories, then products, then metadata inside a transaction.
8. Run `PRAGMA foreign_key_check` and `PRAGMA integrity_check`.
9. Close the connection and atomically replace the output with `os.replace`.
10. Remove the temporary file on any failure; leave an existing database intact.
11. Print a JSON validation report to stdout and return process exit code `0` or
    `1`.

If the output directory does not exist, create it. If the destination is an
existing database, replacement is atomic. The importer must never write under
`data/raw/`.

### 5.5 Validation behavior

Critical, fail closed:

- Missing/unreadable source file.
- Undecodable UTF-8 content.
- Missing/renamed required header, blank header, or duplicate header.
- Duplicate product IDs or category IDs.
- Duplicate normalized category names across distinct IDs.
- Orphan product category reference.
- Blank name, description, category name, or category description.
- Invalid/negative/over-precision price.
- Blank/negative/non-integer stock.
- Missing/unknown status.
- Blank `specs`, invalid JSON, non-object JSON, or non-string spec values.
- Non-positive/non-integer category or product IDs.

Warnings, import may proceed:

- Extra unknown columns.
- Duplicate normalized product names without duplicate IDs.

Valid and expected, not warnings:

- Category with zero products.
- Category name absent from product names.
- `coming_soon` or `discontinued` with non-zero stock.
- `active` with zero stock.
- Zero-row data file with valid headers (structurally valid, successful import).

Price parsing accepts only the observed decimal forms with zero, one, or two
decimal places. A regex guard rejects signs, exponents, currency symbols, blank
values, and more than two decimal places before `Decimal` conversion. Examples:
`849` → `84900`; `599.9` → `59990`; `199.99` → `19999`.

### 5.6 Validation report

The import report is JSON and contains:

```json
{
  "status": "ok",
  "snapshot_id": "64-hex-character-hash",
  "source_files": [
    {
      "name": "desafio_tecnico_ai_eng - categories.csv",
      "size_bytes": 756,
      "sha256": "64-hex-character-hash",
      "rows_read": 9
    },
    {
      "name": "desafio_tecnico_ai_eng - products.csv",
      "size_bytes": 22399,
      "sha256": "64-hex-character-hash",
      "rows_read": 65
    }
  ],
  "rows_read": 74,
  "canonical_rows_loaded": 74,
  "rows_rejected": [],
  "warnings": [],
  "counts": {
    "categories": 9,
    "products": 65,
    "by_status": {"active": 62, "discontinued": 2, "coming_soon": 1},
    "by_availability": {
      "available": 61,
      "out_of_stock": 1,
      "coming_soon": 1,
      "discontinued": 2
    }
  }
}
```

Failed reports use `"status": "failed"`, a null `snapshot_id` when sources cannot
be read, and structured issues with file, source row, field, code, severity, and
sanitized message. Reports contain basenames, not absolute paths, secrets, or
full dataset dumps.

## 6. Public tool contracts

### 6.1 Exact public functions

```python
def search_products(
    query: str | None = None,
    category: str | None = None,
    price_min_cents: int | None = None,
    price_max_cents: int | None = None,
    availability: str = "available",
    limit: int = 10,
) -> dict: ...

def get_product_details(product_id: int) -> dict: ...

def list_categories() -> dict: ...
```

These parameter lists match the approved spec. The database path is not a public
argument; it is resolved from `EMPORIO_CATALOG_DB` or the default path.

### 6.2 Result envelopes

- Success: `{"ok": true, "data": {...}, "meta": {"snapshot_id": "...", "returned": N, "truncated": bool}}`.
- Failure: `{"ok": false, "error": {"code": "...", "message": "...", "details": {...}}, "meta": {"snapshot_id": "... or null"}}`.
- `get_product_details` success uses `returned: 1`, `truncated: false`.
- `list_categories` success uses `returned: len(categories)`, `truncated: false`.
- Empty search results are successful with `products: []`.

### 6.3 Argument validation

| Function | Rule |
| --- | --- |
| `search_products` | Trim `query`; require 2–120 characters when present; reject non-string |
| `search_products` | Trim `category`; require 1–80 characters when present; reject non-string |
| `search_products` | Require at least one of `query`, `category`, `price_min_cents`, or `price_max_cents` |
| `search_products` | `price_min_cents`/`price_max_cents` must be non-negative integers, not booleans |
| `search_products` | `price_max_cents >= price_min_cents` when both are present |
| `search_products` | `availability` must be exactly one of the documented values |
| `search_products` | `limit` must be an integer from 1 through 50, not a boolean |
| `get_product_details` | `product_id` must be a positive integer, not a boolean |
| `list_categories` | No arguments |

Invalid arguments return `INVALID_ARGUMENT` with field-level details and execute
no SQL.

### 6.4 Query behavior

- Normalize query, category, and tokens with the approved NFKD/casefold/whitespace
  algorithm.
- Tokenize query on whitespace. Every token must match `instr(search_text, ?) > 0`.
  `instr` makes `%`, `_`, and escape characters literal.
- Resolve category by exact `normalized_name`. Existing zero-product category
  returns success with no products. Unknown category returns `CATEGORY_NOT_FOUND`.
- Apply inclusive price bounds.
- `availability="any"` applies no availability predicate. Other values apply
  exact equality.
- Default is `available`.
- Order by `normalized_name ASC, product_id ASC`.
- Fetch `limit + 1` rows to compute `truncated` without a second query.
- Return only `product_id`, `name`, `category {id,name}`, `price {amount_cents,
  currency:"BRL"}`, and `availability`.
- Never expose `stock_quantity`.
- Details returns description and structured `specs` from `specs_json`.
- Categories returns all categories ordered by `normalized_name ASC,
  category_id ASC`, with `product_count` from a left join counting all products.

### 6.5 Error mapping

| Condition | Code |
| --- | --- |
| Invalid type, length, range, or filter combination | `INVALID_ARGUMENT` |
| Unknown normalized category | `CATEGORY_NOT_FOUND` |
| Unknown product ID | `PRODUCT_NOT_FOUND` |
| Missing/unreadable/corrupt database or unsupported schema version | `CATALOG_UNAVAILABLE` |
| Unexpected failure at tool boundary | `INTERNAL_ERROR` |

Messages are sanitized engineering text. No stack trace, SQL text, file path, or
secret appears. Empty results are not errors.

## 7. TDD sequence and acceptance mapping

### 7.1 Red → green → refactor sequence

1. **Packaging and fixtures (RED/GREEN):** add `pyproject.toml`, package markers,
   synthetic fixtures, and `tests/conftest.py`; run pytest with no application
   code to establish collection failure.
2. **Normalization (RED/GREEN/REFACTOR):** write `test_normalization.py`; implement
   `normalization.py`; cover case, accents, whitespace, tokenization, and
   search-text order.
3. **Rules (RED/GREEN/REFACTOR):** write `test_rules.py`; implement `rules.py`;
   cover zero/one/two-decimal prices, over-precision, blanks, negatives, and all
   four availability mappings.
4. **Validation (RED/GREEN/REFACTOR):** write malformed-fixture tests; implement
   `validation.py`; verify fail-closed errors and warnings.
5. **Database and import (RED/GREEN/REFACTOR):** write `test_database.py` and
   `test_importer.py`; implement schema, read-only connection, hashing, snapshot
   ID, atomic replacement, and report.
6. **Search tool (RED/GREEN/REFACTOR):** write `test_search_products.py`; implement
   filters, ordering, truncation, literal matching, and envelopes.
7. **Details tool (RED/GREEN/REFACTOR):** write `test_product_details.py`;
   implement details without stock exposure.
8. **Categories tool (RED/GREEN/REFACTOR):** write `test_list_categories.py`;
   implement all-category listing and counts.
9. **Security and scope (RED/GREEN/REFACTOR):** write
   `test_security_boundaries.py`; verify read-only enforcement, sanitized errors,
   literal injection-like text, and absence of out-of-scope tables/columns.
10. **Reproducibility (RED/GREEN/REFACTOR):** write
    `test_reproducibility.py`; verify two imports produce identical canonical
    rows, ordering, counts, and snapshot ID.
11. **Real-data smoke (after unit/integration green):** run the import against the
    supplied CSVs and record evidence.
12. **Full refactor and review:** run the entire suite, inspect diff, confirm no
    generated or private data is staged.

No application code is written before Gate P approval.

### 7.2 Acceptance-criteria coverage

| AC | Primary tests | Key assertions |
| --- | --- | --- |
| AC-01 | `test_importer.py`, `test_security_boundaries.py` | Source bytes unchanged; only two sources read; DB under generated path; no out-of-scope tables |
| AC-02 | `test_reproducibility.py`, `test_importer.py` | Two imports match canonical rows, order, counts, and snapshot ID |
| AC-03 | `test_validation.py`, `test_importer.py` | Missing header, duplicate IDs/names, orphan, invalid status fail closed; old DB remains |
| AC-04 | `test_importer.py` | All fields, provenance, relationships, descriptions, and specs load |
| AC-05 | `test_normalization.py`, `test_search_products.py` | Case/accent/whitespace match; every token required |
| AC-06 | `test_search_products.py` | Category filter independent of names; Ukuleles 10/14/15; zero category empty; unknown category error |
| AC-07 | `test_search_products.py` | Inclusive price, availability, limit, ordering, truncation; unfiltered dump rejected |
| AC-08 | `test_product_details.py` | Description/specs preserved; stock absent; unknown ID error |
| AC-09 | `test_rules.py`, `test_search_products.py` | All availability mappings; default search only `available` |
| AC-10 | `test_rules.py`, `test_validation.py` | Decimal/exact cents; invalid/over-precision fails; BRL constant |
| AC-11 | `test_search_products.py` | Description/spec values are searchable; no brand/model extraction |
| AC-12 | `test_list_categories.py` | All 9 categories, empty categories, counts, order, no hierarchy |
| AC-13 | `test_importer.py`, `test_database.py` | Import and all successful tools share the same snapshot ID |
| AC-14 | `test_security_boundaries.py`, `test_product_details.py` | Error codes, sanitized messages, no SQL/paths/traces |
| AC-15 | `test_database.py`, `test_search_products.py` | Writes fail; injection-like and wildcard text treated literally |
| AC-16 | `pyproject.toml`, full suite, clean-checkout run | Offline `pytest` using isolated synthetic fixtures, independent of the versioned datasets |
| AC-17 | `test_security_boundaries.py`, diff review | No LLM/CLI/promotions/orders/auth/payment/mutation/brand/model features |

## 8. Real-data verification

Run after implementation and before claiming F-01 verification.

### 8.1 Pre-import integrity

```bash
sha256sum \
  "data/raw/desafio_tecnico_ai_eng - categories.csv" \
  "data/raw/desafio_tecnico_ai_eng - products.csv"
```

Expected hashes match section 2.1. Re-run after verification and compare. Also
confirm all six versioned CSVs are present and byte-identical to the committed
versions; only the two catalog files are passed to the importer.

### 8.2 Build and capture report

```bash
python -m scripts.build_catalog \
  --data-dir data/raw \
  --output data/generated/catalog.sqlite \
  | tee /tmp/f01-import-report.json
```

Expected report:

- `status = "ok"`
- 9 categories and 65 products
- status counts `62 active`, `2 discontinued`, `1 coming_soon`
- same snapshot ID in the report and all tool responses
- no critical rejected rows

### 8.3 Representative tool checks

Run a one-off verification script from the repository root:

```bash
python - <<'PY'
from app.catalog.tools import get_product_details, list_categories, search_products

def ids(result):
    return {p["product_id"] for p in result["data"]["products"]}

u_default = search_products(category="Ukuleles")
u_available = search_products(category="Ukuleles", availability="available", limit=50)
u_any = search_products(category="Ukuleles", availability="any", limit=50)
empty = search_products(category="Instrumentos de Sopro (Madeiras)")
categories = list_categories()
by_name = {c["name"]: c for c in categories["data"]["categories"]}
p81 = get_product_details(81)
p96 = get_product_details(96)
p130 = get_product_details(130)
p136 = get_product_details(136)

assert u_default["meta"] == {
    "snapshot_id": u_default["meta"]["snapshot_id"],
    "returned": 10,
    "truncated": True,
}
assert u_available["meta"]["returned"] == 14
assert u_any["meta"]["returned"] == 15
assert 130 in ids(u_any)
assert empty["ok"] is True and empty["data"]["products"] == []
assert len(categories["data"]["categories"]) == 9
assert by_name["Ukuleles"]["product_count"] == 15
assert p81["data"]["product"]["price"]["amount_cents"] == 59990
assert p96["data"]["product"]["availability"] == "out_of_stock"
assert p130["data"]["product"]["availability"] == "coming_soon"
assert p136["data"]["product"]["availability"] == "discontinued"
assert all("stock_quantity" not in p["data"]["product"] for p in (p81, p96, p130, p136))
print("F-01 real-data checks passed")
PY
```

Also confirm:

- `list_categories` returns all 9 categories, including the three zero-product
  categories with `product_count = 0`.
- The zero-product category search succeeds with an empty list.
- The snapshot ID from the report equals each tool's `meta.snapshot_id`.
- The database has no out-of-scope tables or stock exposure.

### 8.4 Record evidence

Create `docs/verification/F-01-verification.md` with:

- date, branch, HEAD before verification
- exact commands
- Python/SQLite versions
- CSV sizes and catalog hashes before/after; presence and byte identity of all
  six versioned datasets
- import report summary
- tool output summary
- test command and result
- known limitations
- confirmation that all six original CSVs are byte-identical, and that no
  generated DB, `.env`, credentials, caches, or temporary artifacts are staged

All six source datasets are versioned. If a local working tree is missing them,
restore them from Git before real-data verification; do not substitute synthetic
fixtures for real-data evidence. Do not claim real-data verification without
execution evidence.

## 9. Reproducibility and public-evaluator strategy

### 9.1 Environment setup

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

`pyproject.toml` will declare:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "emporio-da-musica-agent"
version = "0.1.0"
description = "Deterministic catalog foundations for the Empório da Música agent"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8,<9"]

[tool.setuptools.packages.find]
include = ["app*", "scripts*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-ra"
```

Runtime dependencies remain empty. No `.env` file is required for F-01.

### 9.2 Offline test command

```bash
python -m pytest -q
```

The suite uses synthetic fixtures and `tmp_path` for isolated TDD; it does not
depend on the real datasets and makes no network calls. A clean checkout
contains all six original CSVs, so the real-data import can also be run after
the synthetic suite. Where available, also run with network disabled:

```bash
unshare -n python -m pytest -q
```

If `unshare` is unavailable, record that and rely on the absence of network
imports and services.

### 9.3 Public evaluator with versioned datasets

The project owner confirmed that all six supplied CSV datasets are fictional and
authorized their inclusion in the public GitHub repository without byte changes.
Therefore:

- A clean Git checkout contains all six original CSVs under `data/raw/`.
- A public evaluator can run the deterministic suite, which remains isolated
  through synthetic fixtures, and can also run the real-data import using the
  committed products and categories CSVs.
- The real-data build command is documented and runnable from the checkout.
- `docs/verification/F-01-verification.md` records the real-data run against the
  versioned datasets.
- F-01 still reads only the products and categories CSVs; the other four
  published datasets remain outside its scope.

Generated SQLite files are never required in the repository. The evaluator
builds them locally.

### 9.4 Clean-checkout requirements

1. Clone the repository.
2. Create a Python 3.11+ virtual environment.
3. Install `.[dev]`.
4. Run `python -m pytest -q`; the suite uses synthetic fixtures.
5. Run the import command using the committed products and categories CSVs.
6. Confirm all six original CSVs are byte-identical and no generated database is
   tracked.

## 10. Git, security, privacy, and commit boundaries

### 10.1 Never stage

- `.env`, tokens, credentials, or secrets
- modified copies of any of the six original CSVs; they must be versioned
  byte-identical
- `data/generated/` or any `*.sqlite`, `*.db`, `*.sqlite3`
- `.venv/`, caches, `__pycache__/`, logs, or temporary artifacts
- unrelated pre-existing modifications to `AGENTS.md` or the constitution

All six original CSVs are authorized for versioning. F-01 still reads only the
products and categories CSVs.

### 10.2 Proposed commit boundaries after Gate P

1. `docs(F-01): record Gate S approval` — spec approval record only.
2. `data(F-01): add supplied fictional CSV snapshots` — all six original CSVs,
   byte-identical.
3. `chore(F-01): add packaging and synthetic catalog fixtures` — `pyproject.toml`,
   package markers, fixtures, `conftest.py`, empty test skeleton.
4. `feat(F-01): validate and import catalog snapshot` — constants, errors,
   normalization, rules, validation, database, importer, build script, and their
   tests.
5. `feat(F-01): add read-only catalog tools` — tools, search/details/categories
   tests, security and reproducibility tests.
6. `docs(F-01): record verification evidence` — verification document and any
   test-only refinements.

Commits are proposed only. Dataset inclusion is owner-authorized, but no commit,
push, PR, tag, or other external publication action occurs without explicit
human authorization.

### 10.3 Security review

- Parameterized SQL only.
- `instr` for literal token matching; no user wildcard expansion.
- Read-only URI and `query_only` tested against writes.
- Sanitized error messages; no paths, SQL, traces, or dataset dumps.
- All six datasets may be published; F-01 still imports only products and
  categories and must never read the other four.
- No brand/model columns or extraction.
- No network calls.
- Source text treated as data, never instructions.
- Import report uses basenames and counts, not full rows.

### 10.4 Rollback

Because implementation is additive:

- Remove new `app/`, `scripts/`, and `tests/` files.
- Revert the `pyproject.toml` addition.
- Delete `data/generated/catalog.sqlite` if created.
- Versioned source CSVs are unchanged source assets; do not remove or modify
  them as part of a code rollback unless the owner reverses the publication
  decision.
- Revert the plan/spec documentation changes separately if the plan is rejected.

## 11. Verification checklist and stop conditions

### 11.1 Before implementation

- [x] Owner confirmed all six supplied CSVs are fictional and authorized their
  versioning/publication, byte-identical.
- [x] F-01 import scope remains products and categories only.
- [ ] Gate P approved by the human.
- [ ] Plan file list and contracts accepted.
- [ ] No unresolved spec conflict.

### 11.2 Implementation verification

```bash
python -m pytest -q
git diff --check
git status --porcelain
```

Additional checks:

- [ ] All AC-01 through AC-17 mapped to passing tests.
- [ ] Real-data import report matches 65 products, 9 categories, status counts.
- [ ] Ukuleles returns 10/14/15 as specified.
- [ ] Product 96 is `out_of_stock`; 130 is `coming_soon`; 136 is `discontinued`.
- [ ] `list_categories` reports 9 categories and `Ukuleles.product_count = 15`.
- [ ] A `599.9` source price becomes `59990` cents.
- [ ] All six original CSVs are byte-identical; catalog hashes match section 2.1.
- [ ] No generated database, modified source CSV, `.env`, credential, cache, or
  temporary artifact is staged.
- [ ] No out-of-scope feature or schema column exists.
- [ ] Verification evidence recorded under `docs/verification/`.

### 11.3 Stop conditions

Stop and request a decision if:

- A spec requirement is ambiguous or conflicts with observed source data.
- A new runtime dependency, schema change, or public-contract change is needed.
- F-01 would need to read or import an out-of-scope CSV.
- A test can only pass by weakening the spec or fabricating data.
- A modified source CSV or generated database would be staged.
- A commit, push, PR, or external action is requested without authorization.

Do not claim Gate V passed merely because tests pass; record actual commands and
outputs.

## 12. Risks, open decisions, and self-review

### 12.1 Resolved and open decisions for Gate P

Resolved by the project owner: all six supplied CSV datasets are fictional and
may be versioned and published byte-identical. F-01 still imports only products
and categories.

Open for Gate P:

1. **Validation-report failures:** failed imports publish no database and leave
   any existing database intact. This is the proposed fail-closed behavior.
2. **Search implementation:** `instr(search_text, ?)` is selected over `LIKE` to
   make `%`, `_`, and escape characters literal by construction.

### 12.2 Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Source CSV bytes modified during import or publication | Read-only import, hash checks, `git status` review |
| Out-of-scope datasets accidentally read or imported | Fixed filenames; only two inputs; no out-of-scope tables or imports |
| Synthetic tests accidentally depend on versioned datasets | Isolated fixtures and `tmp_path`; clean-checkout test run |
| CSV filenames contain spaces | Fixed basenames via `pathlib`; no shell interpolation in Python |
| UTF-8 BOM/CRLF data | `utf-8-sig`, `newline=""` |
| Price rounding errors | Regex guard plus `Decimal`; exact cents; over-precision fails |
| Status safety regression | Dedicated rules tests; default search only `available` |
| Stock leakage | Tool output assertions; no stock in details/search |
| SQL injection or wildcard behavior | Parameterized `instr`; literal token tests |
| Atomic import corruption | Temp database, integrity checks, `os.replace`, failed import preserves old DB |
| Scope creep | AC-17 review; no FTS/ORM/LLM/CLI/orders/promotions |
| Accidental generated DB staging | Existing `*.sqlite` and `data/generated/` ignores; status review |

### 12.3 Self-review

- **AC coverage:** all AC-01 through AC-17 have named tests and verification
  evidence.
- **Circular dependencies:** none; layers flow downward only.
- **Overengineering:** no ORM, FTS, vector layer, hierarchy, ambiguity resolver, or
  external service.
- **Dependencies:** runtime standard library only; `pytest` is the sole dev
  dependency.
- **Privacy:** all six datasets are owner-confirmed fictional and authorized for
  publication; only products/categories are read; stock is internal; generated
  databases and secrets are ignored.
- **Ambiguity:** output paths, source-row numbering, snapshot hashing, price
  regex, error mapping, test isolation, and publication strategy are explicit.
- **Contradictions:** no public contract changes; no customer CLI; the import
  script is engineering-only; F-01 imports only two of the six published CSVs.

## 13. Requested approval

Gate P approval is requested for this file-level plan, test strategy, dependency
set, risks, and scope. Approval authorizes implementation only. Dataset inclusion
is owner-authorized; this plan does not authorize commits, pushes, PRs, paid
services, or other external actions.

After approval, implementation starts with the first failing normalization and
rule tests, then proceeds through the sequence in section 7.
