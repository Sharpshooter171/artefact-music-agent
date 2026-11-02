# Policy: PIX discount

Authentic single-turn customer conversation from a real F-03 execution. The user message and final application response below are copied verbatim from the saved run; they were not recreated with a mock or rewritten for this example.

- Execution artifact timestamp (UTC, captured after the batch): `2026-11-02T05:06:07.245556+00:00`.
- Requested model: `nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter.
- Returned model: `nvidia/nemotron-3-ultra-550b-a55b:free`.
- HTTP status for each model request: `200, 200` (2 requests; no retries).
- Reported provider cost per request: `0, 0`. This is response metadata, not an independent billing audit.
- Application error: `none`.
- Local source artifact: `data/generated/f03-router-live-smoke-final-bcd.json` (ignored; not required to run the project).
- SHA-256 of that artifact: `4847a941a485b6fa8982c08b80dd90b39ce31bbb63493f0da45fa3542bf62c02`.
- Earlier verification: [F-03 evidence](../docs/verification/F-03-verification.md).

## Conversation (pt-BR)

Customer:

```text
Como funciona o desconto no PIX?
```

Assistant (final application response):

```text
O desconto no PIX é de **5% sobre o preço de tabela** para pagamentos à vista, válido tanto para compras presenciais quanto online (Manual, seção 3 – Formas de Pagamento, pág. 3).

**Pontos importantes:**
- O desconto **não se acumula** com preços já promocionais (seção 6.2 – Regras de Promoções, pág. 6).
- Promoções estão sujeitas à disponibilidade de estoque e não geram direito a reserva de preço.

*Atenção:* O manual é de junho de 2025; campanhas descritas não comprovam promoções ativas nem preços atuais (caution PROMOTION_NOT_LIVE). Este manual é de junho de 2025. Campanhas descritas não comprovam promoções ativas nem preços atuais; o desconto PIX não se acumula com preços promocionais.
```

## Observed tool evidence

The following is a selected metadata extract from the actual captured tool results. Section references and result counts are preserved; full policy text and raw provider messages are omitted.

```json
[
  {
    "tool": "search_store_policies",
    "arguments": {
      "query": "desconto PIX como funciona",
      "limit": 3
    },
    "ok": true,
    "meta": {
      "source_sha256": "b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7",
      "document_version": "2.1",
      "returned": 3,
      "truncated": true
    },
    "sections": [
      {
        "section_id": "3",
        "title": "Formas de Pagamento",
        "pages": [
          3
        ]
      },
      {
        "section_id": "6.2",
        "title": "Regras de Promoções",
        "pages": [
          6
        ]
      },
      {
        "section_id": "6.1",
        "title": "Tipos de Promoção",
        "pages": [
          6
        ]
      }
    ],
    "caution_codes": [
      "PROMOTION_NOT_LIVE"
    ]
  }
]
```

## Observed limitation

The caution about historical promotions appears twice in the actual answer: once in model prose and once appended by the host. The transcript retains both. The June 2025 manual does not establish current campaigns.
