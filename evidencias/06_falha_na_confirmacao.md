# Cenario 6: Falha durante a confirmacao e posterior recuperacao

**Resultado: PASSOU** (12/12 verificacoes, 81.2 s, executado em 2026-11-19 03:04:44)

**Objectivo:** (a) A decisao COMMIT ja esta gravada e o Europa ja confirmou quando o America cai. A transferencia fica COMMIT_DECIDIDO (pendente no America). A transaccao preparada sobrevive ao reinicio do PostgreSQL e a recuperacao conclui o COMMIT. (b) Falha de rede: o America fica sem responder (processos congelados com docker compose pause, como numa particao); o COMMIT esgota o tempo, a decisao nao muda e a transferencia conclui quando a rede volta.

**Dois computadores:** Com dois PCs pode desligar-se a rede do PC B durante a pausa.

## Procedimento executado

1. `03:03:24` (a) Pausa de laboratorio de 10 s antes do COMMIT PREPARED no America
2. `03:03:26` (a) ana envia 20.00 de EU-1001 para US-2001 (em segundo plano)
3. `03:03:31` docker compose stop db-america (o America tem a transaccao preparada)
4. `03:03:41` docker compose start db-america (a recuperacao tem uma pausa de 25 s para se observar o no)
5. `03:03:48` Esperar que o ciclo de recuperacao do coordenador repita o COMMIT PREPARED
6. `03:04:11` (b) Pausa de 6 s antes do COMMIT no America; ana envia 8.00 de EU-1001 para US-2001
7. `03:04:14` (b) docker compose pause db-america (o no deixa de responder, sem perder ligacao de rede nem dados)
8. `03:04:34` (b) docker compose unpause db-america (a rede volta)

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
  "id": "ab96e04a-ec39-4725-8b8b-37aadbfbeda7",
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
  "chave_idempotencia": "c06-c5e66c91-ceed-4cde-b873-f4a0e4e18205",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-ab96e04a-ec39-4725-8b8b-37aadbfbeda7-america",
      "estado": "PREPARADO"
    },
    {
      "no": "europa",
      "gid": "gs-ab96e04a-ec39-4725-8b8b-37aadbfbeda7-europa",
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
  "criada_em": "2026-11-19T01:03:26.937060+00:00",
  "decidida_em": "2026-11-19T01:03:27.421490+00:00",
  "concluida_em": null,
  "repetido": false
}
```

## pg_prepared_xacts no America logo apos o reinicio

```
{
  "europa": [],
  "america": [
    "gs-ab96e04a-ec39-4725-8b8b-37aadbfbeda7-america"
  ]
}
```

## Diario do coordenador

```
01:03:26.937  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 2000 centimos
01:03:27.205  PREPARADO                europa: PREPARE TRANSACTION 'gs-ab96e04a-ec39-4725-8b8b-37aadbfbeda7-europa'
01:03:27.319  PREPARADO                america: PREPARE TRANSACTION 'gs-ab96e04a-ec39-4725-8b8b-37aadbfbeda7-america'
01:03:27.421  DECISAO_COMMIT           todos os participantes prepararam
01:03:27.659  PAUSA_LABORATORIO        antes_commit_america: 10.0 s
01:03:27.853  CONFIRMADO               europa: COMMIT PREPARED 'gs-ab96e04a-ec39-4725-8b8b-37aadbfbeda7-europa'
01:03:41.048  DECISAO_PENDENTE         america: OperationalError; a decisao COMMIT mantem-se e sera repetida
01:03:43.073  PAUSA_LABORATORIO        antes_commit_america: 25.0 s
01:04:08.213  CONFIRMADO               america: COMMIT PREPARED 'gs-ab96e04a-ec39-4725-8b8b-37aadbfbeda7-america'
01:04:08.333  CONCLUIDA                decisao aplicada em todos os participantes
01:04:08.761  PARCEIRO_CONFIRMOU       referencia BP-000010 (HTTP 201)
```

## (b) Resposta da API com o America sem responder

```
{
  "http": 202,
  "instancia": "api-1",
  "corpo": {
    "id": "e12f62f8-f6d6-481b-a369-550bbd6a5d89",
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
    "chave_idempotencia": "c06b-d7630099-74fb-41f0-a7ec-40da30a37aac",
    "instancia_api": "api-1",
    "participantes": [
      {
        "no": "america",
        "gid": "gs-e12f62f8-f6d6-481b-a369-550bbd6a5d89-america",
        "estado": "PREPARADO"
      },
      {
        "no": "europa",
        "gid": "gs-e12f62f8-f6d6-481b-a369-550bbd6a5d89-europa",
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
    "criada_em": "2026-11-19T01:04:13.865113+00:00",
    "decidida_em": "2026-11-19T01:04:14.350522+00:00",
    "concluida_em": null,
    "repetido": false
  }
}
```

## (b) Diario do coordenador

```
01:04:13.865  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 800 centimos
01:04:14.111  PREPARADO                europa: PREPARE TRANSACTION 'gs-e12f62f8-f6d6-481b-a369-550bbd6a5d89-europa'
01:04:14.264  PREPARADO                america: PREPARE TRANSACTION 'gs-e12f62f8-f6d6-481b-a369-550bbd6a5d89-america'
01:04:14.350  DECISAO_COMMIT           todos os participantes prepararam
01:04:14.502  PAUSA_LABORATORIO        antes_commit_america: 6.0 s
01:04:14.610  CONFIRMADO               europa: COMMIT PREPARED 'gs-e12f62f8-f6d6-481b-a369-550bbd6a5d89-europa'
01:04:25.557  DECISAO_PENDENTE         america: TimeoutError; a decisao COMMIT mantem-se e sera repetida
01:04:34.005  DECISAO_PENDENTE         america: TimeoutError; a decisao COMMIT mantem-se e sera repetida
01:04:39.921  CONFIRMADO               america: COMMIT PREPARED 'gs-e12f62f8-f6d6-481b-a369-550bbd6a5d89-america'
01:04:40.038  CONCLUIDA                decisao aplicada em todos os participantes
01:04:40.363  PARCEIRO_CONFIRMOU       referencia BP-000011 (HTTP 201)
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
