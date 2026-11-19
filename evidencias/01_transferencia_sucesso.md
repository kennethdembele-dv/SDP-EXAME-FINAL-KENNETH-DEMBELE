# Cenario 1: Transferencia bem-sucedida entre Europa e America

**Resultado: PASSOU** (8/8 verificacoes, 7.2 s, executado em 2026-11-19 02:13:41)

**Objectivo:** Transferir 125.50 EUR de EU-1001 (no Europa) para US-2001 (no America) com 2PC.

**Dois computadores:** Localmente os dois nos sao contentores no mesmo PC. Com distribuido/ o no Europa corre no PC A e o no America no PC B; o procedimento e o mesmo.

## Procedimento executado

1. `02:13:36` ana autentica-se em https://localhost:8000 e envia POST /api/v1/transferencias a api-1
2. `02:13:41` Consultar o estado (GET /api/v1/transferencias/{id}) ate o banco parceiro confirmar

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1001 | 5 000.00 | 4 874.50 |
| US-2001 | 3 000.00 | 3 125.50 |

## Resposta da API (HTTP 201)

```
{
  "id": "05948f69-7ede-4341-82e2-bfd2846bd6de",
  "estado": "CONCLUIDA",
  "explicacao": "confirmada em todos os participantes: um debito e um credito",
  "decisao": "COMMIT",
  "codigo_erro": null,
  "motivo": null,
  "conta_origem": "EU-1001",
  "conta_destino": "US-2001",
  "montante": "125.50",
  "montante_centimos": 12550,
  "moeda": "EUR",
  "utilizador": "ana",
  "chave_idempotencia": "c01-faff139f-6174-42cd-b070-55b5ae14398f",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-05948f69-7ede-4341-82e2-bfd2846bd6de-america",
      "estado": "CONFIRMADO"
    },
    {
      "no": "europa",
      "gid": "gs-05948f69-7ede-4341-82e2-bfd2846bd6de-europa",
      "estado": "CONFIRMADO"
    }
  ],
  "pendente_em": [],
  "parceiro": {
    "estado": "POR_ENVIAR",
    "referencia": null
  },
  "criada_em": "2026-11-19T00:13:36.214130+00:00",
  "decidida_em": "2026-11-19T00:13:36.634115+00:00",
  "concluida_em": "2026-11-19T00:13:36.973605+00:00",
  "repetido": false
}
```

## Movimentos desta transferencia nos dois nos

```
('europa', 'DEBITO', 'EU-1001', 12550)
('america', 'CREDITO', 'US-2001', 12550)
```

## Diario do coordenador (tabela eventos)

```
00:13:36.214  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 12550 centimos
00:13:36.410  PREPARADO                europa: PREPARE TRANSACTION 'gs-05948f69-7ede-4341-82e2-bfd2846bd6de-europa'
00:13:36.541  PREPARADO                america: PREPARE TRANSACTION 'gs-05948f69-7ede-4341-82e2-bfd2846bd6de-america'
00:13:36.634  DECISAO_COMMIT           todos os participantes prepararam
00:13:36.874  CONFIRMADO               america: COMMIT PREPARED 'gs-05948f69-7ede-4341-82e2-bfd2846bd6de-america'
00:13:36.903  CONFIRMADO               europa: COMMIT PREPARED 'gs-05948f69-7ede-4341-82e2-bfd2846bd6de-europa'
00:13:37.014  CONCLUIDA                decisao aplicada em todos os participantes
00:13:38.057  PARCEIRO_CONFIRMOU       referencia BP-000001 (HTTP 201)
```

## Comandos 2PC nos logs dos participantes PostgreSQL

```
statement: PREPARE TRANSACTION 'gs-05948f69-7ede-4341-82e2-bfd2846bd6de-europa'
statement: COMMIT PREPARED 'gs-05948f69-7ede-4341-82e2-bfd2846bd6de-europa'
statement: PREPARE TRANSACTION 'gs-05948f69-7ede-4341-82e2-bfd2846bd6de-america'
statement: COMMIT PREPARED 'gs-05948f69-7ede-4341-82e2-bfd2846bd6de-america'
```

## Estado final da transferencia

```
{
  "id": "05948f69-7ede-4341-82e2-bfd2846bd6de",
  "estado": "CONCLUIDA",
  "explicacao": "confirmada em todos os participantes: um debito e um credito",
  "decisao": "COMMIT",
  "codigo_erro": null,
  "motivo": null,
  "conta_origem": "EU-1001",
  "conta_destino": "US-2001",
  "montante": "125.50",
  "montante_centimos": 12550,
  "moeda": "EUR",
  "utilizador": "ana",
  "chave_idempotencia": "c01-faff139f-6174-42cd-b070-55b5ae14398f",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-05948f69-7ede-4341-82e2-bfd2846bd6de-america",
      "estado": "CONFIRMADO"
    },
    {
      "no": "europa",
      "gid": "gs-05948f69-7ede-4341-82e2-bfd2846bd6de-europa",
      "estado": "CONFIRMADO"
    }
  ],
  "pendente_em": [],
  "parceiro": {
    "estado": "CONFIRMADA",
    "referencia": "BP-000001"
  },
  "criada_em": "2026-11-19T00:13:36.214130+00:00",
  "decidida_em": "2026-11-19T00:13:36.634115+00:00",
  "concluida_em": "2026-11-19T00:13:36.973605+00:00",
  "repetido": false
}
```

## Verificacoes

- [x] HTTP 201 e estado CONCLUIDA
- [x] EU-1001 debitada em 125.50
- [x] US-2001 creditada em 125.50
- [x] total das duas contas conservado
- [x] exactamente um DEBITO (europa) e um CREDITO (america)
- [x] os dois participantes executaram PREPARE TRANSACTION e COMMIT PREPARED
- [x] confirmada pelo banco parceiro (Java) com referencia BP-xxxxxx
- [x] nenhuma transaccao preparada ficou por resolver
