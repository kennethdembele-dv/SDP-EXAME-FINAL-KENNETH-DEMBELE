# Cenario 4: Repeticao de um pedido com a mesma chave de idempotencia

**Resultado: PASSOU** (8/8 verificacoes, 9.5 s, executado em 2026-11-19 03:02:29)

**Objectivo:** O mesmo pedido enviado a api-1 e repetido em api-2 com a mesma Idempotency-Key produz uma so transferencia; a mesma chave com outro montante e recusada.

## Procedimento executado

1. `03:02:20` POST a api-1 com Idempotency-Key c04-46db5d22-d730-41c3-8a67-4b55889296b5
2. `03:02:22` Repetir o mesmo pedido em api-2 (como faria um cliente depois de um timeout)
3. `03:02:22` Reutilizar a chave com outro montante (20.00)
4. `03:02:25` 5 pedidos SIMULTANEOS com a mesma chave c04-paralelo-aa6ba48d-91d1-4dd7-9bf9-d8f7b5aeba12 (api-1 e api-2 alternadas)

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
      "id": "98bd6157-17cf-410e-bfdc-511dbfcf8696",
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
      "chave_idempotencia": "c04-46db5d22-d730-41c3-8a67-4b55889296b5",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-98bd6157-17cf-410e-bfdc-511dbfcf8696-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-98bd6157-17cf-410e-bfdc-511dbfcf8696-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T01:02:21.185298+00:00",
      "decidida_em": "2026-11-19T01:02:21.628818+00:00",
      "concluida_em": "2026-11-19T01:02:21.932504+00:00",
      "repetido": false
    }
  },
  "repeticao (api-2)": {
    "http": 200,
    "instancia": "api-2",
    "corpo": {
      "id": "98bd6157-17cf-410e-bfdc-511dbfcf8696",
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
      "chave_idempotencia": "c04-46db5d22-d730-41c3-8a67-4b55889296b5",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-98bd6157-17cf-410e-bfdc-511dbfcf8696-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-98bd6157-17cf-410e-bfdc-511dbfcf8696-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "CONFIRMADA",
        "referencia": "BP-000008"
      },
      "criada_em": "2026-11-19T01:02:21.185298+00:00",
      "decidida_em": "2026-11-19T01:02:21.628818+00:00",
      "concluida_em": "2026-11-19T01:02:21.932504+00:00",
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
(202, '09babb89-5df3-45a4-a626-7bd0be11818c', 'INICIADA')
(202, '09babb89-5df3-45a4-a626-7bd0be11818c', 'INICIADA')
(202, '09babb89-5df3-45a4-a626-7bd0be11818c', 'INICIADA')
(201, '09babb89-5df3-45a4-a626-7bd0be11818c', 'CONCLUIDA')
(202, '09babb89-5df3-45a4-a626-7bd0be11818c', 'INICIADA')
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
