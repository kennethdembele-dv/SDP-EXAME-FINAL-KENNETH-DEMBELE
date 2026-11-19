# Cenario 1: Transferencia bem-sucedida entre Europa e America

**Resultado: PASSOU** (8/8 verificacoes, 7.8 s, executado em 2026-11-19 03:01:39)

**Objectivo:** Transferir 125.50 EUR de EU-1001 (no Europa) para US-2001 (no America) com 2PC.

**Dois computadores:** Localmente os dois nos sao contentores no mesmo PC. Com distribuido/ o no Europa corre no PC A e o no America no PC B; o procedimento e o mesmo.

## Procedimento executado

1. `03:01:33` ana autentica-se em https://localhost:8000 e envia POST /api/v1/transferencias a api-1
2. `03:01:38` Consultar o estado (GET /api/v1/transferencias/{id}) ate o banco parceiro confirmar

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1001 | 5 000.00 | 4 874.50 |
| US-2001 | 3 000.00 | 3 125.50 |

## Resposta da API (HTTP 201)

```
{
  "id": "2b560500-48c7-4e65-8450-70bc3ea6db96",
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
  "chave_idempotencia": "c01-0051f3b4-ba12-4562-b139-5b2632652d89",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-2b560500-48c7-4e65-8450-70bc3ea6db96-america",
      "estado": "CONFIRMADO"
    },
    {
      "no": "europa",
      "gid": "gs-2b560500-48c7-4e65-8450-70bc3ea6db96-europa",
      "estado": "CONFIRMADO"
    }
  ],
  "pendente_em": [],
  "parceiro": {
    "estado": "POR_ENVIAR",
    "referencia": null
  },
  "criada_em": "2026-11-19T01:01:33.708739+00:00",
  "decidida_em": "2026-11-19T01:01:34.181438+00:00",
  "concluida_em": "2026-11-19T01:01:34.572133+00:00",
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
01:01:33.708  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 12550 centimos
01:01:33.891  PREPARADO                europa: PREPARE TRANSACTION 'gs-2b560500-48c7-4e65-8450-70bc3ea6db96-europa'
01:01:34.086  PREPARADO                america: PREPARE TRANSACTION 'gs-2b560500-48c7-4e65-8450-70bc3ea6db96-america'
01:01:34.181  DECISAO_COMMIT           todos os participantes prepararam
01:01:34.434  CONFIRMADO               america: COMMIT PREPARED 'gs-2b560500-48c7-4e65-8450-70bc3ea6db96-america'
01:01:34.459  CONFIRMADO               europa: COMMIT PREPARED 'gs-2b560500-48c7-4e65-8450-70bc3ea6db96-europa'
01:01:34.618  CONCLUIDA                decisao aplicada em todos os participantes
01:01:35.779  PARCEIRO_CONFIRMOU       referencia BP-000001 (HTTP 201)
```

## Comandos 2PC nos logs dos participantes PostgreSQL

```
statement: PREPARE TRANSACTION 'gs-2b560500-48c7-4e65-8450-70bc3ea6db96-europa'
statement: COMMIT PREPARED 'gs-2b560500-48c7-4e65-8450-70bc3ea6db96-europa'
statement: PREPARE TRANSACTION 'gs-2b560500-48c7-4e65-8450-70bc3ea6db96-america'
statement: COMMIT PREPARED 'gs-2b560500-48c7-4e65-8450-70bc3ea6db96-america'
```

## Estado final da transferencia

```
{
  "id": "2b560500-48c7-4e65-8450-70bc3ea6db96",
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
  "chave_idempotencia": "c01-0051f3b4-ba12-4562-b139-5b2632652d89",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-2b560500-48c7-4e65-8450-70bc3ea6db96-america",
      "estado": "CONFIRMADO"
    },
    {
      "no": "europa",
      "gid": "gs-2b560500-48c7-4e65-8450-70bc3ea6db96-europa",
      "estado": "CONFIRMADO"
    }
  ],
  "pendente_em": [],
  "parceiro": {
    "estado": "CONFIRMADA",
    "referencia": "BP-000001"
  },
  "criada_em": "2026-11-19T01:01:33.708739+00:00",
  "decidida_em": "2026-11-19T01:01:34.181438+00:00",
  "concluida_em": "2026-11-19T01:01:34.572133+00:00",
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
