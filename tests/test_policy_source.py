from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import re

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.policy.source import (
    EXPECTED_SECTIONS,
    EXPECTED_SHA256,
    PolicySourceError,
    _extract_pages,
    _parse_sections,
    build_policy_index,
    extract_policy_index,
    validate_index,
)
from scripts.build_policy_index import main


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "resources" / "políticas_da_loja.pdf"
PAGE_MAP = {
    "1": [2], "1.1": [2], "1.2": [2], "2": [2],
    "3": [3], "3.1": [3],
    "4": [4], "4.1": [4], "4.2": [4], "4.3": [4], "4.4": [4],
    "5": [4], "5.1": [4], "5.2": [4, 5], "5.3": [5],
    "6": [6], "6.1": [6], "6.2": [6], "7": [6], "7.1": [6],
    "7.2": [6, 7], "7.3": [7], "8": [7], "8.1": [7],
    "8.2": [7], "8.3": [7], "9": [7, 8], "10": [8],
}


@pytest.fixture(scope="module")
def real_index():
    return extract_policy_index(PDF)


def test_original_identity_and_every_physical_page_ac01(real_index):
    assert hashlib.sha256(PDF.read_bytes()).hexdigest() == EXPECTED_SHA256
    assert real_index["source_sha256"] == "b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7"
    assert real_index["schema_version"] == 1
    assert real_index["document_version"] == "2.1"
    assert real_index["page_count"] == 8
    assert real_index["source_filename"] == PDF.name
    assert [s["section_id"] for s in real_index["sections"]] == list(PAGE_MAP)
    assert len(real_index["sections"]) == 28
    assert {s["section_id"]: s["pages"] for s in real_index["sections"]} == PAGE_MAP
    assert real_index["cover"]["pages"] == [1]
    validate_index(real_index)


def test_original_bytes_and_repeated_builds_are_identical_ac02(tmp_path):
    before = PDF.read_bytes()
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    assert build_policy_index(input_path=PDF, output=first)["status"] == "ok"
    assert build_policy_index(input_path=PDF, output=second)["status"] == "ok"
    assert first.read_bytes() == second.read_bytes()
    assert PDF.read_bytes() == before
    assert json.loads(first.read_text(encoding="utf-8"))["source_sha256"] == EXPECTED_SHA256


def test_identical_pdf_bytes_use_canonical_source_name_ac02(tmp_path):
    copied_source = tmp_path / "renamed-original.pdf"
    copied_source.write_bytes(PDF.read_bytes())
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    assert build_policy_index(input_path=PDF, output=first)["status"] == "ok"
    assert build_policy_index(input_path=copied_source, output=second)["status"] == "ok"
    assert first.read_bytes() == second.read_bytes()


def test_original_clauses_tables_negations_and_continuations_ac03(real_index):
    sections = {s["section_id"]: s for s in real_index["sections"]}
    assert "Sábado 09:00 às 13:00 Domingo e Feriados Fechado" in sections["2"]["content"]
    assert "5% de desconto sobre o preço de tabela" in sections["3"]["content"]
    assert "Parcela mínima de R$ 100,00" in sections["3"]["content"]
    assert "• Parcelamento de 4x a 6x: sem juros, parcela mínima de R$ 80,00." in sections["3.1"]["content"]
    assert "7 (sete) dias corridos após o recebimento" in sections["4.1"]["content"]
    assert "em até 10 dias úteis" in sections["4.1"]["content"]
    assert "R$ 500,00" in sections["5.1"]["content"]
    assert "R$ 35,00" in sections["5.1"]["content"]
    assert "PAC (Correios) 5 a 12 dias úteis Sim Incluído" in sections["5.2"]["content"]
    assert "SEDEX (Correios) 2 a 5 dias úteis" in sections["5.2"]["content"]
    assert "não se aplica sobre preços já promocionais" in sections["6.2"]["content"]
    assert "1. Saudação:" in sections["7.2"]["content"]
    assert "5. Fechamento:" in sections["7.2"]["content"]
    assert "mediante consentimento explícito do cliente" in sections["9"]["content"]
    assert "não são compartilhados com terceiros para fins de marketing" in sections["9"]["content"]
    assert all("Página" not in s["content"] for s in real_index["sections"])
    assert all("Manual de Políticas e Procedimentos" not in s["content"] for s in real_index["sections"])


