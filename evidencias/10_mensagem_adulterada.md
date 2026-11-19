# Cenario 10: Mensagem de transferencia adulterada

**Resultado: PASSOU** (7/7 verificacoes, 18.5 s, executado em 2026-11-19 02:26:49)

**Objectivo:** Um intermediario altera o montante de uma ordem assinada por api-1. O coordenador verifica a assinatura RSA-PSS/SHA-256 antes de tocar nos saldos e recusa a ordem.

## Procedimento executado

1. `02:26:32` Ordem de 1.00 assinada com a chave de api-1; o montante e alterado para 999 999.00

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1001 | 4 841.50 | 4 840.50 |
| US-2001 | 3 458.50 | 3 459.50 |

## Representacao canonica e SHA-256

```
{
  "original": "{\"chave_idempotencia\":\"c10-32bb62db-40f2-4ab6-8fa4-a2f18781a238\",\"conta_destino\":\"US-2001\",\"conta_origem\":\"EU-1001\",\"emitido_em\":\"2026-11-19T00:26:32.484+00:00\",\"id\":\"d1f7d73e-306a-424e-8f04-38ce14fb91bb\",\"instancia\":\"api-1\",\"moeda\":\"EUR\",\"montante_centimos\":100,\"utilizador\":\"ana\"}",
  "sha256 original": "cd51e0188b30ee56a9179b9543e5008128f6682462714ecbcfc41956ec254cc8",
  "adulterada": "{\"chave_idempotencia\":\"c10-32bb62db-40f2-4ab6-8fa4-a2f18781a238\",\"conta_destino\":\"US-2001\",\"conta_origem\":\"EU-1001\",\"emitido_em\":\"2026-11-19T00:26:32.484+00:00\",\"id\":\"d1f7d73e-306a-424e-8f04-38ce14fb91bb\",\"instancia\":\"api-1\",\"moeda\":\"EUR\",\"montante_centimos\":99999900,\"utilizador\":\"ana\"}",
  "sha256 adulterada": "56817e6d8e273e20d8d183c5f3350ff30451c5864d0cb1040695192666cb341d"
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
      "id": "d1f7d73e-306a-424e-8f04-38ce14fb91bb",
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
      "chave_idempotencia": "c10-32bb62db-40f2-4ab6-8fa4-a2f18781a238",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-d1f7d73e-306a-424e-8f04-38ce14fb91bb-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-d1f7d73e-306a-424e-8f04-38ce14fb91bb-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T00:26:41.780040+00:00",
      "decidida_em": "2026-11-19T00:26:42.158445+00:00",
      "concluida_em": "2026-11-19T00:26:42.507547+00:00",
      "repetido": false
    }
  }
}
```

## Auditoria no DFS: ordens recusadas

```
{
 "transferencia_id": "d1f7d73e-306a-424e-8f04-38ce14fb91bb",
 "data_utc": "2026-11-19T00:26:34.585+00:00",
 "servico": "coordenador",
 "evento": "ORDEM_RECUSADA",
 "resultado": "ASSINATURA_INVALIDA",
 "detalhe": {
  "motivo": "assinatura invalida: a mensagem foi alterada ou nao foi assinada por uma API conhecida",
  "montante_centimos": 99999900,
  "utilizador": "ana"
 }
}{
 "transferencia_id": "6f918ac4-5257-42e4-a8ee-68c395d156c4",
 "data_utc": "2026-11-19T00:26:36.812+00:00",
 "servico": "coordenador",
 "evento": "ORDEM_RECUSADA",
 "resultado": "ASSINATURA_INVALIDA",
 "detalhe": {
  "motivo": "assinatura invalida: a mensagem foi alterada ou nao foi assinada por uma API conhecida",
  "montante_centimos": 99999900,
  "utilizador": "ana"
 }
}{
 "transferencia_id": "35c938ca-72aa-4ad1-b976-c10251ec05db",
 "data_utc": "2026-11-19T00:26:38.943+00:00",
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
