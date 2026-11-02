"""Deterministic lexical selection. Source excerpts remain untrusted data."""

from __future__ import annotations

import re
import unicodedata


_STOPWORDS = frozenset("""
a ao aos as ate com como da das de do dos e em entre eu me meu meus minha minhas
na nas no nos o os ou para pelo pela pelos pelas por qual quais que se sem sua
suas seu seus um uma uns umas voce voces isso isto esse essa tem ter quero posso
podem pode fazem faz ser sao e esta estao sobre quanto loja produto produtos
instrumento instrumentos preco precos diga bom dia tudo bem campo grande
funciona funcionam aceita aceitam hoje agora atual atuais ativa ativas ativo ativos
""".split())


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def _tokens(value: str) -> set[str]:
    return set(normalize_text(value).split()) - _STOPWORDS


# Small explicit topic map, containing identifiers rather than authored answers.
_TOPICS = {
    "hours": ({"horario", "horarios", "funcionamento", "abre", "abrem", "aberto", "aberta", "fecha", "fecham", "fechado", "expediente"}, {"2": 140}),
    "contact": ({"whatsapp", "contato", "contatos", "telefone", "telefones", "email", "localizacao", "endereco", "cnpj"}, {"1.2": 140, "7": 140, "cover": 140}),
    "payment": ({"pagamento", "pagamentos", "pagar", "pago", "pagam", "debito", "boleto", "dinheiro"}, {"3": 140, "3.1": 90}),
    "pix": ({"pix"}, {"3": 145, "6.2": 140}),
    "installments": ({"cartao", "credito", "parcelar", "parcelamento", "parcela", "parcelas", "dividir", "divido"}, {"3.1": 150, "3": 145}),
    "withdrawal": ({"arrependi", "arrependimento", "desisti", "desistir", "reembolso", "reembolsar", "estorno", "devolver", "devolucao", "devolucoes"}, {"4.1": 150, "4": 85}),
    "exchange": ({"troca", "trocar", "trocas"}, {"4": 85, "4.1": 100, "4.2": 100, "4.3": 100, "4.4": 100}),
    "defect": ({"defeito", "defeitos", "defeituoso", "quebrado", "avaria"}, {"4.2": 155, "8.1": 145, "8.3": 90}),
    "preference": ({"cor", "tamanho", "preferencia"}, {"4.3": 160}),
    "ineligible": ({"elegiveis", "inelegiveis", "personalizacao", "personalizado", "boquilhas"}, {"4.4": 160}),
    "shipping": ({"frete", "entrega", "entregas", "envio", "envios", "enviar"}, {"5.1": 120, "5.2": 115, "5": 75}),
    "carrier": ({"pac", "sedex", "jadlog", "correios", "transportadora"}, {"5.2": 170}),
    "tracking": ({"rastreio", "rastreamento", "rastrear", "rastreie", "despachado"}, {"5.3": 160}),
    "promotions": ({"promocao", "promocoes", "promocional", "promocionais", "desconto", "descontos", "black", "friday", "acumulam", "acumula", "acumular", "cumulativas", "cumulatividade", "campanhas", "campanha", "oferta", "ofertas"}, {"6.2": 140, "6.1": 115, "6": 70}),
    "service": ({"atendimento", "atendente", "atendentes", "humano", "humana", "assistente", "reclamacao", "reclamacoes", "reclamar"}, {"7.2": 115, "7.1": 110, "7.3": 105}),
    "warranty": ({"garantia", "garantias"}, {"8.1": 150, "4.2": 145, "8.2": 110, "8.3": 100, "8": 70}),
    "privacy": ({"dados", "privacidade", "lgpd", "consentimento", "exclusao"}, {"9": 160}),
    "catalog": ({"acessorio", "acessorios", "palheta", "palhetas", "cabo", "cabos", "amplificador", "amplificadores", "pedal", "pedais", "cases", "catalogo"}, {"1": 150, "7.1": 145}),
}


def _section_key(section_id: str) -> tuple[int, ...]:
    return (0,) if section_id == "cover" else tuple(map(int, section_id.split(".")))