def test_heading_only_parents_remain_original_text(real_index):
    sections = {s["section_id"]: s for s in real_index["sections"]}
    assert sections["5"]["content"] == "5. Política de Frete e Entregas"
    assert sections["6"]["content"] == "6. Promoções e Descontos"
    assert sections["8"]["content"] == "8. Garantia"


def test_all_source_text_is_preserved_without_missing_clauses_ac03(real_index):
    # Independently reconstruct every physical page, rather than checking only
    # selected answers or using the production parser to produce expectations.
    clean_pages = []
    header = "Empório da Música Manual de Políticas e Procedimentos"
    for number, page in enumerate(PdfReader(PDF).pages[1:], start=2):
        text = " ".join(page.extract_text().split())
        assert text.startswith(header)
        text = text[len(header):].strip()
        text = re.sub(rf"\s+Página {number}$", "", text).strip()
        clean_pages.append(text)
    assert " ".join(section["content"] for section in real_index["sections"]) == " ".join(clean_pages)


def _synthetic_pages():
    pages = ["Capa controlada Versão 2.1"] + [""] * 7
    for section_id, title in EXPECTED_SECTIONS:
        page = PAGE_MAP[section_id][0]
        number = section_id + ("." if "." not in section_id else "")
        pages[page - 1] += f" {number} {title} Marcador-{section_id}."
    pages[4] = "Continuação sintética do transporte. " + pages[4]
    pages[6] = "3. Passo controlado. 4. Outro passo. 5. Último passo. " + pages[6]
    pages[7] = "• Não compartilhar o marcador. " + pages[7]
    return pages


def test_small_controlled_pages_preserve_continuations_and_numbered_steps():
    sections = _parse_sections(_synthetic_pages())
    by_id = {s["section_id"]: s for s in sections}
    assert len(sections) == 28
    assert "Continuação sintética" in by_id["5.2"]["content"]
    assert by_id["5.2"]["pages"] == [4, 5]
    assert "3. Passo controlado. 4. Outro passo. 5. Último passo." in by_id["7.2"]["content"]
    assert by_id["7.2"]["pages"] == [6, 7]
    assert "• Não compartilhar" in by_id["9"]["content"]
    assert by_id["9"]["pages"] == [7, 8]


@pytest.mark.parametrize("change", ["missing", "duplicate", "order", "empty"])
def test_controlled_pages_fail_closed_on_heading_damage(change):
    pages = _synthetic_pages()
    if change == "missing":
        pages[1] = pages[1].replace("1.1 Missão", "Ausente Missão")
    elif change == "duplicate":
        pages[1] += " 1.1 Missão Duplicada."
    elif change == "order":
        pages[1] = pages[1].replace("1.1 Missão", "1.2 Dados da Empresa", 1)
    else:
        pages[4] = ""
    with pytest.raises(PolicySourceError):
        _parse_sections(pages)


def test_small_pdf_is_extracted_locally_without_external_binary():
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 100 Td (Controlled marker) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    assert _extract_pages(buffer.getvalue()) == ["Controlled marker"]


