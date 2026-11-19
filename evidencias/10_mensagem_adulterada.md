# Cenario 10: Mensagem de transferencia adulterada

**Resultado: PASSOU** (7/7 verificacoes, 18.3 s, executado em 2026-11-19 03:06:46)

**Objectivo:** Um intermediario altera o montante de uma ordem assinada por api-1. O coordenador verifica a assinatura RSA-PSS/SHA-256 antes de tocar nos saldos e recusa a ordem.

## Procedimento executado

1. `03:06:29` Ordem de 1.00 assinada com a chave de api-1; o montante e alterado para 999 999.00

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1001 | 4 841.50 | 4 840.50 |
| US-2001 | 3 458.50 | 3 459.50 |

## Representacao canonica e SHA-256

```
{
  "original": "{\"chave_idempotencia\":\"c10-d42f61e2-6d0f-4418-9f93-c1fe72f1ed40\",\"conta_destino\":\"US-2001\",\"conta_origem\":\"EU-1001\",\"emitido_em\":\"2026-11-19T01:06:29.393+00:00\",\"id\":\"22cd0e0d-f6fd-4b4a-a2be-49b76a76d61e\",\"instancia\":\"api-1\",\"moeda\":\"EUR\",\"montante_centimos\":100,\"utilizador\":\"ana\"}",
  "sha256 original": "81b61c85e1c2b29d504996aa10ce822ab8cbfe924ed8a88bde4e5bc325a5641f",
  "adulterada": "{\"chave_idempotencia\":\"c10-d42f61e2-6d0f-4418-9f93-c1fe72f1ed40\",\"conta_destino\":\"US-2001\",\"conta_origem\":\"EU-1001\",\"emitido_em\":\"2026-11-19T01:06:29.393+00:00\",\"id\":\"22cd0e0d-f6fd-4b4a-a2be-49b76a76d61e\",\"instancia\":\"api-1\",\"moeda\":\"EUR\",\"montante_centimos\":99999900,\"utilizador\":\"ana\"}",
  "sha256 adulterada": "c97250f20b0a0a2cee24ff13435c5b4914a58262891779b57e687835bdb11b8e"
}
```

## Respostas do coordenador

```
{
  "montante adulterado": {
    "http": 401,
    "instancia": null,
    "corpo": {
      "detail": "assinatura invalida: a mensagem foi alterada ou nao foi assinada por uma API conhecida"
    }
  },
  "assinada por chave desconhecida": {
    "http": 401,
    "instancia": null,
    "corpo": {
      "detail": "assinatura invalida: a mensagem foi alterada ou nao foi assinada por uma API conhecida"
    }
  },
  "ordem antiga (repeticao)": {
    "http": 401,
    "instancia": null,
    "corpo": {
      "detail": "mensagem fora da janela de 120 s (possivel repeticao)"
    }
  },
  "ordem original intacta": {
    "http": 201,
    "instancia": null,
    "corpo": {
      "id": "22cd0e0d-f6fd-4b4a-a2be-49b76a76d61e",
      "estado": "CONCLUIDA",
      "explicacao": "confirmada em todos os participantes: um debito e um credito",
      "decisao": "COMMIT",
      "codigo_erro": null,
      "motivo": null,
      "conta_origem": "EU-1001",
      "conta_destino": "US-2001",
      "montante": "1.00",
      "montante_centimos": 100,
      "moeda": "EUR",
      "utilizador": "ana",
      "chave_idempotencia": "c10-d42f61e2-6d0f-4418-9f93-c1fe72f1ed40",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-22cd0e0d-f6fd-4b4a-a2be-49b76a76d61e-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-22cd0e0d-f6fd-4b4a-a2be-49b76a76d61e-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T01:06:38.626837+00:00",
      "decidida_em": "2026-11-19T01:06:39.039737+00:00",
      "concluida_em": "2026-11-19T01:06:39.359369+00:00",
      "repetido": false
    }
  }
}
```

## Auditoria no DFS: ordens recusadas

```
{
 "transferencia_id": "22cd0e0d-f6fd-4b4a-a2be-49b76a76d61e",
 "data_utc": "2026-11-19T01:06:31.493+00:00",
 "servico": "coordenador",
 "evento": "ORDEM_RECUSADA",
 "resultado": "ASSINATURA_INVALIDA",
 "detalhe": {
  "motivo": "assinatura invalida: a mensagem foi alterada ou nao foi assinada por uma API conhecida",
  "montante_centimos": 99999900,
  "utilizador": "ana"
 }
}{
 "transferencia_id": "17aaf9a5-4f0f-49e2-b3cd-3b23cd3c8ed8",
 "data_utc": "2026-11-19T01:06:33.658+00:00",
 "servico": "coordenador",
 "evento": "ORDEM_RECUSADA",
 "resultado": "ASSINATURA_INVALIDA",
 "detalhe": {
  "motivo": "assinatura invalida: a mensagem foi alterada ou nao foi assinada por uma API conhecida",
  "montante_centimos": 99999900,
  "utilizador": "ana"
 }
}{
 "transferencia_id": "35ed2685-a743-4134-862b-90efa2f9f760",
 "data_utc": "2026-11-19T01:06:35.785+00:00",
 "servico": "coordenador",
 "evento": "ORDEM_RECUSADA",
 "resultado": "ASSINATURA_INVALIDA",
 "detalhe": {
  "motivo": "mensagem fora da janela de 120 s (possivel repeticao)",
  "montante_centimos": 100,
  "utilizador": "ana"
 }
}
```

## Verificacoes

- [x] montante adulterado: HTTP 401 assinatura invalida
- [x] assinada com outra chave: HTTP 401
- [x] ordem com mais de 120 s: HTTP 401 (fora da janela)
- [x] nenhum saldo mudou com as ordens recusadas
- [x] a ordem original intacta e aceite (HTTP 201)
- [x] so a ordem intacta (1.00) mudou saldos
- [x] a recusa ficou registada na auditoria do DFS
