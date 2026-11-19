# Cenario 5: Falha de um participante antes e durante a preparacao

**Resultado: PASSOU** (9/9 verificacoes, 38.5 s, executado em 2026-11-19 02:23:56)

**Objectivo:** (a) O no Europa esta em baixo quando chega uma transferencia US-2001 -> EU-1001: o primeiro participante falha, nenhum prepara e a decisao e ABORT. (b) O no America cai depois de o Europa ja ter preparado (PREPARE TRANSACTION): o Europa faz ROLLBACK PREPARED. Nenhum saldo muda.

**Dois computadores:** Com dois PCs pode desligar-se o cabo/Wi-Fi do PC B em vez de parar o contentor.

## Procedimento executado

1. `02:23:19` (a) docker compose stop db-europa; carlos envia 12.00 de US-2001 para EU-1001
2. `02:23:25` (a) docker compose start db-europa
3. `02:23:31` (b) Pausa de laboratorio de 8 s antes de preparar no America
4. `02:23:33` (b) ana envia 15.00 de EU-1001 para US-2001 (em segundo plano)
5. `02:23:35` (b) docker compose stop db-america (queda do no America)
6. `02:23:47` (b) docker compose start db-america

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1001 | 4 874.50 | 4 874.50 |
| US-2001 | 3 425.50 | 3 425.50 |

## (a) Resposta com o no Europa em baixo antes da preparacao

```
{
  "http": 503,
  "instancia": "api-1",
  "corpo": {
    "id": "fbe6b1e0-c2ed-4ced-a4a0-eaa60f52396b",
    "estado": "ABORTADA",
    "explicacao": "abortada em todos os participantes: nenhum saldo foi alterado",
    "decisao": "ABORT",
    "codigo_erro": "NO_INDISPONIVEL",
    "motivo": "o no europa nao respondeu durante a preparacao",
    "conta_origem": "US-2001",
    "conta_destino": "EU-1001",
    "montante": "12.00",
    "montante_centimos": 1200,
    "moeda": "EUR",
    "utilizador": "carlos",
    "chave_idempotencia": "c05a-ad69036e-12bc-48cb-a141-702e3b016039",
    "instancia_api": "api-1",
    "participantes": [
      {
        "no": "america",
        "gid": "gs-fbe6b1e0-c2ed-4ced-a4a0-eaa60f52396b-america",
        "estado": "POR_PREPARAR"
      },
      {
        "no": "europa",
        "gid": "gs-fbe6b1e0-c2ed-4ced-a4a0-eaa60f52396b-europa",
        "estado": "NAO_PREPARADO"
      }
    ],
    "pendente_em": [],
    "parceiro": {
      "estado": "NAO_APLICAVEL",
      "referencia": null
    },
    "criada_em": "2026-11-19T00:23:20.515813+00:00",
    "decidida_em": "2026-11-19T00:23:24.024583+00:00",
    "concluida_em": "2026-11-19T00:23:24.151432+00:00",
    "repetido": false
  }
}
```

## (b) pg_prepared_xacts durante a pausa

```
{
  "europa": [
    "gs-7acead8d-8a78-47e6-badd-49841a714ecb-europa"
  ],
  "america": []
}
```

## (b) Resposta da API (HTTP 503)

```
{
  "id": "7acead8d-8a78-47e6-badd-49841a714ecb",
  "estado": "ABORTADA",
  "explicacao": "abortada em todos os participantes: nenhum saldo foi alterado",
  "decisao": "ABORT",
  "codigo_erro": "NO_INDISPONIVEL",
  "motivo": "o no america nao respondeu durante a preparacao",
  "conta_origem": "EU-1001",
  "conta_destino": "US-2001",
  "montante": "15.00",
  "montante_centimos": 1500,
  "moeda": "EUR",
  "utilizador": "ana",
  "chave_idempotencia": "c05-344cfc33-698a-42d9-bfa7-828e5b5cc03e",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-7acead8d-8a78-47e6-badd-49841a714ecb-america",
      "estado": "NAO_PREPARADO"
    },
    {
      "no": "europa",
      "gid": "gs-7acead8d-8a78-47e6-badd-49841a714ecb-europa",
      "estado": "DESFEITO"
    }
  ],
  "pendente_em": [],
  "parceiro": {
    "estado": "NAO_APLICAVEL",
    "referencia": null
  },
  "criada_em": "2026-11-19T00:23:33.916202+00:00",
  "decidida_em": "2026-11-19T00:23:45.847474+00:00",
  "concluida_em": "2026-11-19T00:23:46.097347+00:00",
  "repetido": false
}
```

## (b) Diario do coordenador

```
00:23:33.916  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 1500 centimos
00:23:34.311  PREPARADO                europa: PREPARE TRANSACTION 'gs-7acead8d-8a78-47e6-badd-49841a714ecb-europa'
00:23:34.390  PAUSA_LABORATORIO        antes_preparar_america: 8.0 s
00:23:45.794  SEM_RESPOSTA_PREPARACAO  america: OperationalError (estado NAO_PREPARADO)
00:23:45.847  DECISAO_ABORT            o no america nao respondeu durante a preparacao
00:23:46.033  DESFEITO                 europa: ROLLBACK PREPARED 'gs-7acead8d-8a78-47e6-badd-49841a714ecb-europa'
00:23:46.128  ABORTADA                 decisao aplicada em todos os participantes
```

## Verificacoes

- [x] (a) HTTP 503, ABORTADA, NO_INDISPONIVEL
- [x] (a) nenhum participante preparou (europa NAO_PREPARADO, america POR_PREPARAR)
- [x] (a) America sem transaccao preparada e US-2001 sem alteracao
- [x] (b) o Europa ja tem a transaccao preparada
- [x] (b) HTTP 503 e estado ABORTADA com codigo NO_INDISPONIVEL
- [x] (b) Europa: transaccao preparada desfeita (ROLLBACK PREPARED)
- [x] (b) EU-1001 sem alteracao com o America em baixo
- [x] saldos inalterados nos dois nos
- [x] nenhum movimento e nenhuma transaccao preparada