@pytest.mark.parametrize("damage", ["missing", "corrupt", "empty", "blank", "wrong_identity", "encrypted"])
def test_malformed_source_preserves_existing_index_and_sanitizes_errors(tmp_path, damage, real_index):
    source = tmp_path / "confidential-source.pdf"
    output = tmp_path / "index.json"
    previous = json.dumps(real_index, ensure_ascii=False).encode("utf-8")
    output.write_bytes(previous)
    if damage == "corrupt":
        source.write_bytes(b"secret-token not a PDF")
    elif damage == "empty":
        source.write_bytes(b"")
    elif damage in {"blank", "encrypted"}:
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        if damage == "encrypted":
            writer.encrypt("secret-password")
        writer.write(source)
    elif damage == "wrong_identity":
        source.write_bytes(PDF.read_bytes() + b"\n% changed provenance")
    report = build_policy_index(input_path=source, output=output)
    assert report["status"] == "error"
    assert "confidential" not in json.dumps(report)
    assert "secret" not in json.dumps(report)
    assert "Traceback" not in json.dumps(report)
    assert output.read_bytes() == previous
    validate_index(json.loads(output.read_bytes()))
    assert sorted(p.name for p in tmp_path.iterdir()) == (["index.json"] if damage == "missing" else ["confidential-source.pdf", "index.json"])


@pytest.mark.parametrize("field,value", [
    ("schema_version", 999), ("schema_version", True), ("document_version", "9.9"),
    ("page_count", 7), ("page_count", True), ("source_sha256", "0" * 64),
    ("source_filename", ""), ("source_filename", "/private/file.pdf"),
    ("sections", []), ("sections", None), ("cover", {"pages": [2]}),
])
def test_invalid_index_metadata_is_rejected(real_index, field, value):
    index = copy.deepcopy(real_index)
    index[field] = value
    with pytest.raises(PolicySourceError):
        validate_index(index)


@pytest.mark.parametrize("change", ["missing", "duplicate", "order", "empty_content", "bad_title", "bad_pages", "bool_page", "non_dict"])
def test_invalid_index_sections_are_rejected(real_index, change):
    index = copy.deepcopy(real_index)
    if change == "missing":
        index["sections"].pop()
    elif change == "duplicate":
        index["sections"][1] = index["sections"][0]
    elif change == "order":
        index["sections"].reverse()
    elif change == "empty_content":
        index["sections"][0]["content"] = "   "
    elif change == "bad_title":
        index["sections"][0]["title"] = "Inventado"
    elif change == "bad_pages":
        index["sections"][0]["pages"] = [8]
    elif change == "bool_page":
        index["sections"][0]["pages"] = [True]
    else:
        index["sections"][0] = None
    with pytest.raises(PolicySourceError):
        validate_index(index)


@pytest.mark.parametrize("shape", [None, [], "index", 123])
def test_nonobject_index_is_rejected(shape):
    with pytest.raises(PolicySourceError):
        validate_index(shape)


def test_failed_atomic_replace_preserves_valid_output(tmp_path, monkeypatch, real_index):
    import app.policy.source as source_module

    output = tmp_path / "index.json"
    previous = json.dumps(real_index, ensure_ascii=False).encode("utf-8")
    output.write_bytes(previous)
    def denied(*args):
        raise OSError("private-path secret-token")
    monkeypatch.setattr(source_module.os, "replace", denied)
    report = build_policy_index(input_path=PDF, output=output)
    assert report["status"] == "error"
    assert output.read_bytes() == previous
    validate_index(json.loads(output.read_bytes()))
    assert list(tmp_path.iterdir()) == [output]
    assert "private" not in json.dumps(report)


def test_source_cannot_be_replaced_by_output(tmp_path):
    source = tmp_path / "original.pdf"
    source.write_bytes(PDF.read_bytes())
    before = source.read_bytes()
    assert build_policy_index(input_path=source, output=source)["status"] == "error"
    assert source.read_bytes() == before


def test_builder_cli_defaults_env_override_and_failure(tmp_path, monkeypatch, capsys):
    output = tmp_path / "policy.json"
    monkeypatch.setenv("EMPORIO_POLICY_PDF", str(PDF))
    assert main(["--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["section_count"] == 28
    assert main(["--input", str(tmp_path / "missing.pdf"), "--output", str(output)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
