# Cenario 8: Queda de uma instancia da API e utilizacao da outra

**Resultado: PASSOU** (5/5 verificacoes, 24.1 s, executado em 2026-11-19 02:17:13)

**Objectivo:** Com api-1 parada, o cliente passa para api-2. O token emitido antes continua valido porque api-2 o valida localmente com a chave publica.

## Procedimento executado

1. `02:16:50` Com as duas instancias activas, respondeu api-1
2. `02:16:50` docker compose stop api-1
3. `02:17:03` docker compose start api-1

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
      "id": "7d6d42c3-6c02-48df-831a-70688d76239b",
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
      "chave_idempotencia": "cli-c59a8e2e-908c-4f25-9cc1-f9b32e3f0f37",
      "instancia_api": "api-2",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-7d6d42c3-6c02-48df-831a-70688d76239b-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-7d6d42c3-6c02-48df-831a-70688d76239b-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T00:17:02.748067+00:00",
      "decidida_em": "2026-11-19T00:17:03.339170+00:00",
      "concluida_em": "2026-11-19T00:17:03.789233+00:00",
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
