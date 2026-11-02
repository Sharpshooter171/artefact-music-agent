"""Local extraction and validated, atomic indexing of the approved policy PDF."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PDF = ROOT / "resources" / "políticas_da_loja.pdf"
DEFAULT_POLICY_INDEX = ROOT / "data" / "generated" / "policy_index.json"
EXPECTED_SHA256 = "b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7"
EXPECTED_SECTIONS = (
    ("1", "Sobre a Empório da Música"),
    ("1.1", "Missão"),
    ("1.2", "Dados da Empresa"),
    ("2", "Horário de Funcionamento"),
    ("3", "Formas de Pagamento"),
    ("3.1", "Regras de Parcelamento"),
    ("4", "Política de Trocas e Devoluções"),
    ("4.1", "Direito de Arrependimento (Compras Online)"),
    ("4.2", "Trocas por Defeito"),
    ("4.3", "Trocas por Preferência"),
    ("4.4", "Itens Não Elegíveis para Troca"),
    ("5", "Política de Frete e Entregas"),
    ("5.1", "Entregas na Região Metropolitana de Campo Grande"),
    ("5.2", "Entregas para Outras Cidades"),
    ("5.3", "Código de Rastreamento"),
    ("6", "Promoções e Descontos"),
    ("6.1", "Tipos de Promoção"),
    ("6.2", "Regras de Promoções"),
    ("7", "Atendimento via WhatsApp"),
    ("7.1", "Diretrizes de Atendimento"),
    ("7.2", "Fluxo de Atendimento Padrão"),
    ("7.3", "Situações Especiais"),
    ("8", "Garantia"),
    ("8.1", "Garantia Legal"),
    ("8.2", "Garantia do Fabricante"),
    ("8.3", "O que Não Cobre a Garantia"),
    ("9", "Privacidade e Proteção de Dados"),
    ("10", "Disposições Finais"),
)
EXPECTED_SECTION_PAGES = {
    "1": [2], "1.1": [2], "1.2": [2], "2": [2],
    "3": [3], "3.1": [3],
    "4": [4], "4.1": [4], "4.2": [4], "4.3": [4], "4.4": [4],
    "5": [4], "5.1": [4], "5.2": [4, 5], "5.3": [5],
    "6": [6], "6.1": [6], "6.2": [6], "7": [6], "7.1": [6],
    "7.2": [6, 7], "7.3": [7], "8": [7], "8.1": [7],
    "8.2": [7], "8.3": [7], "9": [7, 8], "10": [8],
}
_HEADER = "Empório da Música Manual de Políticas e Procedimentos"
_HEADINGS = {
    f"{section_id}{'.' if '.' not in section_id else ''} {title}": (section_id, title)
    for section_id, title in EXPECTED_SECTIONS
}
_HEADING_PATTERN = re.compile(
    r"(?<!\S)(?:" + "|".join(re.escape(heading) for heading in _HEADINGS) + r")(?=\s|$)"
)


class PolicySourceError(ValueError):
    """The source or generated index does not satisfy the approved contract."""


def _whitespace(text: str) -> str:
    return " ".join(text.split())


def _extract_pages(raw_pdf: bytes) -> list[str]:
    """Extract physical pages; no OCR, subprocesses, models, or network."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw_pdf), strict=True)
        if reader.is_encrypted or not reader.pages:
            raise PolicySourceError("Unsupported policy source.")
        pages = [_whitespace(page.extract_text() or "") for page in reader.pages]
        if not all(pages):
            raise PolicySourceError("Empty policy page.")
        return pages
    except PolicySourceError:
        raise
    except Exception as exc:
        raise PolicySourceError("Unreadable policy source.") from exc


def _clean_page(text: str, page_number: int) -> str:
    text = _whitespace(text)
    if page_number > 1 and text.startswith(_HEADER):
        text = text[len(_HEADER):].strip()
    return re.sub(rf"\s+Página\s+{page_number}$", "", text).strip()


def _parse_sections(pages: list[str]) -> list[dict]:
    """Split only official heading strings, retaining original numbered steps."""
    if len(pages) != 8 or not all(isinstance(page, str) and page.strip() for page in pages):
        raise PolicySourceError("Unexpected policy pages.")
    sections: list[dict] = []
    current: dict | None = None

    def append_fragment(fragment: str, page_number: int) -> None:
        fragment = fragment.strip()
        if not fragment:
            return
        if current is None:
            raise PolicySourceError("Text before the first policy heading.")
        current["content"] = _whitespace(current["content"] + " " + fragment)
        if page_number not in current["pages"]:
            current["pages"].append(page_number)

    for page_number, text in enumerate(pages[1:], start=2):
        text = _clean_page(text, page_number)
        cursor = 0
        for match in _HEADING_PATTERN.finditer(text):
            append_fragment(text[cursor:match.start()], page_number)
            section_id, title = _HEADINGS[match.group()]
            current = {
                "section_id": section_id,
                "title": title,
                # Headings are part of the original excerpt, including empty parents.
                "content": match.group(),
                "pages": [page_number],
            }
            sections.append(current)
            cursor = match.end()
        append_fragment(text[cursor:], page_number)

    if [section["section_id"] for section in sections] != [sid for sid, _ in EXPECTED_SECTIONS]:
        raise PolicySourceError("Missing, repeated, or unordered policy headings.")
    if any(section["pages"] != EXPECTED_SECTION_PAGES[section["section_id"]] for section in sections):
        raise PolicySourceError("Unexpected policy page provenance.")
    return sections


