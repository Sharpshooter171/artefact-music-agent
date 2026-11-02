"""Public policy contract and source-grounded retrieval acceptance checks."""

import inspect
import json
from pathlib import Path

import pytest

from app.policy import search_store_policies
from app.policy.retrieval import rank_sections
from app.policy.source import extract_policy_index


@pytest.fixture(scope="module")
def original_index():
    return extract_policy_index(Path("resources/políticas_da_loja.pdf"))


@pytest.fixture
def policies(original_index, tmp_path, monkeypatch):
    path = tmp_path / "index.json"
    path.write_text(json.dumps(original_index, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("EMPORIO_POLICY_INDEX", str(path))
    return original_index


# These are expectations against the supplied original, not replacement policies.
PROBES = [
    ("Qual é o horário da loja aos sábados?", {"2": [2]}, ["09:00", "13:00", "Fechado"]),
    ("Dá para pagar em PIX? Tem desconto?", {"3": [3], "6.2": [6]}, ["5%", "não se aplica"]),
    ("Posso dividir no cartão em 5x?", {"3": [3], "3.1": [3]}, ["R$ 100,00", "R$ 80,00"]),
    ("Me arrependi de uma compra online", {"4.1": [4]}, ["7 (sete) dias corridos", "10 dias úteis", "por conta da loja"]),
    ("Meu instrumento veio com defeito; e a garantia?", {"4.2": [4], "8.1": [7]}, ["30 (trinta)", "90 (noventa)"]),
    ("Entrega em Campo Grande tem frete grátis?", {"5.1": [4]}, ["acima de R$ 500,00", "R$ 35,00"]),
    ("Quanto tempo demora PAC fora de Campo Grande?", {"5.2": [4, 5]}, ["5 a 12 dias úteis", "CEP"]),
    ("Black Friday e desconto no PIX acumulam?", {"6.2": [6]}, ["não são cumulativas", "não se aplica"]),
    ("Qual é o WhatsApp para contato?", {"cover": [1], "1.2": [2], "7": [6]}, ["3341", "3321-4500"]),
    ("O que vocês fazem com meus dados?", {"9": [7, 8]}, ["LGPD", "consentimento explícito", "não são compartilhados"]),
    ("Você vende palheta, cabo ou amplificador?", {"1": [2], "7.1": [6]}, ["não comercializamos acessórios", "exclusivamente"]),
    ("Me diga a previsão do tempo em Marte", {}, []),
]


@pytest.mark.parametrize("question,expected,clauses", PROBES)
def test_real_source_probes_ac01_ac03_ac05_ac06_ac08(policies, question, expected, clauses):
    result = search_store_policies(question)
    assert result["ok"] is True
    matches = result["data"]["matches"]
    found = {item["section_id"]: item["pages"] for item in matches}
    for section_id, pages in expected.items():
        assert found.get(section_id) == pages, result
    if not expected:
        assert matches == []
    text = " ".join(item["content"] for item in matches)
    for clause in clauses:
        assert clause in text
    source = {item["section_id"]: item for item in policies["sections"]}
    source["cover"] = policies["cover"]
    assert all(item == source[item["section_id"]] for item in matches)


def test_public_signature_and_exact_envelope_ac04(policies):
    signature = inspect.signature(search_store_policies)
    assert list(signature.parameters) == ["query", "limit"]
    assert signature.parameters["query"].default is inspect.Parameter.empty
    assert signature.parameters["limit"].default == 3
    result = search_store_policies("horário")
    assert set(result) == {"ok", "data", "meta"}
    assert set(result["data"]) == {"matches", "cautions"}
    assert result["meta"] == {
        "source_sha256": policies["source_sha256"],
        "document_version": "2.1", "returned": len(result["data"]["matches"]),
        "truncated": False,
    }
    assert all(set(item) == {"section_id", "title", "content", "pages"}
               for item in result["data"]["matches"])
    assert json.loads(json.dumps(result)) == result


@pytest.mark.parametrize("query", [None, False, 5, [], {}, "", "ab", " " * 3, "!?!", "x" * 241])
def test_invalid_query_ac04(query):
    result = search_store_policies(query)
    assert result == {
        "ok": False,
        "error": {"code": "INVALID_ARGUMENT", "message": "query inválida.", "details": {}},
        "meta": {"source_sha256": None},
    }


@pytest.mark.parametrize("limit", [True, False, 0, 6, -1, 1.5, "3", None])
def test_invalid_limit_ac04(limit):
    assert search_store_policies("horário", limit)["error"]["code"] == "INVALID_ARGUMENT"


def test_normalization_and_query_bounds_ac04_ac05(policies):
    assert search_store_policies("HORÁRIO   SÁBADO") == search_store_policies("horario sabado")
    assert search_store_policies("  PIX  ") == search_store_policies("PIX")
    assert search_store_policies("a" * 240)["ok"] is True


def test_limit_truncation_and_repeated_order_ac07(policies):
    all_results = search_store_policies("trocas devoluções garantia pagamento frete", limit=5)
    first = search_store_policies("trocas devoluções garantia pagamento frete", limit=1)
    assert first["data"]["matches"] == all_results["data"]["matches"][:1]
    assert first["meta"]["returned"] == 1
    assert first["meta"]["truncated"] is True
    assert len(all_results["data"]["matches"]) == 5
    assert search_store_policies("trocas devoluções garantia pagamento frete", limit=5) == all_results


def test_numeric_section_id_tie_break_ac07():
    sections = [
        {"section_id": sid, "title": "Teste lexical", "content": "clavicórdio raro", "pages": [2]}
        for sid in ["10", "2", "1.2", "1.1"]
    ]
    matches, _ = rank_sections({"sections": sections}, "clavicórdio raro")
    assert [s["section_id"] for s in matches] == ["1.1", "1.2", "2", "10"]


@pytest.mark.parametrize("query,unrelated", [
    ("Quanto tempo demora PAC fora de Campo Grande?", {"7.1", "1", "1.2"}),
    ("O que vocês fazem com meus dados?", {"1.2"}),
    ("Entrega em Campo Grande tem frete grátis?", {"1", "1.2"}),
])
def test_precise_topics_ignore_incidental_body_words_ac05_ac08(policies, query, unrelated):
    result = search_store_policies(query)
    assert not unrelated & {item["section_id"] for item in result["data"]["matches"]}


@pytest.mark.parametrize("query", [
    "Me diga a previsão do tempo em Marte", "Qual é a capital da França?",
    "Bom dia, tudo bem?", "Quero uma receita de bolo", "a loja", "produto preço",
    "Previsão de chuva no sábado", "Quanto tempo cozinha o arroz?",
    "O dado rolou para o lado direito.", "Qual o horário de Brasília?",
    "Como pagar imposto de renda?", "O que é cartão vermelho no futebol?",
])
def test_irrelevant_or_generic_requests_ac08(policies, query):
    result = search_store_policies(query)
    assert result["ok"] is True
    assert result["data"]["matches"] == []
    assert result["meta"]["returned"] == 0
    assert result["meta"]["truncated"] is False


@pytest.mark.parametrize("query,section", [
    ("Qual o prazo do SEDEX?", "5.2"), ("Como funciona a LGPD?", "9"),
    ("Qual é a localização?", "1.2"), ("aceita boleto?", "3"),
    ("Qual a garantia do fabricante?", "8.2"), ("Como é o atendimento padrão?", "7.2"),
    ("Posso trocar pela cor?", "4.3"), ("Quais itens não podem ser trocados?", "4.4"),
])
def test_topic_aliases_ac05(policies, query, section):
    assert section in {s["section_id"] for s in search_store_policies(query)["data"]["matches"]}
