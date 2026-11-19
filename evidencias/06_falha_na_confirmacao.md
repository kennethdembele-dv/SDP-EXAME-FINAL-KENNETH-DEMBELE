# Cenario 6: Falha durante a confirmacao e posterior recuperacao

**Resultado: PASSOU** (12/12 verificacoes, 84.0 s, executado em 2026-11-19 02:25:20)

**Objectivo:** (a) A decisao COMMIT ja esta gravada e o Europa ja confirmou quando o America cai. A transferencia fica COMMIT_DECIDIDO (pendente no America). A transaccao preparada sobrevive ao reinicio do PostgreSQL e a recuperacao conclui o COMMIT. (b) Falha de rede: o America fica sem responder (processos congelados com docker compose pause, como numa particao); o COMMIT esgota o tempo, a decisao nao muda e a transferencia conclui quando a rede volta.

**Dois computadores:** Com dois PCs pode desligar-se a rede do PC B durante a pausa.

## Procedimento executado

1. `02:23:57` (a) Pausa de laboratorio de 10 s antes do COMMIT PREPARED no America
2. `02:23:59` (a) ana envia 20.00 de EU-1001 para US-2001 (em segundo plano)
3. `02:24:04` docker compose stop db-america (o America tem a transaccao preparada)
4. `02:24:16` docker compose start db-america (a recuperacao tem uma pausa de 25 s para se observar o no)
5. `02:24:22` Esperar que o ciclo de recuperacao do coordenador repita o COMMIT PREPARED
6. `02:24:47` (b) Pausa de 6 s antes do COMMIT no America; ana envia 8.00 de EU-1001 para US-2001
7. `02:24:50` (b) docker compose pause db-america (o no deixa de responder, sem perder ligacao de rede nem dados)
8. `02:25:10` (b) docker compose unpause db-america (a rede volta)

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
  "id": "f3d829cb-ab88-4a78-87b0-86dd8013e9d3",
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
  "chave_idempotencia": "c06-ddda382a-3210-4556-b698-7fc83b8b2de6",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-f3d829cb-ab88-4a78-87b0-86dd8013e9d3-america",
      "estado": "PREPARADO"
    },
    {
      "no": "europa",
      "gid": "gs-f3d829cb-ab88-4a78-87b0-86dd8013e9d3-europa",
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
  "criada_em": "2026-11-19T00:23:59.894956+00:00",
  "decidida_em": "2026-11-19T00:24:00.548511+00:00",
  "concluida_em": null,
  "repetido": false
}
```

## pg_prepared_xacts no America logo apos o reinicio

```
{
  "europa": [],
  "america": [
    "gs-f3d829cb-ab88-4a78-87b0-86dd8013e9d3-america"
  ]
}
```

## Diario do coordenador

```
00:23:59.894  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 2000 centimos
00:24:00.308  PREPARADO                europa: PREPARE TRANSACTION 'gs-f3d829cb-ab88-4a78-87b0-86dd8013e9d3-europa'
00:24:00.442  PREPARADO                america: PREPARE TRANSACTION 'gs-f3d829cb-ab88-4a78-87b0-86dd8013e9d3-america'
00:24:00.548  DECISAO_COMMIT           todos os participantes prepararam
00:24:00.846  PAUSA_LABORATORIO        antes_commit_america: 10.0 s
00:24:00.970  CONFIRMADO               europa: COMMIT PREPARED 'gs-f3d829cb-ab88-4a78-87b0-86dd8013e9d3-europa'
00:24:15.755  DECISAO_PENDENTE         america: OperationalError; a decisao COMMIT mantem-se e sera repetida
00:24:17.645  PAUSA_LABORATORIO        antes_commit_america: 25.0 s
00:24:42.973  CONFIRMADO               america: COMMIT PREPARED 'gs-f3d829cb-ab88-4a78-87b0-86dd8013e9d3-america'
00:24:43.074  CONCLUIDA                decisao aplicada em todos os participantes
00:24:43.349  PARCEIRO_CONFIRMOU       referencia BP-000010 (HTTP 201)
```

## (b) Resposta da API com o America sem responder

```
{
  "http": 202,
  "instancia": "api-1",
  "corpo": {
    "id": "158efdd1-056e-48ea-bba5-2e1695a1409d",
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
    "chave_idempotencia": "c06b-e281103e-bafb-44c2-b85d-013b06cc82c8",
    "instancia_api": "api-1",
    "participantes": [
      {
        "no": "america",
        "gid": "gs-158efdd1-056e-48ea-bba5-2e1695a1409d-america",
        "estado": "PREPARADO"
      },
      {
        "no": "europa",
        "gid": "gs-158efdd1-056e-48ea-bba5-2e1695a1409d-europa",
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
    "criada_em": "2026-11-19T00:24:49.434619+00:00",
    "decidida_em": "2026-11-19T00:24:49.980176+00:00",
    "concluida_em": null,
    "repetido": false
  }
}
```

## (b) Diario do coordenador

```
00:24:49.434  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 800 centimos
00:24:49.723  PREPARADO                europa: PREPARE TRANSACTION 'gs-158efdd1-056e-48ea-bba5-2e1695a1409d-europa'
00:24:49.885  PREPARADO                america: PREPARE TRANSACTION 'gs-158efdd1-056e-48ea-bba5-2e1695a1409d-america'
00:24:49.980  DECISAO_COMMIT           todos os participantes prepararam
00:24:50.143  PAUSA_LABORATORIO        antes_commit_america: 6.0 s
00:24:50.290  CONFIRMADO               europa: COMMIT PREPARED 'gs-158efdd1-056e-48ea-bba5-2e1695a1409d-europa'
00:25:01.261  DECISAO_PENDENTE         america: TimeoutError; a decisao COMMIT mantem-se e sera repetida
00:25:08.635  DECISAO_PENDENTE         america: TimeoutError; a decisao COMMIT mantem-se e sera repetida
00:25:16.033  CONFIRMADO               america: COMMIT PREPARED 'gs-158efdd1-056e-48ea-bba5-2e1695a1409d-america'
00:25:16.136  CONCLUIDA                decisao aplicada em todos os participantes
00:25:16.796  PARCEIRO_CONFIRMOU       referencia BP-000011 (HTTP 201)
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
