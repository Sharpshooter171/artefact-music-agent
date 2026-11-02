# F-01 — Data Foundation & Catalog Tools

**Project:** Empório da Música AI Agent\
**Feature:** F-01 — Data Foundation & Catalog Tools\
**Document:** `docs/specs/F-01-data-foundation-catalog.md`\
**Version:** 0.3 — approved baseline for planning\
**Status:** APPROVED / GATE S PASSED\
**Date:** November 1, 2026\
**Prepared by:** Coding agent, for human review\
**Approved by:** Project owner (human), explicit instruction to proceed to PLAN\
**Approval date:** November 1, 2026\
**Approval scope:** F-01 planning only. Implementation, dependency installation, publication, commits, and external actions remain unauthorized until Gate P and later gates.\
**Approval:** GATE S APPROVED — planning authorized; implementation remains gated by Gate P.

---

## 1. Problem

The future agent (F-03) needs trustworthy, deterministic access to the store's
catalog before it can answer customer questions. The supplied catalog CSVs are
now available in `data/raw/`, but no application code or generated query layer
exists yet. Without a defined data foundation, later LLM responses could
fabricate prices, availability, descriptions, or technical specifications.

F-01 establishes:

1. A reproducible, validated local catalog built from the supplied product and
   category CSVs.
2. A read-only SQLite query layer over that catalog.
3. Stable, typed tool contracts for product search, product details, and
   category listing.
4. Conservative rules for price, stock, and product-status reporting.
5. Preservation of product descriptions and structured specifications.

F-01 is a data and deterministic-tool feature. It does not include the LLM,
prompting, tool selection, or the customer-facing CLI.

## 2. User story

> As the agent application, I need validated catalog data and deterministic
> read-only functions so that every catalog answer is grounded in the supplied
> records and unsupported or missing facts are reported honestly.

A secondary maintainer story:

> As the maintainer, I need the import to be reproducible from immutable source
> CSVs so that I can explain and verify every catalog fact.

## 3. CSV audit evidence

This revision is based on direct inspection of the supplied files on November 1,
2026. The facts below are observed, not inferred.

### 3.1 Files inspected

| File | Size | Records | Header |
| --- | ---: | ---: | --- |
| `data/raw/desafio_tecnico_ai_eng - categories.csv` | 756 bytes | 9 | `category_id,name,description` |
| `data/raw/desafio_tecnico_ai_eng - products.csv` | 22,399 bytes | 65 | `product_id,price_brl,name,category_id,description,stock_quantity,status,specs,created_at` |

Both files are UTF-8 without a BOM, use a comma delimiter, and use CRLF line
endings.

Additional files are present in `data/raw/`: `customers.csv`, `orders.csv`,
`order_items.csv`, and `promotions.csv`. They are outside F-01 scope. Their
contents were not read during this audit and must not be imported by F-01.

### 3.2 Categories

- 9 records with category IDs `1` through `9`.
- Category IDs are unique, numeric, and have no gaps.
- Category names are unique both exactly and after normalization.
- Every category has a non-blank description.
- The structure is flat: there is no parent, hierarchy, or nested-category
  column.
- Categories with products:

| ID | Name | Product count |
| ---: | --- | ---: |
| 1 | Guitarras | 5 |
| 2 | Baixos | 4 |
| 3 | Baterias e Percussão | 3 |
| 4 | Teclados e Pianos | 3 |
| 5 | Violões | 35 |
| 9 | Ukuleles | 15 |

- Categories `6` (Instrumentos de Sopro (Madeiras)), `7` (Instrumentos de Sopro
  (Metais)), and `8` (Cordas Orquestrais) currently have zero products. This is
  valid data and must be preserved, not treated as an import failure.

### 3.3 Products

- 65 records with product IDs `81` through `145`.
- Product IDs are unique, numeric, sequential, and have no gaps.
- Product names are unique both exactly and after normalization.
- All 65 rows have non-blank name, description, specs, status, price, stock, and
  category.
