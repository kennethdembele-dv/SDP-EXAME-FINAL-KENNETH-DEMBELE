# Cenario 5: Falha de um participante antes e durante a preparacao

**Resultado: PASSOU** (9/9 verificacoes, 39.0 s, executado em 2026-11-19 02:14:51)

**Objectivo:** (a) O no Europa esta em baixo quando chega uma transferencia US-2001 -> EU-1001: o primeiro participante falha, nenhum prepara e a decisao e ABORT. (b) O no America cai depois de o Europa ja ter preparado (PREPARE TRANSACTION): o Europa faz ROLLBACK PREPARED. Nenhum saldo muda.

**Dois computadores:** Com dois PCs pode desligar-se o cabo/Wi-Fi do PC B em vez de parar o contentor.

## Procedimento executado

1. `02:14:13` (a) docker compose stop db-europa; carlos envia 12.00 de US-2001 para EU-1001
2. `02:14:19` (a) docker compose start db-europa
3. `02:14:26` (b) Pausa de laboratorio de 8 s antes de preparar no America
4. `02:14:28` (b) ana envia 15.00 de EU-1001 para US-2001 (em segundo plano)
5. `02:14:29` (b) docker compose stop db-america (queda do no America)
6. `02:14:41` (b) docker compose start db-america

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
    "id": "66877c18-3f70-46e5-aeb5-e69d62ea09b6",
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
    "chave_idempotencia": "c05a-64193475-dd82-4397-9974-9ef9c8b02031",
    "instancia_api": "api-1",
    "participantes": [
      {
        "no": "america",
        "gid": "gs-66877c18-3f70-46e5-aeb5-e69d62ea09b6-america",
        "estado": "POR_PREPARAR"
      },
      {
        "no": "europa",
        "gid": "gs-66877c18-3f70-46e5-aeb5-e69d62ea09b6-europa",
        "estado": "NAO_PREPARADO"
      }
    ],
    "pendente_em": [],
    "parceiro": {
      "estado": "NAO_APLICAVEL",
      "referencia": null
    },
    "criada_em": "2026-11-19T00:14:15.189800+00:00",
    "decidida_em": "2026-11-19T00:14:18.712352+00:00",
    "concluida_em": "2026-11-19T00:14:18.847394+00:00",
    "repetido": false
  }
}
```

## (b) pg_prepared_xacts durante a pausa

```
{
  "europa": [
    "gs-6810d873-9bcc-4077-90c9-ffd5b9593b51-europa"
  ],
  "america": []
}
```

## (b) Resposta da API (HTTP 503)

```
{
  "id": "6810d873-9bcc-4077-90c9-ffd5b9593b51",
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
  "chave_idempotencia": "c05-5ce10e6d-8eda-43f3-b2b7-8e2243c274f3",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-6810d873-9bcc-4077-90c9-ffd5b9593b51-america",
      "estado": "NAO_PREPARADO"
    },
    {
      "no": "europa",
      "gid": "gs-6810d873-9bcc-4077-90c9-ffd5b9593b51-europa",
      "estado": "DESFEITO"
    }
  ],
  "pendente_em": [],
  "parceiro": {
    "estado": "NAO_APLICAVEL",
    "referencia": null
  },
  "criada_em": "2026-11-19T00:14:28.374010+00:00",
  "decidida_em": "2026-11-19T00:14:40.179850+00:00",
  "concluida_em": "2026-11-19T00:14:40.506652+00:00",
  "repetido": false
}
```

## (b) Diario do coordenador

```
00:14:28.374  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 1500 centimos
00:14:28.624  PREPARADO                europa: PREPARE TRANSACTION 'gs-6810d873-9bcc-4077-90c9-ffd5b9593b51-europa'
00:14:28.711  PAUSA_LABORATORIO        antes_preparar_america: 8.0 s
00:14:40.120  SEM_RESPOSTA_PREPARACAO  america: OperationalError (estado NAO_PREPARADO)
00:14:40.179  DECISAO_ABORT            o no america nao respondeu durante a preparacao
00:14:40.427  DESFEITO                 europa: ROLLBACK PREPARED 'gs-6810d873-9bcc-4077-90c9-ffd5b9593b51-europa'
00:14:40.572  ABORTADA                 decisao aplicada em todos os participantes
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
