# Cenario 4: Repeticao de um pedido com a mesma chave de idempotencia

**Resultado: PASSOU** (8/8 verificacoes, 13.2 s, executado em 2026-11-19 02:14:12)

**Objectivo:** O mesmo pedido enviado a api-1 e repetido em api-2 com a mesma Idempotency-Key produz uma so transferencia; a mesma chave com outro montante e recusada.

## Procedimento executado

1. `02:13:59` POST a api-1 com Idempotency-Key c04-82d4f05d-6847-4228-91cb-d6bd1972abb2
2. `02:14:01` Repetir o mesmo pedido em api-2 (como faria um cliente depois de um timeout)
3. `02:14:01` Reutilizar a chave com outro montante (20.00)
4. `02:14:03` 5 pedidos SIMULTANEOS com a mesma chave c04-paralelo-d8b4904b-0010-4568-8acd-ae0be0a384a4 (api-1 e api-2 alternadas)

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1002 | 1 500.00 | 1 490.00 |
| US-2002 | 800.00 | 810.00 |

## Respostas

```
{
  "primeiro (api-1)": {
    "http": 201,
    "instancia": "api-1",
    "corpo": {
      "id": "0512cf4f-5239-4e09-9fe8-e7584a2aced7",
      "estado": "CONCLUIDA",
      "explicacao": "confirmada em todos os participantes: um debito e um credito",
      "decisao": "COMMIT",
      "codigo_erro": null,
      "motivo": null,
      "conta_origem": "EU-1002",
      "conta_destino": "US-2002",
      "montante": "10.00",
      "montante_centimos": 1000,
      "moeda": "EUR",
      "utilizador": "ana",
      "chave_idempotencia": "c04-82d4f05d-6847-4228-91cb-d6bd1972abb2",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-0512cf4f-5239-4e09-9fe8-e7584a2aced7-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-0512cf4f-5239-4e09-9fe8-e7584a2aced7-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T00:14:00.126656+00:00",
      "decidida_em": "2026-11-19T00:14:00.620559+00:00",
      "concluida_em": "2026-11-19T00:14:00.943102+00:00",
      "repetido": false
    }
  },
  "repeticao (api-2)": {
    "http": 200,
    "instancia": "api-2",
    "corpo": {
      "id": "0512cf4f-5239-4e09-9fe8-e7584a2aced7",
      "estado": "CONCLUIDA",
      "explicacao": "confirmada em todos os participantes: um debito e um credito",
      "decisao": "COMMIT",
      "codigo_erro": null,
      "motivo": null,
      "conta_origem": "EU-1002",
      "conta_destino": "US-2002",
      "montante": "10.00",
      "montante_centimos": 1000,
      "moeda": "EUR",
      "utilizador": "ana",
      "chave_idempotencia": "c04-82d4f05d-6847-4228-91cb-d6bd1972abb2",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-0512cf4f-5239-4e09-9fe8-e7584a2aced7-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-0512cf4f-5239-4e09-9fe8-e7584a2aced7-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "CONFIRMADA",
        "referencia": "BP-000008"
      },
      "criada_em": "2026-11-19T00:14:00.126656+00:00",
      "decidida_em": "2026-11-19T00:14:00.620559+00:00",
      "concluida_em": "2026-11-19T00:14:00.943102+00:00",
      "repetido": true
    }
  },
  "chave reutilizada com 20.00": {
    "http": 409,
    "instancia": "api-1",
    "corpo": {
      "detail": "chave de idempotencia ja usada com dados diferentes"
    }
  }
}
```

## Pedidos simultaneos com a mesma chave (HTTP, id, estado)

```
(202, 'e0c58742-937e-481b-8f79-497ba59bc8b2', 'INICIADA')
(202, 'e0c58742-937e-481b-8f79-497ba59bc8b2', 'INICIADA')
(202, 'e0c58742-937e-481b-8f79-497ba59bc8b2', 'INICIADA')
(201, 'e0c58742-937e-481b-8f79-497ba59bc8b2', 'CONCLUIDA')
(202, 'e0c58742-937e-481b-8f79-497ba59bc8b2', 'INICIADA')
```

## Verificacoes

- [x] primeiro pedido: HTTP 201 CONCLUIDA
- [x] repeticao: HTTP 200, mesmo id, repetido=true
- [x] chave reutilizada com dados diferentes: HTTP 409
- [x] saldos alterados uma unica vez (10.00)
- [x] so um debito e um credito
- [x] todos os pedidos devolvem a mesma transferencia
- [x] o coordenador tem uma unica transferencia com esta chave
- [x] um debito e um credito para a transferencia paralela
