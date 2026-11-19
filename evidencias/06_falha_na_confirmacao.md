# Cenario 6: Falha durante a confirmacao e posterior recuperacao

**Resultado: PASSOU** (12/12 verificacoes, 85.2 s, executado em 2026-11-19 02:16:16)

**Objectivo:** (a) A decisao COMMIT ja esta gravada e o Europa ja confirmou quando o America cai. A transferencia fica COMMIT_DECIDIDO (pendente no America). A transaccao preparada sobrevive ao reinicio do PostgreSQL e a recuperacao conclui o COMMIT. (b) Falha de rede: o America fica sem responder (processos congelados com docker compose pause, como numa particao); o COMMIT esgota o tempo, a decisao nao muda e a transferencia conclui quando a rede volta.

**Dois computadores:** Com dois PCs pode desligar-se a rede do PC B durante a pausa.

## Procedimento executado

1. `02:14:52` (a) Pausa de laboratorio de 10 s antes do COMMIT PREPARED no America
2. `02:14:54` (a) ana envia 20.00 de EU-1001 para US-2001 (em segundo plano)
3. `02:14:59` docker compose stop db-america (o America tem a transaccao preparada)
4. `02:15:09` docker compose start db-america (a recuperacao tem uma pausa de 25 s para se observar o no)
5. `02:15:16` Esperar que o ciclo de recuperacao do coordenador repita o COMMIT PREPARED
6. `02:15:40` (b) Pausa de 6 s antes do COMMIT no America; ana envia 8.00 de EU-1001 para US-2001
7. `02:15:43` (b) docker compose pause db-america (o no deixa de responder, sem perder ligacao de rede nem dados)
8. `02:16:03` (b) docker compose unpause db-america (a rede volta)

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois | final |
|---|---:|---:|---:|
| EU-1001 | 4 874.50 | 4 854.50 | 4 846.50 |
| US-2001 | 3 425.50 | 3 445.50 | 3 453.50 |

## Estado no coordenador durante a pausa

```
{
  "estado": "COMMIT_DECIDIDO",
  "decisao": "COMMIT",
  "codigo_erro": null,
  "parceiro": "NAO_APLICAVEL",
  "participantes": {
    "america": "PREPARADO",
    "europa": "CONFIRMADO"
  }
}
```

## Resposta da API (HTTP 202)

```
{
  "id": "8ca334da-7f8c-49a0-a7ff-a9fbf0c8f4da",
  "estado": "COMMIT_DECIDIDO",
  "explicacao": "decisao COMMIT gravada; falta aplica-la nos participantes pendentes (o credito/debito aparece quando o no responder; a recuperacao repete automaticamente)",
  "decisao": "COMMIT",
  "codigo_erro": null,
  "motivo": null,
  "conta_origem": "EU-1001",
  "conta_destino": "US-2001",
  "montante": "20.00",
  "montante_centimos": 2000,
  "moeda": "EUR",
  "utilizador": "ana",
  "chave_idempotencia": "c06-2fe2f24c-5db3-4a54-9992-9ec6afa16bab",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-8ca334da-7f8c-49a0-a7ff-a9fbf0c8f4da-america",
      "estado": "PREPARADO"
    },
    {
      "no": "europa",
      "gid": "gs-8ca334da-7f8c-49a0-a7ff-a9fbf0c8f4da-europa",
      "estado": "CONFIRMADO"
    }
  ],
  "pendente_em": [
    "america"
  ],
  "parceiro": {
    "estado": "NAO_APLICAVEL",
    "referencia": null
  },
  "criada_em": "2026-11-19T00:14:54.336098+00:00",
  "decidida_em": "2026-11-19T00:14:54.842014+00:00",
  "concluida_em": null,
  "repetido": false
}
```

## pg_prepared_xacts no America logo apos o reinicio

```
{
  "europa": [],
  "america": [
    "gs-8ca334da-7f8c-49a0-a7ff-a9fbf0c8f4da-america"
  ]
}
```

## Diario do coordenador

