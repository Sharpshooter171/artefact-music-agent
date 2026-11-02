"""Bounded model-selected read-only tools with fail-closed reply validation."""
from __future__ import annotations

import json
import re

from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tool_registry import ToolRegistry

TOOL_NAMES = frozenset({
    "search_products", "get_product_details", "list_categories", "search_store_policies",
})
MAX_REQUESTS = 4
MAX_TOOL_CALLS = 6
MAX_TOOL_BYTES = 12 * 1024
MAX_INPUT_BYTES = 4096
MAX_HISTORY = 12

FALLBACK = ("Não consegui confirmar essa informação com segurança agora. "
            "Posso ajudar com outra consulta ou você pode confirmar com a equipe da loja.")
RATE_FALLBACK = ("O serviço de atendimento está temporariamente no limite de consultas. "
                 "Tente novamente mais tarde ou confirme com a equipe da loja.")
PROVIDER_CODES = frozenset({
    "PROVIDER_RATE_LIMIT", "PROVIDER_AUTH", "PROVIDER_REDIRECT", "PROVIDER_HTTP_ERROR",
    "PROVIDER_TIMEOUT", "PROVIDER_UNAVAILABLE", "REQUEST_TOO_LARGE", "RESPONSE_TOO_LARGE",
    "MALFORMED_RESPONSE", "PROVIDER_REJECTED", "UNAUTHORIZED_RESPONSE_MODEL",
    "INVALID_PROVIDER_COST", "NONZERO_PROVIDER_COST", "INCOMPLETE_RESPONSE",
    "EMPTY_RESPONSE", "UNSAFE_RESPONSE",
})
# The model classifies intent semantically. Evidence-free replies are rendered by
# the host so a malicious final label cannot smuggle store facts or a tutorial.
NONFACTUAL_REPLIES = {
    "out_of_scope": ("Meu atendimento é sobre o Empório da Música. Posso ajudar com "
                     "instrumentos do catálogo ou políticas da loja. Qual é sua dúvida?"),
    "greeting": "Olá! Como posso ajudar com instrumentos ou políticas do Empório da Música?",
    "clarification": ("Pode detalhar sua dúvida sobre instrumentos ou políticas do Empório da Música? "
                      "Se precisar, você também pode confirmar com a equipe da loja."),
}


