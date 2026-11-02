"""Bounded public read-only tool. Never execute query or source text."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.policy.retrieval import normalize_text, rank_sections
from app.policy.source import PolicySourceError, validate_index


_DEFAULT_INDEX = Path(__file__).resolve().parents[2] / "data/generated/policy_index.json"


def search_store_policies(query: str, limit: int = 3) -> dict:
    """Read-only retrieval of relevant original manual sections."""
    if (not isinstance(query, str) or not 3 <= len(query.strip()) <= 240
            or not normalize_text(query)):
        return _error("INVALID_ARGUMENT", "query inválida.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5:
        return _error("INVALID_ARGUMENT", "limit inválido.")
    try:
        path = Path(os.environ.get("EMPORIO_POLICY_INDEX", str(_DEFAULT_INDEX)))
        index = json.loads(path.read_text(encoding="utf-8"))
        validate_index(index)
    except (OSError, ValueError, TypeError, RecursionError, PolicySourceError):
        return _error("POLICY_UNAVAILABLE", "Políticas indisponíveis. Consulte a equipe da loja.")
    except Exception:
        return _error("INTERNAL_ERROR", "Erro interno ao consultar políticas. Consulte a equipe da loja.")
    try:
        matches, cautions = rank_sections(index, query)
        selected = matches[:limit]
        return {
            "ok": True,
            "data": {"matches": selected, "cautions": cautions},
            "meta": {
                "source_sha256": index["source_sha256"],
                "document_version": index["document_version"],
                "returned": len(selected),
                "truncated": len(matches) > limit,
            },
        }
    except Exception:
        return _error("INTERNAL_ERROR", "Erro interno ao consultar políticas. Consulte a equipe da loja.")


def _error(code: str, message: str) -> dict:
    return {
        "ok": False, "error": {"code": code, "message": message, "details": {}},
        "meta": {"source_sha256": None},
    }