def rank_sections(index: dict, query: str) -> tuple[list[dict], list[dict]]:
    """Return all relevant full sections and topic cautions before caller limits."""
    normalized = normalize_text(query)
    tokens = _tokens(query)
    vocabulary = set().union(*(
        _tokens(section["content"]) | _tokens(section["title"])
        for section in index["sections"]
    ))
    aliases = set().union(*(topic[0] for topic in _TOPICS.values()))
    support = vocabulary | aliases | {"sabados", "domingos"}
    # Most informative words must belong to the policy vocabulary or aliases.
    # This prevents an isolated "cartão" in a football question from selecting
    # payment rules. Unknown context receives an honest no-match.
    if not tokens or len(tokens & support) * 2 <= len(tokens):
        return [], []
    weights: dict[str, int] = {}
    active: set[str] = set()

    def activate(topic: str) -> None:
        active.add(topic)
        for section_id, weight in _TOPICS[topic][1].items():
            weights[section_id] = max(weights.get(section_id, 0), weight)

    for topic, (aliases, _) in _TOPICS.items():
        if tokens & aliases:
            activate(topic)
    if re.search(r"\b(?:[2-9]|1[0-2])x\b", normalized) or "sem juros" in normalized:
        activate("installments")
    if "e mail" in normalized:
        activate("contact")
    if "campo grande" in normalized and ("shipping" in active or "carrier" in active):
        if "carrier" not in active and "fora" not in tokens:
            weights["5.1"] = 165
        else:
            weights["5.2"] = 175
    if "outras cidades" in normalized or "outra cidade" in normalized:
        activate("shipping")
        weights["5.2"] = 170
    if "fabricante" in tokens and "warranty" in active:
        weights["8.2"] = 180
    if "padrao" in tokens and "service" in active:
        weights["7.2"] = 170
    if tokens & {"reclamacao", "reclamacoes", "reclamar"}:
        weights["7.3"] = 175
    if "exchange" in active and ("nao" in tokens or "itens" in tokens):
        activate("ineligible")
    if "hours" not in active and tokens & {"sabado", "domingo", "feriados"} and ("loja" in normalized.split() or "service" in active):
        activate("hours")

    candidates = list(index["sections"])
    if "contact" in active and index.get("cover"):
        candidates.append(index["cover"])
    ranked: list[tuple[int, dict]] = []
    for section in candidates:
        title_hits = tokens & _tokens(section["title"])
        content_hits = tokens & _tokens(section["content"])
        topic_weight = weights.get(section["section_id"], 0)
        # A lone incidental body word (e.g. tempo/sábado) is insufficient.
        lexical_relevant = (
            (not active and tokens == _tokens(section["title"])
             and any(len(token) >= 5 for token in title_hits))
            or len(content_hits) >= 2 and (
                bool(title_hits) or sum(len(token) >= 4 for token in content_hits) >= 2
            ) and len(content_hits) * 2 >= len(tokens)
        )
        if active and not title_hits:
            lexical_relevant = lexical_relevant and len(content_hits) * 4 >= len(tokens) * 3
        if topic_weight or lexical_relevant:
            score = topic_weight + 4 * len(title_hits) + 2 * len(content_hits)
            ranked.append((score, section))
    ranked.sort(key=lambda item: (-item[0], _section_key(item[1]["section_id"])))
    # Guardrails follow relevant source sections too, including lexical matches
    # whose words are absent from the alias map. Evaluate before truncation.
    caution_topics = {
        "cover": "contact", "1.2": "contact", "7": "contact",
        "3.1": "installments", "4.1": "withdrawal", "4.2": "defect",
        "8.1": "warranty", "5.3": "tracking", "6": "promotions",
        "6.1": "promotions", "6.2": "promotions", "7.3": "service",
    }
    active.update(caution_topics[section["section_id"]] for _, section in ranked
                  if section["section_id"] in caution_topics)
    return [section for _, section in ranked], _cautions(active)


def _cautions(active: set[str]) -> list[dict]:
    cautions = []

    def add(code: str, message: str, pages: list[int]) -> None:
        cautions.append({"code": code, "message": message, "pages": pages})

    if "contact" in active:
        add("CONTACT_CONFLICT", "O manual apresenta telefones/WhatsApp e e-mails divergentes entre a capa e as seções de contato. Confirme com a equipe antes de escolher um contato definitivo.", [1, 2, 6])
    if "installments" in active:
        add("INSTALLMENT_CONFLICT", "A tabela de pagamentos e as regras de parcelamento apresentam condições mínimas divergentes. Consulte ambas e confirme com a equipe; não há um mínimo único confirmado.", [3])
    if active & {"defect", "warranty"}:
        add("WARRANTY_PROCEDURE_DISTINCTION", "Troca por defeito e garantia legal são procedimentos distintos, com prazos e marcos iniciais próprios. Consulte ambas as seções; o prazo de troca não substitui a garantia legal.", [4, 7])
    if active & {"promotions", "pix"}:
        add("PROMOTION_NOT_LIVE", "Este manual é de junho de 2025. Campanhas descritas não comprovam promoções ativas nem preços atuais; o desconto PIX não se acumula com preços promocionais.", [6])
    action_pages = set()
    if "withdrawal" in active:
        action_pages.add(4)
    if "tracking" in active:
        action_pages.add(5)
    if "service" in active:
        action_pages.update([6, 7])
    if action_pages:
        add("ACTION_NOT_IMPLEMENTED", "Esta ferramenta apenas consulta políticas. Não processa reembolso, reclamação, envio, rastreamento de pedido ou encaminhamento humano; os procedimentos e prazos do manual não confirmam ações realizadas nem SLA deste protótipo.", sorted(action_pages))
    return cautions
