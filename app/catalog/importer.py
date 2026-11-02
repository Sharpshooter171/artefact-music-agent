from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from app.catalog.constants import (
    AVAILABILITIES,
    CATEGORIES_SOURCE,
    PRODUCTS_SOURCE,
    VALID_STATUSES,
)
from app.catalog.database import create_catalog_db
from app.catalog.validation import PreparedCatalog, validate_catalog


def build_catalog(data_dir: str | Path, output: str | Path) -> dict:
    data_dir = Path(data_dir)
    output = Path(output)
    report = _base_report()

    texts: dict[str, str] = {}
    hashes: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for source_name in (CATEGORIES_SOURCE, PRODUCTS_SOURCE):
        path = data_dir / source_name
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            report["rows_rejected"].append(
                _issue("MISSING_FILE", source_name, "Arquivo de origem ausente.")
            )
            continue
        except OSError:
            report["rows_rejected"].append(
                _issue("SOURCE_READ_ERROR", source_name, "Falha ao ler arquivo de origem.")
            )
            continue

        hashes[source_name] = hashlib.sha256(raw).hexdigest()
        sizes[source_name] = len(raw)
        try:
            texts[source_name] = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            report["source_files"].append(
                {
                    "name": source_name,
                    "size_bytes": sizes[source_name],
                    "sha256": hashes[source_name],
                    "rows_read": 0,
                }
            )
            report["rows_rejected"].append(
                _issue("DECODE_ERROR", source_name, "Arquivo de origem inválido.")
            )

    if report["rows_rejected"]:
        return report

    prepared = validate_catalog(
        texts[CATEGORIES_SOURCE],
        texts[PRODUCTS_SOURCE],
        source_hashes=hashes,
        source_sizes=sizes,
    )
    report = prepared.report
    if report["status"] != "ok":
        return report

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temp_name = tempfile.mkstemp(
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
        )
        temp_path = Path(temp_name)
    except OSError:
        return _failed_report(
            prepared,
            "OUTPUT_ERROR",
            output.name,
            "Falha ao preparar o catálogo.",
        )

    try:
        os.close(file_descriptor)
        create_catalog_db(temp_path, prepared)
        os.replace(temp_path, output)
    except Exception:
        temp_path.unlink(missing_ok=True)
        return _failed_report(
            prepared,
            "OUTPUT_ERROR",
            output.name,
            "Falha ao gerar o catálogo.",
        )

    return report


def _failed_report(
    prepared: PreparedCatalog,
    code: str,
    source_name: str,
    message: str,
) -> dict:
    report = dict(prepared.report)
    report["status"] = "failed"
    report["snapshot_id"] = None
    report["canonical_rows_loaded"] = 0
    report["warnings"] = list(prepared.report["warnings"])
    report["rows_rejected"] = [
        *prepared.report["rows_rejected"],
        _issue(code, source_name, message),
    ]
    return report


def _base_report() -> dict:
    return {
        "status": "failed",
        "snapshot_id": None,
        "source_files": [],
        "rows_read": 0,
        "canonical_rows_loaded": 0,
        "counts": {
            "categories": 0,
            "products": 0,
            "rows_read": 0,
            "by_status": {status: 0 for status in VALID_STATUSES},
            "by_availability": {availability: 0 for availability in AVAILABILITIES},
        },
        "warnings": [],
        "rows_rejected": [],
    }


def _issue(code: str, source_name: str, message: str) -> dict:
    return {
        "code": code,
        "message": message,
        "file": source_name,
        "row": None,
        "field": None,
        "severity": "critical",
    }