```
00:14:54.336  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 2000 centimos
00:14:54.559  PREPARADO                europa: PREPARE TRANSACTION 'gs-8ca334da-7f8c-49a0-a7ff-a9fbf0c8f4da-europa'
00:14:54.742  PREPARADO                america: PREPARE TRANSACTION 'gs-8ca334da-7f8c-49a0-a7ff-a9fbf0c8f4da-america'
00:14:54.842  DECISAO_COMMIT           todos os participantes prepararam
00:14:55.142  PAUSA_LABORATORIO        antes_commit_america: 10.0 s
00:14:55.272  CONFIRMADO               europa: COMMIT PREPARED 'gs-8ca334da-7f8c-49a0-a7ff-a9fbf0c8f4da-europa'
00:15:09.313  DECISAO_PENDENTE         america: OperationalError; a decisao COMMIT mantem-se e sera repetida
00:15:11.336  PAUSA_LABORATORIO        antes_commit_america: 25.0 s
00:15:36.512  CONFIRMADO               america: COMMIT PREPARED 'gs-8ca334da-7f8c-49a0-a7ff-a9fbf0c8f4da-america'
00:15:36.647  CONCLUIDA                decisao aplicada em todos os participantes
00:15:36.912  PARCEIRO_CONFIRMOU       referencia BP-000010 (HTTP 201)
```

## (b) Resposta da API com o America sem responder

```
{
  "http": 202,
  "instancia": "api-1",
  "corpo": {
    "id": "07477465-e8cc-4a01-8adf-ce8c7bc59a4e",
    "estado": "COMMIT_DECIDIDO",
    "explicacao": "decisao COMMIT gravada; falta aplica-la nos participantes pendentes (o credito/debito aparece quando o no responder; a recuperacao repete automaticamente)",
    "decisao": "COMMIT",
    "codigo_erro": null,
    "motivo": null,
    "conta_origem": "EU-1001",
    "conta_destino": "US-2001",
    "montante": "8.00",
    "montante_centimos": 800,
    "moeda": "EUR",
    "utilizador": "ana",
    "chave_idempotencia": "c06b-eb0fd4d2-cda2-43ff-b4f3-f7cc932a7ba1",
    "instancia_api": "api-1",
    "participantes": [
      {
        "no": "america",
        "gid": "gs-07477465-e8cc-4a01-8adf-ce8c7bc59a4e-america",
        "estado": "PREPARADO"
      },
      {
        "no": "europa",
        "gid": "gs-07477465-e8cc-4a01-8adf-ce8c7bc59a4e-europa",
        "estado": "CONFIRMADO"
      }
    ],
    "pendente_em": [
      "america"
    ],
    "parceiro": {
      "estado": "NAO_APLICAVEL",
      "referencia": null
    },
    "criada_em": "2026-11-19T00:15:42.350239+00:00",
    "decidida_em": "2026-11-19T00:15:43.104799+00:00",
    "concluida_em": null,
    "repetido": false
  }
}
```

## (b) Diario do coordenador

```
00:15:42.350  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 800 centimos
00:15:42.650  PREPARADO                europa: PREPARE TRANSACTION 'gs-07477465-e8cc-4a01-8adf-ce8c7bc59a4e-europa'
00:15:42.830  PREPARADO                america: PREPARE TRANSACTION 'gs-07477465-e8cc-4a01-8adf-ce8c7bc59a4e-america'
00:15:43.104  DECISAO_COMMIT           todos os participantes prepararam
00:15:43.344  PAUSA_LABORATORIO        antes_commit_america: 6.0 s
00:15:43.497  CONFIRMADO               europa: COMMIT PREPARED 'gs-07477465-e8cc-4a01-8adf-ce8c7bc59a4e-europa'
00:15:54.483  DECISAO_PENDENTE         america: TimeoutError; a decisao COMMIT mantem-se e sera repetida
00:16:02.165  DECISAO_PENDENTE         america: TimeoutError; a decisao COMMIT mantem-se e sera repetida
00:16:09.507  CONFIRMADO               america: COMMIT PREPARED 'gs-07477465-e8cc-4a01-8adf-ce8c7bc59a4e-america'
00:16:09.610  CONCLUIDA                decisao aplicada em todos os participantes
00:16:10.030  PARCEIRO_CONFIRMOU       referencia BP-000011 (HTTP 201)
```

## Verificacoes

- [x] HTTP 202, estado COMMIT_DECIDIDO, pendente no america
- [x] Europa ja debitou (a decisao COMMIT e definitiva)
- [x] a transaccao preparada sobreviveu ao reinicio do PostgreSQL
- [x] (a) estado final CONCLUIDA
- [x] (a) US-2001 creditada em 20.00
- [x] (a) total conservado
- [x] (a) um debito e um credito
- [x] (b) HTTP 202 COMMIT_DECIDIDO, pendente no america (o timeout nao mudou a decisao)
- [x] (b) durante a falha de rede a transferencia continua COMMIT_DECIDIDO
- [x] (b) o diario regista o COMMIT sem resposta (timeout) e a repeticao bem-sucedida
- [x] (b) um debito e um credito e total conservado
- [x] nenhuma transaccao preparada ficou por resolver