- No orphan category references exist.
- No duplicate product IDs or names were observed.
- Every product belongs to one of the six populated categories.
- Brand and model are **not** separate columns. Brand-like and model-like tokens
  appear only inside the free-text `name` (for example, "Yamaha C40 Nylon
  Natural"). F-01 must not attempt speculative brand/model extraction.
- The `description` field is non-blank, 109–148 characters per row, in Brazilian
  Portuguese.
- The `specs` field is non-blank and is valid JSON in every row. Each value is a
  JSON object whose values are strings. There are no nested objects or arrays.
- Spec keys vary by category. Observed keys include `top`, `back_sides`, `neck`,
  `strings`, `scale`, `electronics`, `color`, `body`, `shells`, `pieces`,
  `hardware`, `keys`, `type`, and `polyphony`.
- `created_at` is non-blank in every row, with 55 distinct dates from
  `2020-02-28` to `2025-05-15`. F-01 does not use this field and does not need to
  import it.
- Category names do not appear in any of the 65 product names. Category-based
  search therefore must filter through `category_id`, not through product-name
  text.

### 3.4 Price, stock, and status observations

- `price_brl` is an unquoted decimal string in Brazilian reais, with no currency
  symbol.
- 53 prices have no decimal part (for example, `849`); 12 have one decimal place
  (for example, `599.9`). No price has more than two decimal places.
- Prices range from `159.9` to `19567`. All are non-negative and convert exactly
  to integer cents without rounding.
- `stock_quantity` contains only non-negative integers from `0` to `15`. No
  blank, negative, or non-integer values were observed.
- `status` contains exactly three observed values:

| Status | Count | Stock observations |
| --- | ---: | --- |
| `active` | 62 | 61 with stock > 0; 1 with stock = 0 |
| `discontinued` | 2 | 1 with stock = 0; 1 with stock = 13 |
| `coming_soon` | 1 | 1 with stock = 2 |

Important observed edge cases:

- Product `130` is `coming_soon` with `stock_quantity = 2`. It must never be
  reported as available.
- Product `136` is `discontinued` with `stock_quantity = 13`. It must never be
  reported as available.
- Product `96` is `active` with `stock_quantity = 0`. It must be reported as out
  of stock.

### 3.5 Observed facts vs. remaining assumptions

| Item | Status |
| --- | --- |
| File names, headers, encoding, delimiter, row counts | Observed |
| Product/category identifiers and relations | Observed |
| Price representation and exact cent conversion | Observed |
| Status vocabulary (`active`, `discontinued`, `coming_soon`) | Observed |
| Stock representation and edge cases | Observed |
| Description and specs presence/shape | Observed |
| Flat category structure and zero-product categories | Observed |
| Category names absent from product names | Observed |
| Currency is BRL | Inferred from the `price_brl` column name and values |
| CSV data is a static snapshot, not live inventory | Constitution rule and observed local files |
| Status vocabulary is exhaustive for the supplied snapshot | Assumption; unexpected values fail import |
| Product/category IDs are stable across regenerations | Assumption for the supplied snapshot |
| `created_at` is not needed for F-01 | Decision; field may be ignored during import |
| Exact stock counts should not be exposed to customers | Conservative product decision; tools expose availability only |

## 4. Scope

### 4.1 In scope

- Read-only inspection, validation, and import of the supplied product and
  category CSV files.
- A canonical catalog model for products and categories.
- A local SQLite database generated reproducibly from those two CSVs.
- Deterministic normalization of searchable text.
- Deterministic, parameterized, read-only catalog queries.
- Typed Python tool contracts for:
  - product search;
  - product details by identifier;
  - category listing.
- Preservation of product descriptions and structured `specs` data.
- Price, stock, and status rules that prevent false availability claims.
- Import/validation diagnostics with explicit failure behavior.
- Unit and integration tests using synthetic fixtures, without network access.
- Documentation of source assumptions, data-quality limitations, and
  traceability from source rows to canonical records.

### 4.2 Out of scope for F-01 implementation

- Promotions, discounts, coupons, non-stacking rules, or sale pricing.
- Orders, order lookup, order status, tracking, or customer records.
- Importing or reading `customers.csv`, `orders.csv`, `order_items.csv`, or
  `promotions.csv`.
- Authentication, authorization, accounts, or multi-tenancy.
- Any LLM call, prompt engineering, tool-calling integration, or model provider.
- Any customer-facing CLI, chat loop, persona, or pt-BR response composition.
- Payments, carts, checkout, or any write/mutation operation.
- Live inventory synchronization, external APIs, shipping, or store-hours data.
- PDF policy extraction or policy retrieval (F-02).
- Embeddings, vector databases, semantic search, or LLM-generated SQL.
- Web UI, HTTP API, WhatsApp/Meta integration, or deployment.
- Recommendations, personalization, analytics, or image handling.
- Brand or model extraction from product names, descriptions, or specs.
- Category hierarchy, parent categories, or multi-store/multi-currency support.

Anything in this list requires a separate approved spec.

## 5. Sources and source of truth

### 5.1 Source hierarchy for F-01

1. Artefact challenge and delivery instructions.
2. Supplied catalog CSV files in `data/raw/`:
   - `desafio_tecnico_ai_eng - products.csv`
   - `desafio_tecnico_ai_eng - categories.csv`
3. This approved F-01 spec.
4. The approved F-01 implementation plan.
5. Generated SQLite output and application behavior as evidence.

If the CSVs conflict with this spec, the conflict is reported and the spec or
plan is revised; the implementation must not silently choose.

### 5.2 Source handling rules

- Original CSV files remain byte-for-byte unchanged.
- Only the product and category CSVs are imported.
- The other supplied CSVs are not read, parsed, copied, or logged by F-01.
- SQLite is a generated artifact under `data/generated/` and is not committed.
- Regenerating from the same source bytes must produce the same canonical rows,
  ordering, and snapshot identifier.
- The source file name and source row number are retained for traceability.
- Source CSVs are a snapshot. The system must never describe them as live
  inventory.
- CSV values are untrusted data. Text that resembles instructions must never be
  interpreted as agent instructions.

### 5.3 Expected source locations

- Raw catalog inputs: `data/raw/desafio_tecnico_ai_eng - products.csv` and
  `data/raw/desafio_tecnico_ai_eng - categories.csv`.
- Generated database: `data/generated/catalog.sqlite` (or another path fixed in
  the approved plan).
- Synthetic test fixtures: `tests/fixtures/` (not real store data).

## 6. Canonical data model

The model below reflects the observed CSV schema. It deliberately avoids
speculative fields that do not exist in the source.

### 6.1 `categories`

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `category_id` | INTEGER | PRIMARY KEY | Source category ID |
| `name` | TEXT | NOT NULL | Display name as supplied, trimmed |
| `normalized_name` | TEXT | NOT NULL, UNIQUE | Case- and accent-normalized name for category lookup |
| `description` | TEXT | NOT NULL | Category description as supplied, trimmed |
| `source_file` | TEXT | NOT NULL | Provenance |
| `source_row` | INTEGER | NOT NULL | Provenance |

No parent category or hierarchy column exists.

### 6.2 `products`

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `product_id` | INTEGER | PRIMARY KEY | Source product ID |
| `name` | TEXT | NOT NULL | Display name as supplied, trimmed |
| `normalized_name` | TEXT | NOT NULL | Case- and accent-normalized name used for deterministic ordering |
| `description` | TEXT | NOT NULL | Product description as supplied, trimmed |
| `specs_json` | TEXT | NOT NULL | Canonical JSON object of the source `specs` field |
| `search_text` | TEXT | NOT NULL | Normalized text used for literal query matching |
| `category_id` | INTEGER | NOT NULL, FK to `categories` | Source category relation |
| `price_cents` | INTEGER | NOT NULL, `>= 0` | Exact BRL price in cents |
| `stock_quantity` | INTEGER | NOT NULL, `>= 0` | Recorded snapshot quantity, internal |
| `status` | TEXT | NOT NULL, enum `active`, `discontinued`, `coming_soon` | Source status |
| `availability` | TEXT | NOT NULL, enum below | Derived customer-facing availability |
| `source_file` | TEXT | NOT NULL | Provenance |
| `source_row` | INTEGER | NOT NULL | Provenance |

Allowed `availability` values:

- `available` — `status = active` and `stock_quantity > 0`.
- `out_of_stock` — `status = active` and `stock_quantity = 0`.
- `coming_soon` — `status = coming_soon`, regardless of stock.
- `discontinued` — `status = discontinued`, regardless of stock.

There is no `unknown` availability state for a successful import. Unexpected
status or stock values fail validation instead of producing ambiguous catalog
rows.

### 6.3 `search_text`

`search_text` is a deterministic normalized concatenation of:

1. the category name;
2. the product name;
3. the product description;
4. every string value in the product's `specs` object.

This preserves searchability of descriptions and technical specifications
without extracting brand or model fields. Category names are included so that
text queries such as "ukulele" can match products whose names omit the category
word. The `category` filter remains independent and uses `category_id`.

### 6.4 `catalog_meta`

A small key/value table containing at least:

- `schema_version`;
- `snapshot_id` — a deterministic hash derived from the sorted source file names
  and SHA-256 content hashes.

### 6.5 Fields intentionally not imported

- `created_at` from products: no F-01 contract uses it.
- Any column from `customers.csv`, `orders.csv`, `order_items.csv`, or
  `promotions.csv`.

### 6.6 Indexes

At minimum, indexes on:

- `products.category_id`;
- `products.normalized_name`;
- `products.availability`;
- `products.price_cents`.

Search may use parameterized `instr(search_text, ?)` or `LIKE` with `%`, `_`,
and the escape character escaped. Query tokens are always literal text;
wildcard characters in user input must never act as wildcards. FTS is not
required and is not approved by this spec.

## 7. Tool contracts

F-01 exposes ordinary typed Python functions. They are deterministic, read-only,
and JSON-serializable at their boundaries so that F-03 can later adapt them to
LLM tool schemas. F-01 does not call an LLM.

All functions:

- accept validated typed arguments;
- use parameterized SQLite queries only;
- never accept raw SQL from a caller;
- open the database in read-only mode;
- return a result envelope rather than leaking raw exceptions;
- never return secrets, file-system paths, customer data, or full table dumps.

### 7.1 Result envelope

Success:

```json
{
  "ok": true,
  "data": {},
  "meta": {
    "snapshot_id": "deterministic-hash",
    "returned": 0,
    "truncated": false
  }
}
```

Failure:

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "Sanitized engineering message",
    "details": {}
  },
  "meta": {
    "snapshot_id": "deterministic-hash-or-null"
  }
}
```

`error.message` is diagnostic, not customer copy. F-03 maps error codes to safe
pt-BR customer messages. No internal stack trace, SQL text, or local path may
appear in `message`.

### 7.2 `search_products`

Purpose: find products matching a customer's descriptive query and optional
filters.

Input:

| Parameter | Type | Rules |
| --- | --- | --- |
| `query` | `str \| None` | Trimmed; 2–120 characters when present; treated as literal text |
| `category` | `str \| None` | Canonical category name; matched case- and accent-insensitively; 1–80 characters |
| `price_min_cents` | `int \| None` | `>= 0` |
| `price_max_cents` | `int \| None` | `>= price_min_cents` when both are present |
| `availability` | `str` | One of `available`, `out_of_stock`, `coming_soon`, `discontinued`, `any`; default `available` |
| `limit` | `int` | Default `10`; minimum `1`; maximum `50` |

At least one of `query`, `category`, `price_min_cents`, or `price_max_cents`
must be present. An unfiltered catalog dump is rejected with
`INVALID_ARGUMENT`.

Matching rules:

- Text normalization: Unicode NFKD, removal of combining marks, `casefold()`,
  and collapsed whitespace.
- `query` is tokenized on whitespace. Every token must occur in the product's
  `search_text`. This is literal substring matching, not semantic matching.
- Search tokens are literal. If `LIKE` is used, `%`, `_`, and the escape
  character must be escaped; parameterized `instr(search_text, ?)` is preferred.
- `query` can match name, description, category name, or spec values because
  those are part of `search_text`.
- `category` resolves against `categories.normalized_name`. A matching category
  filters products by `category_id`, independent of whether the category word
  appears in product names.
- A category that exists but has zero products returns a successful empty
  result. A category that does not exist returns `CATEGORY_NOT_FOUND`.
- Category names are unique after normalization; duplicate normalized names are
  an import failure, so no ambiguity resolution is needed.
- Price bounds are inclusive.
- `availability = "any"` includes all four availability values.
- Default search returns only `available` products. `coming_soon`,
  `discontinued`, and `out_of_stock` products are excluded unless explicitly
  requested.
- Ordering is deterministic: `products.normalized_name ASC`, then `product_id
  ASC`.
- `limit` truncates the ordered result. `meta.truncated` is `true` when more
  matching rows exist than were returned.

Output `data`:

```json
{
  "products": [
    {
      "product_id": 81,
      "name": "Yamaha C40 Nylon Natural",
      "category": {"id": 5, "name": "Violões"},
      "price": {"amount_cents": 59990, "currency": "BRL"},
      "availability": "available"
    }
  ]
}
```

`stock_quantity` is internal and is not exposed by any F-01 tool. `description`
and `specs` are not part of the default search output but are exposed through
`get_product_details`.

### 7.3 `get_product_details`

Purpose: return grounded details and verified technical information for one
known catalog item.

Input:

| Parameter | Type | Rules |
| --- | --- | --- |
| `product_id` | `int` | Positive integer; exact match |

Output `data`:

```json
{
  "product": {
    "product_id": 81,
    "name": "Yamaha C40 Nylon Natural",
    "category": {"id": 5, "name": "Violões"},
    "description": "Violão clássico com tampo em Spruce e fundo/laterais em Meranti. Ideal para estudantes e iniciantes, com excelente projeção sonora.",
    "specs": {
      "top": "Spruce",
      "back_sides": "Meranti",
      "neck": "Nato",
      "strings": "nylon",
      "scale": "650mm",
      "electronics": "no",
      "color": "Natural"
    },
    "price": {"amount_cents": 59990, "currency": "BRL"},
    "availability": "available"
  }
}
```

`description` and `specs` are returned from the validated source record. F-01
does not summarize, translate, flatten, or infer additional specifications from
them. `stock_quantity` is internal and is not returned by this tool. A missing
identifier returns `PRODUCT_NOT_FOUND`. The function never returns a "nearby" or
guessed product.

### 7.4 `list_categories`

Purpose: support category discovery and resolve customer category names.

Input: none.

Output `data`:

```json
{
  "categories": [
    {
      "category_id": 1,
      "name": "Guitarras",
      "description": "Guitarras elétricas de todos os estilos, do rock ao jazz",
      "product_count": 5
    }
  ]
}
```

- All 9 categories are returned, including categories with zero products.
- `product_count` counts every catalog product in the category, regardless of
  availability (`available`, `out_of_stock`, `coming_soon`, or `discontinued`).
- The structure is flat. No parent field is returned.
- Ordering is deterministic by normalized name and then category ID.
- The category list is small and is not a product dump.

### 7.5 Error codes

- `INVALID_ARGUMENT` — invalid type, length, range, or filter combination.
- `CATEGORY_NOT_FOUND` — no category matches the requested normalized name.
- `PRODUCT_NOT_FOUND` — no product matches the requested identifier.
- `CATALOG_UNAVAILABLE` — generated database is missing, unreadable, corrupt,
  or has an unsupported schema version.
- `INTERNAL_ERROR` — unexpected failure; sanitized, with no sensitive detail.

An empty search result is a successful response with `products: []`, not an
error. This includes searches in categories with zero products.

## 8. Price, stock, and status rules

### 8.1 Price

- Parse `price_brl` into `Decimal`; never use binary floating point for monetary
  values.
- Accept the observed forms with zero, one, or two decimal places, such as
  `849`, `599.9`, and `199.99`.
- Store exact integer cents. Examples: `599.9` becomes `59990`; `849` becomes
  `84900`.
- Reject values with more than two significant decimal places instead of
  silently rounding.
- Reject blank, negative, non-numeric, or currency-symbol-bearing values.
- All prices are BRL. The tool contract returns `currency: "BRL"` as a constant;
  no currency column is stored.
- F-01 does not apply promotions, discounts, installments, or interest. It
  returns the recorded catalog price only, even though a separate
  `promotions.csv` exists in the supplied data.
- Price ranges are evaluated on `price_cents`.

### 8.2 Stock and status

Status mapping is deterministic:

| Source status | Stock | Derived availability |
| --- | --- | --- |
| `active` | `> 0` | `available` |
| `active` | `0` | `out_of_stock` |
| `coming_soon` | any | `coming_soon` |
| `discontinued` | any | `discontinued` |

Rules:

- `coming_soon` is never advertised as available, even when
  `stock_quantity > 0`.
- `discontinued` is never advertised as available, even when
  `stock_quantity > 0`.
- Stock quantity does not override status.
- Missing, negative, or non-integer stock is a validation error.
- Missing or unrecognized status is a validation error; the import fails closed.
- Exact stock quantity is internal by default. Customer-facing output reports
  the normalized availability. Exposing exact counts requires a later decision.
- F-01 has no restock date or estimated arrival field. It must not invent one.

### 8.3 Snapshot honesty

Every tool response includes a `snapshot_id`. F-03 must be able to tell the
customer that availability reflects the provided catalog snapshot, not a live
inventory system. F-01 does not compose that sentence itself.

## 9. Import and validation

### 9.1 Import flow

1. Read only the two catalog CSV files from `data/raw/` without modifying them.
2. Compute each file's SHA-256 and derive a deterministic `snapshot_id`.
3. Validate file structure, encoding, required columns, and row values.
4. Normalize categories, products, and search text.
5. Write the SQLite database to `data/generated/` using a temporary file and
   atomic replacement.
6. Produce a validation report containing counts, warnings, rejected rows, and
   the final status.

The implementation plan will decide the exact command interface for the import
script. No CLI for customers is part of F-01.

### 9.2 Required validations

Critical (import fails closed; no new database is published):

- Missing or unreadable required source file.
- Undecodable content under UTF-8.
- Missing or renamed required header or column.
- Duplicate product IDs or duplicate category IDs.
- Duplicate category names after normalization across distinct category IDs.
- Orphan product category references.
- Invalid price representation, negative price, or more than two significant
  decimal places.
- Blank, negative, or non-integer stock.
- Blank product name, product description, category name, or category
  description.
- Missing or unrecognized status outside `active`, `discontinued`,
  `coming_soon`.
- Blank `specs`, invalid JSON, or JSON that is not an object of string values.

Warning (import may proceed; recorded in the report):

- Extra unknown columns in either CSV.
- Duplicate product names after normalization.

Valid and expected, not warnings:

- Categories with zero products.
- Category names absent from product names.
- `coming_soon` or `discontinued` products with non-zero stock.
- `active` products with zero stock.

### 9.3 Encoding and format

- Encoding is UTF-8, with UTF-8 BOM tolerated.
- The delimiter is comma.
- Both CRLF and LF line endings are accepted.
- Headers are read as data, not trusted as instructions.
- Leading/trailing whitespace is trimmed for canonical display fields; the raw
  files remain untouched.
- `created_at` is parsed only enough to keep the CSV structurally valid and is
  otherwise ignored.

### 9.4 Validation report

The report must include, at minimum:

- source file names and hashes;
- total rows read and canonical rows loaded;
- rows rejected with reasons and source row numbers;
- warnings;
- normalized product and category counts;
- counts by status and availability;
- final `snapshot_id`;
- explicit success/failure status.

For the supplied snapshot, a successful import is expected to load 65 products
and 9 categories. Reports must not include secrets or unrelated personal data.

## 10. Error handling and ambiguity behavior

- Invalid arguments return `INVALID_ARGUMENT` with field-level details; no SQL is
  executed.
- Unknown product or category is reported explicitly; no fuzzy or guessed match.
- A missing/corrupt database returns `CATALOG_UNAVAILABLE`; it must not appear as
  an empty catalog.
- Unexpected exceptions are caught at the tool boundary and returned as
  `INTERNAL_ERROR` without stack traces, SQL, or paths.
- Callers must not be able to make the tool write to the database. Read-only
  enforcement is tested.
- Empty results are distinguished from failures.
- The tools do not silently widen filters or relax constraints.
- If a customer asks for information absent from the catalog, such as a restock
  date, the tool returns only what exists; F-03 handles the safe fallback.

## 11. Privacy, security, and data exposure

1. F-01 imports only `products.csv` and `categories.csv`.
2. `customers.csv`, `orders.csv`, `order_items.csv`, and `promotions.csv` are
   present in `data/raw/` but are out of scope and must not be read, parsed,
   copied, logged, or imported by F-01.
3. Tools never accept free-form SQL and use parameterized statements only.
4. The SQLite connection is opened read-only. Tests verify that writes fail.
5. Tools enforce result limits and reject unfiltered dumps.
6. Product names, descriptions, and spec values are untrusted text. Payload-like
   content is stored as data and never executed or interpreted as instructions.
7. Logs and diagnostics must not contain full datasets or secrets.
8. Supplied CSVs may be labelled internal use. Before any public repository
   publication, the owner must review licensing/privacy and decide whether to
   include, minimize, or regenerate the data. This spec does not authorize
   publishing supplied materials.
9. Generated databases are ignored by Git via the existing `*.sqlite` rules.
10. No network access occurs during import, query, or tests.

## 12. Assumptions and dependencies

### 12.1 Observed and resolved

- The two catalog files and their schemas are as described in section 3.
- Product IDs are integers and unique; category IDs are integers and unique.
- Categories are flat and unique by normalized name.
- Status values are exactly `active`, `discontinued`, and `coming_soon`.
- Prices are BRL decimal strings with at most two decimal places.
- Stock is a non-negative integer snapshot.
- Product descriptions are non-blank.
- Specs are JSON objects with string values.
- Category names are absent from all product names, so category search must use
  `category_id`.
- Three categories currently have zero products.
- `created_at` exists but is not needed for F-01.

### 12.2 Remaining assumptions

- The supplied files are a static snapshot and will not change during an
  implementation run.
- The observed status vocabulary is exhaustive for this snapshot; unexpected
  values fail closed.
- Exact stock quantity is not exposed to customers in F-01.
- No F-01 contract needs `created_at` or any field from the other supplied CSVs.
- Python 3.11+ standard library is sufficient for runtime (`csv`, `sqlite3`,
  `decimal`, `unicodedata`, `hashlib`, `json`, `pathlib`).
- `pytest` is the only test dependency and will be declared in the approved
  plan.

### 12.3 Dependencies

- Constitution V1.0 (approved).
- Supplied catalog CSVs (present and inspected).
- Human approval of this spec at Gate S.
- Human approval of the file-level implementation plan at Gate P.
- No external service, model provider, or paid dependency.

## 13. Acceptance criteria

Each criterion is testable offline with synthetic fixtures that use the observed
schema.

- **AC-01 — Source integrity.** When the import runs, the original CSV files
  remain byte-for-byte unchanged. Only products and categories are imported. The
  generated database is created under `data/generated/` and is not committed.
- **AC-02 — Reproducibility.** Given identical source bytes, two independent
  imports produce identical canonical rows, ordering, counts, and `snapshot_id`.
- **AC-03 — Structural validation.** Given a fixture with a missing required
  header, duplicate identifiers, duplicate normalized category names across
  distinct IDs, an orphan category, or an invalid status, the import fails
  closed, publishes no new database, and reports the specific errors.
- **AC-04 — Canonical loading.** Given a valid fixture, all products and
  categories load with the documented fields, provenance (`source_file`,
  `source_row`), category relationships, descriptions, and specs.
- **AC-05 — Search normalization.** Given products and categories differing by
  case, accents, and extra whitespace, searches match them deterministically
  using the specified normalization. Multi-word queries require every token to
  match.
- **AC-06 — Category search independence.** Given a category whose name does not
  appear in any product name, `search_products(category=...)` returns that
  category's products by joining on `category_id`. For the supplied `Ukuleles`
  category: the default call (availability `available`, limit 10) returns 10
  products with `meta.truncated = true`; `availability="available", limit=50`
  returns 14 products; and `availability="any", limit=50` returns all 15
  products, including product 130. A category with zero products returns a
  successful empty result. An unknown category returns `CATEGORY_NOT_FOUND`.
- **AC-07 — Search filters and limits.** Given a valid fixture,
  `search_products` applies category, inclusive price range, availability, and
  limit filters correctly, with stable ordering by `products.normalized_name`
  and `product_id`. Results are capped at 50 and `meta.truncated` is correct. A
  call with no discriminating filter is rejected with `INVALID_ARGUMENT`.
- **AC-08 — Product details and specs.** Given an existing product ID,
  `get_product_details` returns the source description and the `specs` object
  without flattening or inventing fields, and does not expose `stock_quantity`.
  Given an unknown ID, it returns `PRODUCT_NOT_FOUND`.
- **AC-09 — Status safety.** `active` with stock > 0 is `available`; `active`
  with stock 0 is `out_of_stock`; `coming_soon` and `discontinued` are never
  `available`, even with stock > 0. Default search returns only available
  products.
- **AC-10 — Price integrity.** Prices are parsed with `Decimal`, stored as exact
  integer cents, and returned with `currency: "BRL"`. Values with more than two
  significant decimal places, blank values, or invalid text cause import failure
  rather than rounding.
- **AC-11 — Description/spec search.** Text queries can match verified product
  descriptions and spec values through `search_text`, without extracting brand
  or model fields.
- **AC-12 — Category contract.** `list_categories` returns all 9 categories in
  deterministic order, including zero-product categories, with descriptions and
  product counts. `product_count` counts all catalog products regardless of
  availability; `Ukuleles` reports 15. No parent/hierarchy field is returned.
- **AC-13 — Snapshot metadata.** Every successful tool response includes the
  same `snapshot_id` that the import report recorded for that database.
- **AC-14 — Error envelope.** Invalid arguments, missing database, and unknown
  identifiers produce the documented error codes with sanitized messages and no
  SQL, paths, or stack traces.
- **AC-15 — Read-only and literal search.** Tests verify that the tool connection
  cannot write, that SQL-injection-like query strings are literal data, and that
  `%`, `_`, and the escape character in search tokens are treated literally (or
  escaped when `LIKE` is used).
- **AC-16 — Offline deterministic tests.** The F-01 test suite runs with
  `pytest` without network access and does not require the real CSVs.
- **AC-17 — Scope and non-extraction boundary.** F-01 exposes no LLM call, CLI,
  promotion logic, order/customer data, authentication, payment, or mutation
  operation. It contains no brand/model columns, filters, or extraction logic.

## 14. Test strategy (TDD)

### 14.1 Approach

Use red → green → refactor per acceptance criterion.

1. **RED:** Add a focused failing test that expresses the AC using a synthetic
   fixture or a directly constructed canonical record.
2. **GREEN:** Implement the minimum importer, validator, query, or contract code
   needed to pass.
3. **REFACTOR:** Remove duplication and improve clarity while keeping all tests
   green.

No application code and no executable tests are written under this spec until
Gate P approves the plan.

### 14.2 Test layers

- **Unit tests:**
  - text normalization;
  - price parsing and cent conversion;
  - status-to-availability mapping, including `coming_soon` and `discontinued`
    with non-zero stock;
  - description/spec search-text construction;
  - product `normalized_name` construction and ordering;
  - argument validation;
  - deterministic ordering and truncation.
- **Integration tests:**
  - import synthetic CSV fixtures with the observed headers into a temporary
    SQLite database;
  - run each tool against the generated database;
  - assert envelopes, provenance, snapshot ID, descriptions, specs, and AC
    behavior.
- **Failure/security tests:**
  - malformed headers;
  - duplicate IDs;
  - duplicate normalized category names;
  - orphan categories;
  - invalid status;
  - invalid price/stock/specs JSON;
  - missing database;
  - write-attempt rejection;
  - SQL-injection-like literals;
  - literal `%`, `_`, and escape-character search tokens;
  - unfiltered dump rejection.
- **Determinism tests:**
  - two imports of the same fixture produce identical canonical output.

### 14.3 Fixtures

- Fixtures are small, synthetic, and contain no real customer or supplier data.
- They use the observed headers:
  - `category_id,name,description`
  - `product_id,price_brl,name,category_id,description,stock_quantity,status,specs,created_at`
- Required fixture families:
  - valid catalog with descriptions and string-valued specs;
  - category names absent from product names;
  - a category with zero products;
  - `coming_soon` with stock > 0;
  - `discontinued` with stock > 0 and with stock 0;
  - `active` with stock 0;
  - one- and zero-decimal prices;
  - malformed headers, statuses, prices, stock, and specs;
  - duplicate identifiers and category names;
  - accent/case/whitespace variants;
  - SQL-injection-like text;
  - literal `%`, `_`, and escape-character text.
- Tests use `tmp_path` for databases and never touch `data/generated/`.

### 14.4 Real-data verification (after Gate P implementation)

- Run the import once against the supplied CSVs and record the validation report.
- Confirm 65 products, 9 categories, and status counts `62 active`, `2
  discontinued`, `1 coming_soon`.
- Confirm the three observed edge cases: product `130` is `coming_soon`, product
  `136` is `discontinued`, and product `96` is `out_of_stock`.
- Execute representative category queries: `Ukuleles` default (availability
  `available`, limit 10) returns 10 with `truncated=true`;
  `availability="available", limit=50` returns 14; `availability="any",
  limit=50` returns 15 including product 130; a zero-product category returns a
  successful empty result.
- Confirm `list_categories` reports `Ukuleles.product_count = 15` regardless of
  availability.
- Verify a sample price such as `599.9` becomes `59990` cents.
- Record results under `docs/verification/`.
- Real-data smoke checks supplement, not replace, deterministic tests.

### 14.5 Explicit non-tests for F-01

- No LLM or network tests.
- No customer conversation transcripts (F-03/F-04).
- No policy retrieval tests (F-02).
- No customer/order/promotion tests.
- No performance/load testing unless a concrete problem appears.

## 15. Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Status semantics are ignored | Coming-soon or discontinued stock advertised as available | Explicit mapping; default search only `available`; AC-09 |
| Category word absent from product names | Category searches return nothing | Resolve category by name to `category_id`; include category name in search text; AC-06 |
| Specs are flattened or dropped | Loss of verified technical details | Store canonical `specs_json`; return structured object; AC-08 |
| Brand/model extraction is speculative | Fabricated attributes | No brand/model columns or filters; AC-17 |
| Price format quirks | Wrong prices | Decimal parsing, exact cents, reject over-precision; AC-10 |
| Zero-product categories treated as errors | Incorrect import failure | Preserve as valid data; list with count 0; AC-12 |
| Other supplied CSVs contain PII | Privacy exposure | Import only products and categories; AC-01/AC-17 |
| Internal-use CSV data in public repo | Privacy/licensing issue | Owner packaging review before publication; minimize data if needed |
| Scope creep toward promotions or orders | Rework and privacy risk | Explicit out-of-scope list and AC-17 |
| Overengineering | Delay | No hierarchy, no ambiguity resolver, no FTS/ORM/vector layer |

## 16. Definition of done for F-01 (after later gates)

- Approved spec (Gate S) and approved plan (Gate P).
- Import and tools implemented within the approved file list.
- All AC-01 through AC-17 covered by passing offline tests.
- Validation report for synthetic fixtures and, once implemented, real CSVs.
- `git diff --check` clean; no secrets or generated databases committed.
- Verification evidence recorded under `docs/verification/`.
- No scope items from section 4.2 present.

## 17. Approval record

**Status:** APPROVED / GATE S PASSED.

- **Approved baseline:** F-01 v0.3.
- **Gate S:** APPROVED on November 1, 2026.
- **Human authorization:** The project owner explicitly authorized moving from
  the reviewed F-01 v0.3 specification to PLAN, received November 1, 2026.
- **Scope of authorization:** Planning only. This approval authorizes preparation
  of the F-01 implementation plan. It does not authorize application code,
  executable tests, dependency installation, data publication, commits, pushes,
  PRs, or external actions.

The human approval covers:

- [x] The scope and out-of-scope boundaries.
- [x] The observed CSV facts and the remaining assumptions.
- [x] The canonical data model without brand/model fields.
- [x] The tool contracts and status rules, especially `coming_soon`.
- [x] The acceptance criteria AC-01 through AC-17.
- [x] The next step is a Gate P implementation plan, not code.
