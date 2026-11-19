# Cenario 5: Falha de um participante antes e durante a preparacao

**Resultado: PASSOU** (9/9 verificacoes, 39.1 s, executado em 2026-11-19 03:03:15)

**Objectivo:** (a) O no Europa esta em baixo quando chega uma transferencia US-2001 -> EU-1001: o primeiro participante falha, nenhum prepara e a decisao e ABORT. (b) O no America cai depois de o Europa ja ter preparado (PREPARE TRANSACTION): o Europa faz ROLLBACK PREPARED. Nenhum saldo muda.

**Dois computadores:** Com dois PCs pode desligar-se o cabo/Wi-Fi do PC B em vez de parar o contentor.

## Procedimento executado

1. `03:02:38` (a) docker compose stop db-europa; carlos envia 12.00 de US-2001 para EU-1001
2. `03:02:43` (a) docker compose start db-europa
3. `03:02:50` (b) Pausa de laboratorio de 8 s antes de preparar no America
4. `03:02:52` (b) ana envia 15.00 de EU-1001 para US-2001 (em segundo plano)
5. `03:02:53` (b) docker compose stop db-america (queda do no America)
6. `03:03:06` (b) docker compose start db-america

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
    "id": "d7196ce9-ef0f-4dd0-be18-80d32c2d0b63",
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
    "chave_idempotencia": "c05a-6698f403-c7ba-4b5b-aa33-e726ee39fa36",
    "instancia_api": "api-1",
    "participantes": [
      {
        "no": "america",
        "gid": "gs-d7196ce9-ef0f-4dd0-be18-80d32c2d0b63-america",
        "estado": "POR_PREPARAR"
      },
      {
        "no": "europa",
        "gid": "gs-d7196ce9-ef0f-4dd0-be18-80d32c2d0b63-europa",
        "estado": "NAO_PREPARADO"
      }
    ],
    "pendente_em": [],
    "parceiro": {
      "estado": "NAO_APLICAVEL",
      "referencia": null
    },
    "criada_em": "2026-11-19T01:02:39.218471+00:00",
    "decidida_em": "2026-11-19T01:02:42.706163+00:00",
    "concluida_em": "2026-11-19T01:02:42.871634+00:00",
    "repetido": false
  }
}
```

## (b) pg_prepared_xacts durante a pausa

```
{
  "europa": [
    "gs-0a912019-fbc7-42b0-b95d-f23c1bd4278c-europa"
  ],
  "america": []
}
```

## (b) Resposta da API (HTTP 503)

```
{
  "id": "0a912019-fbc7-42b0-b95d-f23c1bd4278c",
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
  "chave_idempotencia": "c05-092f024b-47ef-45c6-ad31-e9ea73b80a9f",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-0a912019-fbc7-42b0-b95d-f23c1bd4278c-america",
      "estado": "NAO_PREPARADO"
    },
    {
      "no": "europa",
      "gid": "gs-0a912019-fbc7-42b0-b95d-f23c1bd4278c-europa",
      "estado": "DESFEITO"
    }
  ],
  "pendente_em": [],
  "parceiro": {
    "estado": "NAO_APLICAVEL",
    "referencia": null
  },
  "criada_em": "2026-11-19T01:02:52.881597+00:00",
  "decidida_em": "2026-11-19T01:03:04.780208+00:00",
  "concluida_em": "2026-11-19T01:03:05.018439+00:00",
  "repetido": false
}
```

## (b) Diario do coordenador

```
01:02:52.881  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 1500 centimos
01:02:53.242  PREPARADO                europa: PREPARE TRANSACTION 'gs-0a912019-fbc7-42b0-b95d-f23c1bd4278c-europa'
01:02:53.315  PAUSA_LABORATORIO        antes_preparar_america: 8.0 s
01:03:04.710  SEM_RESPOSTA_PREPARACAO  america: OperationalError (estado NAO_PREPARADO)
01:03:04.780  DECISAO_ABORT            o no america nao respondeu durante a preparacao
01:03:04.964  DESFEITO                 europa: ROLLBACK PREPARED 'gs-0a912019-fbc7-42b0-b95d-f23c1bd4278c-europa'
01:03:05.050  ABORTADA                 decisao aplicada em todos os participantes
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
