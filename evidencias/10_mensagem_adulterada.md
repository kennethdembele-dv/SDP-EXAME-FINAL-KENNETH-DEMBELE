# Cenario 10: Mensagem de transferencia adulterada

**Resultado: PASSOU** (7/7 verificacoes, 18.5 s, executado em 2026-11-19 02:17:46)

**Objectivo:** Um intermediario altera o montante de uma ordem assinada por api-1. O coordenador verifica a assinatura RSA-PSS/SHA-256 antes de tocar nos saldos e recusa a ordem.

## Procedimento executado

1. `02:17:28` Ordem de 1.00 assinada com a chave de api-1; o montante e alterado para 999 999.00

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1001 | 4 841.50 | 4 840.50 |
| US-2001 | 3 458.50 | 3 459.50 |

## Representacao canonica e SHA-256

```
{
  "original": "{\"chave_idempotencia\":\"c10-03de7c5b-b66c-4454-8bf7-2d2360a9b1cd\",\"conta_destino\":\"US-2001\",\"conta_origem\":\"EU-1001\",\"emitido_em\":\"2026-11-19T00:17:28.857+00:00\",\"id\":\"d96fed09-de03-4bee-af35-cfad084f12da\",\"instancia\":\"api-1\",\"moeda\":\"EUR\",\"montante_centimos\":100,\"utilizador\":\"ana\"}",
  "sha256 original": "3852c31fe017a718b0de73e3e89735d9b89d75bf6ae5908d0ae384dd20e9cc34",
  "adulterada": "{\"chave_idempotencia\":\"c10-03de7c5b-b66c-4454-8bf7-2d2360a9b1cd\",\"conta_destino\":\"US-2001\",\"conta_origem\":\"EU-1001\",\"emitido_em\":\"2026-11-19T00:17:28.857+00:00\",\"id\":\"d96fed09-de03-4bee-af35-cfad084f12da\",\"instancia\":\"api-1\",\"moeda\":\"EUR\",\"montante_centimos\":99999900,\"utilizador\":\"ana\"}",
  "sha256 adulterada": "64090498dec730466039361c5cc05c8651b8c7f0d89a0b827f86dc32913b03c5"
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
      "id": "d96fed09-de03-4bee-af35-cfad084f12da",
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
      "chave_idempotencia": "c10-03de7c5b-b66c-4454-8bf7-2d2360a9b1cd",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-d96fed09-de03-4bee-af35-cfad084f12da-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-d96fed09-de03-4bee-af35-cfad084f12da-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T00:17:38.334645+00:00",
      "decidida_em": "2026-11-19T00:17:38.708547+00:00",
      "concluida_em": "2026-11-19T00:17:39.025863+00:00",
      "repetido": false
    }
  }
}
```

## Auditoria no DFS: ordens recusadas

```
{
 "transferencia_id": "d96fed09-de03-4bee-af35-cfad084f12da",
 "data_utc": "2026-11-19T00:17:30.972+00:00",
 "servico": "coordenador",
 "evento": "ORDEM_RECUSADA",
 "resultado": "ASSINATURA_INVALIDA",
 "detalhe": {
  "motivo": "assinatura invalida: a mensagem foi alterada ou nao foi assinada por uma API conhecida",
  "montante_centimos": 99999900,
  "utilizador": "ana"
 }
}{
 "transferencia_id": "96c4b08a-32ad-4420-8c28-233e6f21f1a2",
 "data_utc": "2026-11-19T00:17:33.263+00:00",
 "servico": "coordenador",
 "evento": "ORDEM_RECUSADA",
 "resultado": "ASSINATURA_INVALIDA",
 "detalhe": {
  "motivo": "assinatura invalida: a mensagem foi alterada ou nao foi assinada por uma API conhecida",
  "montante_centimos": 99999900,
  "utilizador": "ana"
 }
}{
 "transferencia_id": "ec8cf347-2e68-450f-9c9f-5a37140dbd51",
 "data_utc": "2026-11-19T00:17:35.384+00:00",
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
