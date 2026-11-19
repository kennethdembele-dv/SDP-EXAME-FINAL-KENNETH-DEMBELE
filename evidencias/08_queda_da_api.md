# Cenario 8: Queda de uma instancia da API e utilizacao da outra

**Resultado: PASSOU** (5/5 verificacoes, 23.4 s, executado em 2026-11-19 03:05:58)

**Objectivo:** Com api-1 parada, o cliente passa para api-2. O token emitido antes continua valido porque api-2 o valida localmente com a chave publica.

## Procedimento executado

1. `03:05:36` Com as duas instancias activas, respondeu api-1
2. `03:05:36` docker compose stop api-1
3. `03:05:49` docker compose start api-1

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1001 | 4 846.50 | 4 841.50 |
| US-2001 | 3 453.50 | 3 458.50 |

## Mensagens do cliente (failover)

```
[failover] https://localhost:8001 nao aceita ligacoes (ConnectError); a tentar a proxima instancia
[failover] https://localhost:8001 nao aceita ligacoes (ConnectError); a tentar a proxima instancia
```

## Respostas com api-1 em baixo

```
{
  "saldo": {
    "http": 200,
    "instancia": "api-2",
    "corpo": {
      "conta": "EU-1001",
      "saldo": "4846.50",
      "saldo_centimos": 484650,
      "moeda": "EUR",
      "no": "europa"
    }
  },
  "transferencia": {
    "http": 201,
    "instancia": "api-2",
    "corpo": {
      "id": "cc6f1627-cd8b-46d0-9edc-f52816c7a6e8",
      "estado": "CONCLUIDA",
      "explicacao": "confirmada em todos os participantes: um debito e um credito",
      "decisao": "COMMIT",
      "codigo_erro": null,
      "motivo": null,
      "conta_origem": "EU-1001",
      "conta_destino": "US-2001",
      "montante": "5.00",
      "montante_centimos": 500,
      "moeda": "EUR",
      "utilizador": "ana",
      "chave_idempotencia": "cli-727f7465-290b-4a5f-9988-b3745e0ad6ce",
      "instancia_api": "api-2",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-cc6f1627-cd8b-46d0-9edc-f52816c7a6e8-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-cc6f1627-cd8b-46d0-9edc-f52816c7a6e8-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T01:05:48.867999+00:00",
      "decidida_em": "2026-11-19T01:05:49.253441+00:00",
      "concluida_em": "2026-11-19T01:05:49.662141+00:00",
      "repetido": false
    }
  }
}
```

## Verificacoes

- [x] saldo respondido por api-2
- [x] transferencia concluida via api-2 (ordem assinada por api-2)
- [x] o token emitido antes da queda foi aceite por api-2 (sem novo login)
- [x] api-1 volta a responder
- [x] saldos mudaram so pela transferencia de 5.00