def extract_policy_index(input_path: Path) -> dict:
    """Build an in-memory index from the unchanged, approved original PDF."""
    try:
        input_path = Path(input_path)
        raw_pdf = input_path.read_bytes()
        pages = _extract_pages(raw_pdf)
        source_sha256 = hashlib.sha256(raw_pdf).hexdigest()
        if source_sha256 != EXPECTED_SHA256 or "Versão 2.1 — Junho de 2025" not in pages[0]:
            raise PolicySourceError("Unexpected policy document identity.")
        index = {
            "schema_version": 1,
            "document_version": "2.1",
            # Provenance names the approved document, even when --input points
            # at a byte-identical copy under a different local filename.
            "source_filename": DEFAULT_POLICY_PDF.name,
            "source_sha256": source_sha256,
            "page_count": len(pages),
            "sections": _parse_sections(pages),
            "cover": {
                "section_id": "cover",
                "title": "Capa",
                "content": _clean_page(pages[0], 1),
                "pages": [1],
            },
        }
        validate_index(index)
        return index
    except PolicySourceError:
        raise
    except Exception as exc:
        raise PolicySourceError("Unreadable policy source.") from exc


def _validate_section(section: object, section_id: str, title: str, pages: list[int]) -> None:
    if not isinstance(section, dict) or set(section) != {"section_id", "title", "content", "pages"}:
        raise PolicySourceError("Invalid policy section.")
    if section["section_id"] != section_id or section["title"] != title:
        raise PolicySourceError("Unexpected policy section identity.")
    if not isinstance(section["content"], str) or not section["content"].strip():
        raise PolicySourceError("Empty policy section content.")
    actual_pages = section["pages"]
    if not isinstance(actual_pages, list) or any(type(page) is not int for page in actual_pages) or actual_pages != pages:
        raise PolicySourceError("Invalid physical page references.")


def validate_index(index: object) -> None:
    """Fail closed on incomplete indexes or unsupported source/schema metadata."""
    if not isinstance(index, dict):
        raise PolicySourceError("Invalid policy index.")
    if type(index.get("schema_version")) is not int or index["schema_version"] != 1:
        raise PolicySourceError("Unsupported policy index schema.")
    if index.get("document_version") != "2.1" or index.get("source_sha256") != EXPECTED_SHA256:
        raise PolicySourceError("Unexpected policy source provenance.")
    if type(index.get("page_count")) is not int or index["page_count"] != 8:
        raise PolicySourceError("Unexpected policy page count.")
    filename = index.get("source_filename")
    if filename != DEFAULT_POLICY_PDF.name:
        raise PolicySourceError("Invalid policy source filename.")
    sections = index.get("sections")
    if not isinstance(sections, list) or len(sections) != len(EXPECTED_SECTIONS):
        raise PolicySourceError("Incomplete policy index.")
    for section, (section_id, title) in zip(sections, EXPECTED_SECTIONS):
        _validate_section(section, section_id, title, EXPECTED_SECTION_PAGES[section_id])
    if "cover" in index:
        _validate_section(index["cover"], "cover", "Capa", [1])


def build_policy_index(*, input_path: Path, output: Path) -> dict:
    """Validate completely before atomically replacing the generated artifact."""
    temporary: Path | None = None
    try:
        input_path, output = Path(input_path), Path(output)
        destination = output.resolve()
        resources = ROOT / "resources"
        if destination == input_path.resolve() or destination == resources or resources in destination.parents:
            raise PolicySourceError("The source location is read-only.")
        index = extract_policy_index(input_path)
        serialized = (json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, prefix=".policy-index-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
        temporary = None
        return {
            "status": "ok",
            "source_sha256": index["source_sha256"],
            "document_version": index["document_version"],
            "page_count": index["page_count"],
            "section_count": len(index["sections"]),
        }
    except Exception:
        return {
            "status": "error",
            "error": {
                "code": "POLICY_UNAVAILABLE",
                "message": "Não foi possível construir o índice de políticas.",
                "details": {},
            },
        }
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
