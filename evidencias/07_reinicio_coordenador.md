# Cenario 7: Reinicio do coordenador com transaccoes pendentes

**Resultado: PASSOU** (8/8 verificacoes, 33.0 s, executado em 2026-11-19 02:16:49)

**Objectivo:** (a) O coordenador cai depois de gravar COMMIT: ao reiniciar conclui o COMMIT nos dois nos. (b) O coordenador cai depois de preparar mas antes de decidir: ao reiniciar faz ABORT presumido.

## Procedimento executado

1. `02:16:17` (a) Pausa de 20 s depois de gravar a decisao; ana envia 30.00 EU-1002 -> US-2002
2. `02:16:21` docker compose kill coordenador (queda abrupta, sem terminar o pedido)
3. `02:16:23` (a) Bloqueio do 2PC: tentar alterar EU-1002 directamente no Europa com lock_timeout de 2 s
4. `02:16:26` (a) docker compose start coordenador -> recuperacao de arranque
5. `02:16:33` (a) o cliente pergunta o resultado pela chave: GET /api/v1/transferencias?chave=...
6. `02:16:33` (b) Pausa de 20 s depois de preparar (antes da decisao); ana envia 40.00 EU-1001 -> US-2001
7. `02:16:37` docker compose kill coordenador
8. `02:16:39` docker compose start coordenador -> abort presumido

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1001 | 4 846.50 | 4 846.50 |
| EU-1002 | 1 489.00 | 1 459.00 |
| US-2001 | 3 453.50 | 3 453.50 |
| US-2002 | 811.00 | 841.00 |

## (a) Resposta da API ao cliente com o coordenador morto

```
{
  "http": 504,
  "instancia": "api-1",
  "corpo": {
    "detail": "sem resposta do coordenador: resultado DESCONHECIDO (nao significa falha). Repita com a mesma Idempotency-Key ou consulte GET /api/v1/transferencias?chave=..."
  }
}
```

## (a) Estado com o coordenador em baixo

```
{
  "registo do coordenador": {
    "estado": "COMMIT_DECIDIDO",
    "decisao": "COMMIT",
    "codigo_erro": null,
    "parceiro": "NAO_APLICAVEL",
    "participantes": {
      "europa": "PREPARADO",
      "america": "PREPARADO"
    }
  },
  "pg_prepared_xacts": {
    "europa": [
      "gs-75ad0527-36aa-4bff-8fed-2999acc15670-europa"
    ],
    "america": [
      "gs-75ad0527-36aa-4bff-8fed-2999acc15670-america"
    ]
  }
}
```

## (a) Linha bloqueada pela transaccao preparada

```
psql db-europa: ERROR:  canceling statement due to lock timeout
CONTEXT:  while updating tuple (0,13) in relation "contas"
```

## (a) Diario do coordenador

```
00:16:19.937  INICIADA                 ordem de api-1: EU-1002 -> US-2002, 3000 centimos
00:16:20.243  PREPARADO                europa: PREPARE TRANSACTION 'gs-75ad0527-36aa-4bff-8fed-2999acc15670-europa'
00:16:20.406  PREPARADO                america: PREPARE TRANSACTION 'gs-75ad0527-36aa-4bff-8fed-2999acc15670-america'
00:16:20.586  DECISAO_COMMIT           todos os participantes prepararam
00:16:20.753  PAUSA_LABORATORIO        apos_decisao: 20.0 s
00:16:29.120  RECUPERACAO              decisao COMMIT gravada: repetir nos participantes
00:16:29.396  CONFIRMADO               america: COMMIT PREPARED 'gs-75ad0527-36aa-4bff-8fed-2999acc15670-america'
00:16:29.431  CONFIRMADO               europa: COMMIT PREPARED 'gs-75ad0527-36aa-4bff-8fed-2999acc15670-europa'
00:16:29.558  CONCLUIDA                decisao aplicada em todos os participantes
00:16:29.957  PARCEIRO_CONFIRMOU       referencia BP-000012 (HTTP 201)
```

## (b) Estado com o coordenador em baixo

```
{
  "registo do coordenador": {
    "estado": "PREPARADA",
    "decisao": null,
    "codigo_erro": null,
    "parceiro": "NAO_APLICAVEL",
    "participantes": {
      "europa": "PREPARADO",
      "america": "PREPARADO"
    }
  },
  "pg_prepared_xacts": {
    "europa": [
      "gs-98059bfc-d67c-49f2-87a6-5ccbff74fc28-europa"
    ],
    "america": [
      "gs-98059bfc-d67c-49f2-87a6-5ccbff74fc28-america"
    ]
  }
}
```

## (b) Diario do coordenador

```
00:16:36.244  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 4000 centimos
00:16:36.606  PREPARADO                europa: PREPARE TRANSACTION 'gs-98059bfc-d67c-49f2-87a6-5ccbff74fc28-europa'
00:16:36.752  PREPARADO                america: PREPARE TRANSACTION 'gs-98059bfc-d67c-49f2-87a6-5ccbff74fc28-america'
00:16:36.874  PAUSA_LABORATORIO        apos_preparar: 20.0 s
00:16:41.976  RECUPERACAO              sem decisao gravada: abort presumido
00:16:42.028  DECISAO_ABORT            o coordenador reiniciou antes de decidir; nada foi confirmado (abort presumido)
00:16:42.264  DESFEITO                 europa: ROLLBACK PREPARED 'gs-98059bfc-d67c-49f2-87a6-5ccbff74fc28-europa'
00:16:42.289  DESFEITO                 america: ROLLBACK PREPARED 'gs-98059bfc-d67c-49f2-87a6-5ccbff74fc28-america'
00:16:42.407  ABORTADA                 decisao aplicada em todos os participantes
```

## Verificacoes

- [x] (a) a API responde 504/503: resultado DESCONHECIDO (timeout nao e decisao)
- [x] (a) decisao COMMIT gravada e os dois nos com a transaccao preparada
- [x] (a) a conta fica bloqueada enquanto o coordenador nao volta
- [x] (a) concluida apos o reinicio: um debito e um credito
- [x] (a) o cliente descobre que a transferencia foi CONCLUIDA
- [x] (b) ABORTADA com codigo RECUPERACAO e sem movimentos
- [x] so a transferencia (a) mudou saldos (30.00)
- [x] nenhuma transaccao preparada ficou por resolver