class Orchestrator:
    def __init__(self, client, registry=None):
        self.client = client
        self.registry = registry if registry is not None else ToolRegistry()
        # Only complete human/assistant exchanges survive between turns. Tool messages
        # stay in the current request loop, preventing orphan IDs and stale authority.
        self.history: list[dict] = []
        self.last_trace: list[dict] = []
        self.last_error_code: str | None = None

    def reply(self, text: str) -> str:
        self.last_trace = []
        self.last_error_code = None
        try:
            valid_input = (isinstance(text, str) and bool(text.strip())
                           and len(text.encode("utf-8")) <= MAX_INPUT_BYTES)
        except UnicodeError:
            valid_input = False
        if not valid_input:
            return self._fail("INVALID_INPUT")
        text = text.strip()
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    *self.history, {"role": "user", "content": text}]
        evidence: dict[str, list[dict]] = {}
        used_ids: set[str] = set()
        tool_count = 0
        tool_bytes = 0
        answer = FALLBACK
        for _ in range(MAX_REQUESTS):
            try:
                message = self.client.complete(messages, self.registry.schemas)
            except Exception as exc:
                # Never expose exception text, provider body, paths or headers.
                code = getattr(exc, "code", "PROVIDER_ERROR")
                answer = self._fail(code if isinstance(code, str) and code in PROVIDER_CODES
                                    else "PROVIDER_ERROR")
                break
            if not isinstance(message, dict) or message.get("role") != "assistant":
                answer = self._fail("INVALID_RESPONSE")
                break
            call_batch = message.get("tool_calls")
            if call_batch:
                if not isinstance(call_batch, list):
                    answer = self._fail("INVALID_RESPONSE")
                    break
                if tool_count + len(call_batch) > MAX_TOOL_CALLS:
                    answer = self._fail("BUDGET_EXCEEDED")
                    break
                if not self._valid_calls(call_batch, used_ids):
                    answer = self._fail("INVALID_RESPONSE")
                    break
                # Append only protocol fields; never forward arbitrary provider keys.
                messages.append({"role": "assistant", "content": message.get("content"),
                                 "tool_calls": call_batch})
                failure = None
                for call in call_batch:
                    tool_count += 1
                    used_ids.add(call["id"])
                    name = call["function"]["name"]
                    try:
                        result = self.registry.dispatch(name, call["function"]["arguments"])
                        serialized = json.dumps(result, ensure_ascii=False, allow_nan=False)
                        size = len(serialized.encode("utf-8"))
                    except Exception:
                        result = {"ok": False, "error": {"code": "TOOL_FAILURE"}}
                        serialized = json.dumps(result)
                        size = len(serialized)
                    ok = isinstance(result, dict) and result.get("ok") is True
                    # Debug/smoke metadata intentionally contains no args or raw results.
                    self.last_trace.append({"tool": name, "ok": ok,
                                            "error_code": None if ok else "TOOL_FAILURE"})
                    tool_bytes += size
                    if tool_bytes > MAX_TOOL_BYTES:
                        failure = "BUDGET_EXCEEDED"
                        break
                    messages.append({"role": "tool", "tool_call_id": call["id"],
                                     "content": serialized})
                    if not ok:
                        failure = "TOOL_FAILURE"
                    elif not self._has_evidence(name, result):
                        failure = "NO_EVIDENCE"
                    else:
                        evidence.setdefault(name, []).append(result)
                # Do not ask a model to repair/override failed or empty source evidence.
                if failure:
                    answer = self._fail(failure)
                    break
            else:
                answer = self._validate_final(message.get("content"), evidence)
                break
        else:
            answer = self._fail("BUDGET_EXCEEDED")
        self.history.extend([{"role": "user", "content": text},
                             {"role": "assistant", "content": answer}])
        self.history = self.history[-MAX_HISTORY:]
        return answer

    def _fail(self, code):
        self.last_error_code = code
        return RATE_FALLBACK if code == "PROVIDER_RATE_LIMIT" else FALLBACK

    @staticmethod
    def _valid_calls(calls, used_ids):
        ids = set(used_ids)
        for call in calls:
            if not isinstance(call, dict) or call.get("type") != "function":
                return False
            call_id = call.get("id")
            if (not isinstance(call_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", call_id)
                    or call_id in ids):
                return False
            ids.add(call_id)
            function = call.get("function")
            if (not isinstance(function, dict) or not isinstance(function.get("name"), str)
                    or function.get("name") not in TOOL_NAMES
                    or not isinstance(function.get("arguments"), str)):
                return False
        return True

    @staticmethod
    def _has_evidence(name, result):
        data = result.get("data")
        if not isinstance(data, dict):
            return False

        def positive_int(value):
            return type(value) is int and value > 0

        def product(value):
            return (isinstance(value, dict) and positive_int(value.get("product_id"))
                    and isinstance(value.get("name"), str) and bool(value["name"])
                    and value.get("availability") in (
                        "available", "out_of_stock", "coming_soon", "discontinued")
                    and isinstance(value.get("price"), dict)
                    and type(value["price"].get("amount_cents")) is int
                    and value["price"]["amount_cents"] >= 0
                    and value["price"].get("currency") == "BRL")

        def pages(value):
            return isinstance(value, list) and bool(value) and all(positive_int(v) for v in value)

        if name == "get_product_details":
            return product(data.get("product"))
        key = {"search_products": "products", "list_categories": "categories",
               "search_store_policies": "matches"}[name]
        items = data.get(key)
        if not isinstance(items, list) or not items:
            return False
        if name == "search_products":
            return all(product(item) for item in items)
        if name == "list_categories":
            return all(isinstance(item, dict) and positive_int(item.get("category_id"))
                       and isinstance(item.get("name"), str)
                       and type(item.get("product_count")) is int and item["product_count"] >= 0
                       for item in items)
        cautions = data.get("cautions")
        return (all(isinstance(item, dict) and all(isinstance(item.get(k), str)
                    for k in ("section_id", "title", "content")) and pages(item.get("pages"))
                    for item in items)
                and isinstance(cautions, list)
                and all(isinstance(c, dict) and isinstance(c.get("code"), str)
                        and isinstance(c.get("message"), str) and pages(c.get("pages"))
                        for c in cautions))

    def _validate_final(self, content, evidence):
        try:
            if not isinstance(content, str) or len(content.encode("utf-8")) > 12000:
                raise ValueError
            payload = json.loads(content)
            if not isinstance(payload, dict) or set(payload) != {"kind", "text", "sources"}:
                raise ValueError
            kind, text, sources = payload["kind"], payload["text"], payload["sources"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError
            if (not isinstance(sources, list) or not all(isinstance(n, str) for n in sources)
                    or len(sources) != len(set(sources))):
                raise ValueError
            if kind != "answer":
                if kind not in {"out_of_scope", "greeting", "clarification"} or sources or evidence:
                    raise ValueError
                # Intent is classified by the model, not by matching customer keywords.
                # This guard only rejects factual assertions in an evidence-free reply.
                if re.search(r"\d|R\$|%|```", text):
                    raise ValueError
                if kind == "out_of_scope" and not re.search(r"loja|Empório|instrumentos", text, re.I):
                    raise ValueError
                if re.search(r"(?:temos|oferecemos|aceitamos|vendemos|abrimos|fechamos)\b", text, re.I):
                    raise ValueError
                return NONFACTUAL_REPLIES[kind]
            if not sources or not set(sources).issubset(evidence):
                raise ValueError
            results = [result for name in sources for result in evidence[name]]
            if not self._numbers_supported(text, results):
                raise ValueError
            if re.search(r"(?<![\d.,])\b\d+(?:\.\d{3})*\s*(?:unidades?|peças?|em estoque)\b|stock_quantity", text, re.I):
                raise ValueError
            if ("search_store_policies" not in sources
                    and re.search(r"\b(?:PIX|desconto|parcelamento|garantia|frete|horário)\b|%", text, re.I)):
                raise ValueError
            cautions = [c for r in results for c in r["data"].get("cautions", [])]
            conflicts = [c for c in cautions if c.get("code") in {"CONTACT_CONFLICT", "INSTALLMENT_CONFLICT"}]
            if conflicts:
                return " ".join(c["message"] for c in conflicts) + " Confirme com a equipe da loja."
            # Keep source cautions even if the model omitted them, including the
            # separate defect-exchange / statutory-warranty procedures.
            additions = [c["message"] for c in cautions
                         if isinstance(c.get("message"), str) and c["message"] not in text]
            if "search_store_policies" in sources:
                citations = [f"seção {m['section_id']}, página(s) {', '.join(map(str, m['pages']))}"
                             for r in evidence["search_store_policies"] for m in r["data"]["matches"]]
                if not re.search(r"página|pág\.", text, re.I):
                    additions.append("Fonte: " + "; ".join(citations) + ".")
            if any(n in sources for n in {"search_products", "get_product_details", "list_categories"}):
                if not re.search(r"catálogo local|retrato|snapshot", text, re.I):
                    additions.append("Disponibilidade conforme o catálogo local, sujeito a confirmação pela equipe.")
            return " ".join([text.strip(), *additions])
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            return self._fail("GROUNDING_FAILED")

    @staticmethod
    def _numbers_supported(text, results):
        # This checks numeric and currency support, not arbitrary semantic truth.
        # Source envelopes remain unchanged in model messages.
        source = json.dumps(results, ensure_ascii=False)
        cents = set()

        def visit(value):
            if isinstance(value, dict):
                price = value.get("price")
                if isinstance(price, dict) and type(price.get("amount_cents")) is int:
                    amount = price["amount_cents"]
                    cents.add(amount)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(results)
        for amount in cents:
            # Integer arithmetic only, including Brazilian thousands formatting.
            whole = f"{amount // 100:,}".replace(",", ".")
            source += f" {whole},{amount % 100:02d} {amount // 100},{amount % 100:02d}"
        if not set(re.findall(r"\d+", text)).issubset(set(re.findall(r"\d+", source))):
            return False
        # Catalog prices and monetary policy thresholds must match exact cents,
        # including mixed requests. Require the canonical Brazilian BRL notation.
        for r in results:
            for match in r.get("data", {}).get("matches", []):
                for raw in re.findall(r"R\$\s*([\d.]+,\d{2})", match.get("content", "")):
                    major, minor = raw.replace(".", "").split(",")
                    cents.add(int(major) * 100 + int(minor))
        if re.search(r"\d[\d.,]*\s*reais\b", text, re.I):
            return False
        for raw in re.findall(r"R\$\s*([\d.,]+)", text):
            raw = raw.rstrip(".")
            if not re.fullmatch(r"(?:\d+|\d{1,3}(?:\.\d{3})+),\d{2}", raw):
                return False
            major, minor = raw.replace(".", "").split(",")
            if int(major) * 100 + int(minor) not in cents:
                return False
        return True
