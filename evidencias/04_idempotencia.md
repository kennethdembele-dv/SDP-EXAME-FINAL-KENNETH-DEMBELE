# Cenario 4: Repeticao de um pedido com a mesma chave de idempotencia

**Resultado: PASSOU** (8/8 verificacoes, 8.9 s, executado em 2026-11-19 02:23:18)

**Objectivo:** O mesmo pedido enviado a api-1 e repetido em api-2 com a mesma Idempotency-Key produz uma so transferencia; a mesma chave com outro montante e recusada.

## Procedimento executado

1. `02:23:09` POST a api-1 com Idempotency-Key c04-46dbbfc1-7ee8-461b-88d0-c7f66a5a2fae
2. `02:23:11` Repetir o mesmo pedido em api-2 (como faria um cliente depois de um timeout)
3. `02:23:11` Reutilizar a chave com outro montante (20.00)
4. `02:23:13` 5 pedidos SIMULTANEOS com a mesma chave c04-paralelo-a26a1671-8bca-441d-a79f-a6eff786731a (api-1 e api-2 alternadas)

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
      "id": "e4677e18-ae43-4c3d-b8b0-18f442f44c83",
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
      "chave_idempotencia": "c04-46dbbfc1-7ee8-461b-88d0-c7f66a5a2fae",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-e4677e18-ae43-4c3d-b8b0-18f442f44c83-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-e4677e18-ae43-4c3d-b8b0-18f442f44c83-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T00:23:10.401324+00:00",
      "decidida_em": "2026-11-19T00:23:10.849233+00:00",
      "concluida_em": "2026-11-19T00:23:11.213643+00:00",
      "repetido": false
    }
  },
  "repeticao (api-2)": {
    "http": 200,
    "instancia": "api-2",
    "corpo": {
      "id": "e4677e18-ae43-4c3d-b8b0-18f442f44c83",
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
      "chave_idempotencia": "c04-46dbbfc1-7ee8-461b-88d0-c7f66a5a2fae",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-e4677e18-ae43-4c3d-b8b0-18f442f44c83-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-e4677e18-ae43-4c3d-b8b0-18f442f44c83-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "CONFIRMADA",
        "referencia": "BP-000008"
      },
      "criada_em": "2026-11-19T00:23:10.401324+00:00",
      "decidida_em": "2026-11-19T00:23:10.849233+00:00",
      "concluida_em": "2026-11-19T00:23:11.213643+00:00",
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
(202, '93397ad8-a5c9-4a81-a5b1-ea96f6232959', 'INICIADA')
(201, '93397ad8-a5c9-4a81-a5b1-ea96f6232959', 'CONCLUIDA')
(202, '93397ad8-a5c9-4a81-a5b1-ea96f6232959', 'INICIADA')
(202, '93397ad8-a5c9-4a81-a5b1-ea96f6232959', 'INICIADA')
(202, '93397ad8-a5c9-4a81-a5b1-ea96f6232959', 'INICIADA')
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
