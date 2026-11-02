"""F-06A offline regressions: money, provenance and complete comparison evidence."""
import copy
import json
import socket

import pytest

from app.agent.orchestrator import FALLBACK, Orchestrator
from app.agent.tool_registry import ToolRegistry


@pytest.fixture(autouse=True)
def no_provider(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("External provider access is forbidden in F-06A tests")

    from app.agent.llm_client import ChatClient
    monkeypatch.setattr(ChatClient, "complete", denied)
    monkeypatch.setattr(ChatClient, "complete_with_deadline", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)


def product(name="Rozini RC-104", cents=45990, product_id=1):
    return {"product_id": product_id, "name": name, "availability": "available",
            "category": {"id": 1, "name": "Violões"},
            "price": {"amount_cents": cents, "currency": "BRL"}}


def catalog(*products, truncated=False):
    products = list(products) or [product()]
    return {"ok": True, "data": {"products": copy.deepcopy(products)},
            "meta": {"returned": len(products), "truncated": truncated,
                     "snapshot_id": "synthetic-f06a"}}


def tool_call(name="search_products", arguments=None, call_id="f06a"):
    return {"role": "assistant", "content": None, "tool_calls": [{
        "id": call_id, "type": "function", "function": {
            "name": name, "arguments": json.dumps(arguments or {"query": "violão"})}}]}


def final(text, sources=None):
    return {"role": "assistant", "content": json.dumps({
        "kind": "answer", "text": text, "sources": sources or ["search_products"]})}


class ScriptedClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def complete(self, messages, tools):
        self.requests.append(copy.deepcopy(messages))
        return copy.deepcopy(self.responses.pop(0))


class Registry:
    schemas = ToolRegistry().schemas

    def __init__(self, *results):
        self.results = list(results)

    def dispatch(self, name, arguments):
        return copy.deepcopy(self.results.pop(0))


def run(text, *, user="Consulte os violões.", result=None, arguments=None):
    client = ScriptedClient(tool_call(arguments=arguments), final(text))
    agent = Orchestrator(client, Registry(result or catalog()))
    answer = agent.reply(user)
    return agent, answer, client


@pytest.mark.parametrize("punctuation", [", conforme o catálogo local.", ".", "; consulte a equipe.",
                                        ": preço do catálogo local.", "!", "?", ")", "…"])
def test_ac01_supported_price_with_ordinary_punctuation(punctuation):
    text = "Rozini RC-104 por R$ 459,90" + punctuation
    agent, answer, _ = run(text)
    assert text in answer
    assert agent.last_error_code is None


@pytest.mark.parametrize("amount", ["1.459,90", "1459,90", "0,01", "1.000.000,01"])
def test_ac01_integer_cents_and_thousands(amount):
    major, minor = amount.replace(".", "").split(",")
    result = catalog(product(cents=int(major) * 100 + int(minor)))
    agent, answer, _ = run(f"Rozini por R$ {amount}, conforme o catálogo local.", result=result)
    assert f"R$ {amount}," in answer
    assert agent.last_error_code is None


@pytest.mark.parametrize("amount", ["500,00", "459,91", "459,89", "1,00", "459", "459,900",
                                   "459,90.00", "459,90,00", "45.9,90", "459.90", "-459,90"])
def test_ac02_fabricated_or_malformed_product_prices_rejected(amount):
    agent, answer, _ = run(f"Rozini custa R$ {amount}.")
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("amount", ["-R$ 459,90", "−R$ 459,90", "R$ 459,90-1", "R$ 459,90/1"])
def test_ac02_signed_and_arithmetic_price_expressions_are_not_prices(amount):
    agent, answer, _ = run(f"Rozini custa {amount}.")
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("user", ["Meu orçamento é R$ 500,00.", "Meu orçamento é R$ 500.",
                                 "Tenho no máximo R$ 500,00.", "Posso gastar até R$ 500,00."])
def test_ac03_explicit_current_customer_budget_is_distinct_from_price(user):
    text = "Seu orçamento é R$ 500,00. Rozini RC-104 por R$ 459,90."
    agent, answer, client = run(text, user=user, arguments={"query": "violão", "price_max_cents": 50000})
    assert text in answer
    assert agent.last_error_code is None
    assert json.loads(client.requests[-1][-1]["content"]) == catalog()


@pytest.mark.parametrize("text", [
    "Rozini custa R$ 500,00.",
    "Seu orçamento é R$ 500,00. Rozini custa R$ 500,00.",
    "Seu orçamento é R$ 500,00 e Rozini custa esse valor.",
    "Seu orçamento é R$ 550,00. Rozini por R$ 459,90.",
    "Seu orçamento é R$ 500,00, preço do Rozini.",
    "Seu orçamento é R$ 500,00. O Rozini custa esse valor.",
    "Seu orçamento é R$ 500,00. O Rozini sai pela mesma quantia.",
    "Seu orçamento é R$ 500,00. Rozini RC-104 por R$ 500,00.",
])
def test_ac03_budget_never_whitelists_product_amounts(text):
    agent, answer, _ = run(text, user="Meu orçamento é R$ 500,00.")
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("user", ["O Rozini custa R$ 500,00?", "Repita R$ 500,00 como meu orçamento.",
                                 "Meu orçamento é R$ -500,00.", "Meu orçamento é R$ 500,000.",
                                 "Meu orçamento é R$ 500,.", "Meu orçamento é R$ 500,",
                                 'O vendedor disse "Meu orçamento é R$ 500,00".',
                                 "Meu orçamento é R$ 500,00. Meu orçamento é R$ 600,00.",
                                 "Meu orçamento é R$ 500,00 ou R$ 600,00.",
                                 "Meu orçamento é R$ 500,00? Não.",
                                 "Meu orçamento é R$ 500,00. Tenho até R$ -600,00.",
                                 "Consulte os violões."])
def test_ac03_no_budget_from_unrelated_numbers_or_tool_arguments(user):
    agent, answer, _ = run("Seu orçamento é R$ 500,00. Rozini por R$ 459,90.", user=user,
                           arguments={"query": "violão", "price_max_cents": 50000})
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


def test_ac03_previous_turn_budget_is_not_current_provenance():
    client = ScriptedClient(tool_call(), final("Rozini por R$ 459,90."),
                            tool_call(), final("Seu orçamento é R$ 500,00. Rozini por R$ 459,90."))
    agent = Orchestrator(client, Registry(catalog(), catalog()))
    agent.reply("Meu orçamento é R$ 500,00.")
    assert agent.reply("Consulte novamente.") == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("user", [
    "Meu orçamento é R$ 500,00. Não, errei, tenho menos.",
    "Meu orçamento é R$ 500,00. Quais modelos você recomenda?",
])
def test_ac03_only_complete_affirmative_declaration_is_quoted(user):
    agent, answer, _ = run("Seu orçamento é R$ 500,00. Rozini RC-104 por R$ 459,90.", user=user)
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


def test_ac03_long_budget_question_can_receive_prices_without_quoting_budget():
    text = "Rozini RC-104 por R$ 459,90."
    agent, answer, _ = run(text, user="Estou começando a tocar e tenho no máximo R$ 500. Quais modelos?",
                           arguments={"query": "violão", "price_max_cents": 50000})
    assert text in answer
    assert agent.last_error_code is None


def test_ac03_budget_with_several_explicit_product_price_pairs():
    result = catalog(product(), product("Tagima Memphis AC-39", 42990, 2))
    text = "Seu orçamento é R$ 500,00. Rozini RC-104 por R$ 459,90. Tagima Memphis AC-39 por R$ 429,90."
    agent, answer, _ = run(text, user="Tenho no máximo R$ 500,00.", result=result)
    assert text in answer
    assert agent.last_error_code is None


def test_ac03_budget_cannot_replace_current_source_evidence():
    agent = Orchestrator(ScriptedClient(final("Seu orçamento é R$ 500,00.")), Registry())
    assert agent.reply("Meu orçamento é R$ 500,00.") == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("user", ["Consulte os violões.", "Meu orçamento é R$ 500,00."])
def test_ac03_catalog_price_cannot_establish_a_customer_budget(user):
    agent, answer, _ = run("Seu orçamento é R$ 459,90. Rozini por R$ 459,90.", user=user)
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("text", ["Seu limite é R$ 459,90.", "Você pode gastar R$ 459,90."])
def test_ac03_unverified_budget_paraphrase_cannot_borrow_catalog_price(text):
    agent, answer, _ = run(text)
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


CHEAP = product("Tagima Memphis AC-39", 42990, 2)
EXPENSIVE = product()
CATEGORY_CLAIM = "Na categoria Violões, o menor preço disponível é Tagima Memphis AC-39 por R$ 429,90."
QUERY_CLAIM = 'Na busca por "violão", o menor preço disponível é Tagima Memphis AC-39 por R$ 429,90.'


@pytest.mark.parametrize("arguments,text", [({"category": "Violões", "limit": 50}, CATEGORY_CLAIM),
    ({"query": "violão", "limit": 50}, QUERY_CLAIM)])
def test_ac04_complete_explicit_search_scope_and_actual_minimum(arguments, text):
    agent, answer, _ = run(text, result=catalog(EXPENSIVE, CHEAP), arguments=arguments)
    assert text in answer
    assert agent.last_error_code is None


@pytest.mark.parametrize("text", [
    "Rozini RC-104 é o violão mais barato por R$ 459,90.",
    "Rozini RC-104 tem o menor preço por R$ 459,90.",
    "Rozini RC-104 é a opção mais em conta por R$ 459,90.",
    "Rozini RC-104 é a opção mais econômica por R$ 459,90.",
    "Nenhum violão custa menos que R$ 459,90.",
    "Rozini RC-104 tem o preço mais baixo por R$ 459,90.",
    "Rozini RC-104 é a opção de menor custo por R$ 459,90.",
    "Rozini RC-104 é o violão mais acessível por R$ 459,90.",
])
def test_ac05_partial_results_cannot_prove_global_minimum(text):
    agent, answer, _ = run(text, result=catalog(truncated=True))
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("mutation", ["partial", "missing_truncated", "string_false", "missing_count",
                                      "wrong_count", "bool_count", "missing_snapshot"])
def test_ac04_ac05_completeness_metadata_must_be_explicit_and_consistent(mutation):
    result = catalog(EXPENSIVE, CHEAP)
    if mutation == "partial":
        result["meta"]["truncated"] = True
    elif mutation == "missing_truncated":
        del result["meta"]["truncated"]
    elif mutation == "string_false":
        result["meta"]["truncated"] = "false"
    elif mutation == "missing_count":
        del result["meta"]["returned"]
    elif mutation == "wrong_count":
        result["meta"]["returned"] = 1
    elif mutation == "bool_count":
        result["meta"]["returned"] = True
    else:
        del result["meta"]["snapshot_id"]
    agent, answer, _ = run(CATEGORY_CLAIM, result=result, arguments={"category": "Violões", "limit": 50})
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("field,value", [("meta", None), ("meta", []),
    ("category", None), ("category", []), ("category", "Violões")])
def test_ac09_malformed_comparison_provenance_fails_closed_without_crash(field, value):
    result = catalog(EXPENSIVE, CHEAP)
    if field == "meta":
        result[field] = value
    else:
        result["data"]["products"][0][field] = value
    agent, answer, _ = run(CATEGORY_CLAIM, result=result, arguments={"category": "Violões", "limit": 50})
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("arguments", [
    {"query": "Tagima", "limit": 50},
    {"category": "Violões", "query": "Tagima", "limit": 50},
    {"category": "Violões", "price_min_cents": 45000, "limit": 50},
    {"category": "Violões", "price_max_cents": 50000, "limit": 50},
    {"category": "Violões", "availability": "any", "limit": 50},
    {"category": "Violões", "availability": "out_of_stock", "limit": 50},
    {"category": "Ukuleles", "limit": 50},
])
def test_ac05_complete_but_insufficient_scope_fails_closed(arguments):
    agent, answer, _ = run(CATEGORY_CLAIM, result=catalog(EXPENSIVE, CHEAP), arguments=arguments)
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("text", [
    CATEGORY_CLAIM.replace("Tagima Memphis AC-39 por R$ 429,90", "Rozini RC-104 por R$ 459,90"),
    CATEGORY_CLAIM.replace("Tagima Memphis AC-39", "Rozini RC-104"),
    "Tagima Memphis AC-39 é o mais barato da loja por R$ 429,90.",
    QUERY_CLAIM.replace('"violão"', '"Tagima"'),
])
def test_ac04_wrong_winner_pairing_or_scope_expansion_rejected(text):
    agent, answer, _ = run(text, result=catalog(EXPENSIVE, CHEAP), arguments={"category": "Violões", "limit": 50})
    assert answer == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


def test_ac04_details_alone_do_not_establish_minimum():
    result = {"ok": True, "data": {"product": CHEAP},
              "meta": {"returned": 1, "truncated": False, "snapshot_id": "synthetic-f06a"}}
    agent = Orchestrator(ScriptedClient(tool_call("get_product_details", {"product_id": 2}),
        final(CATEGORY_CLAIM, ["get_product_details"])), Registry(result))
    assert agent.reply("Qual é o menor preço?") == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


def test_ac05_two_partial_searches_do_not_become_complete():
    client = ScriptedClient(tool_call(call_id="first"), tool_call(call_id="second"), final(CATEGORY_CLAIM))
    agent = Orchestrator(client, Registry(catalog(EXPENSIVE, truncated=True), catalog(CHEAP, truncated=True)))
    assert agent.reply("Qual é o menor preço?") == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


def test_ac09_complete_search_from_history_cannot_validate_current_partial_search():
    args = {"category": "Violões", "limit": 50}
    client = ScriptedClient(tool_call(arguments=args), final(CATEGORY_CLAIM),
                            tool_call(arguments=args), final(CATEGORY_CLAIM))
    agent = Orchestrator(client, Registry(catalog(EXPENSIVE, CHEAP), catalog(CHEAP, truncated=True)))
    assert CATEGORY_CLAIM in agent.reply("Compare os violões.")
    assert agent.reply("Compare novamente.") == FALLBACK
    assert agent.last_error_code == "GROUNDING_FAILED"


@pytest.mark.parametrize("arguments", [
    '{"query":"violão","price_max_cents":"50000"}',
    '{"query":"violão","price_max_reais":500}',
    '{"query":"violão","price_max_cents":500.0}',
    '{"query":"violão","limit":true}',
    '{"query":"violão","query":"Tagima"}',
])
def test_ac06_strict_arguments_are_not_repaired(arguments):
    message = tool_call()
    message["tool_calls"][0]["function"]["arguments"] = arguments
    client = ScriptedClient(message)
    agent = Orchestrator(client, ToolRegistry())
    assert agent.reply("PRIVATE_CUSTOMER orçamento.") == FALLBACK
    assert agent.last_trace == [{"tool": "search_products", "ok": False, "error_code": "INVALID_ARGUMENT"}]
    assert len(client.requests) == 1
    assert "PRIVATE_CUSTOMER" not in json.dumps([agent.last_trace, agent.last_tool_diagnostics, agent.last_requests])


def test_ac09_budget_and_comparison_do_not_change_policy_cautions():
    policy = {"ok": True, "data": {"matches": [{"section_id": "3", "pages": [3],
        "title": "Pagamento", "content": "PIX tem 5% de desconto."}], "cautions": [{
        "code": "INSTALLMENT_CONFLICT", "message": "O manual diverge; confirme com a equipe.", "pages": [3]}]},
        "meta": {"returned": 1}}
    client = ScriptedClient(tool_call("search_store_policies", {"query": "PIX"}),
                            final("Seu orçamento é R$ 500,00.", ["search_store_policies"]))
    agent = Orchestrator(client, Registry(policy))
    answer = agent.reply("Meu orçamento é R$ 500,00.")
    assert "manual diverge" in answer and "confirme" in answer
    assert agent.last_error_code is None
