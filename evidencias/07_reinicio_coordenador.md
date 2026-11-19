# Cenario 7: Reinicio do coordenador com transaccoes pendentes

**Resultado: PASSOU** (8/8 verificacoes, 32.8 s, executado em 2026-11-19 02:25:53)

**Objectivo:** (a) O coordenador cai depois de gravar COMMIT: ao reiniciar conclui o COMMIT nos dois nos. (b) O coordenador cai depois de preparar mas antes de decidir: ao reiniciar faz ABORT presumido.

## Procedimento executado

1. `02:25:21` (a) Pausa de 20 s depois de gravar a decisao; ana envia 30.00 EU-1002 -> US-2002
2. `02:25:25` docker compose kill coordenador (queda abrupta, sem terminar o pedido)
3. `02:25:28` (a) Bloqueio do 2PC: tentar alterar EU-1002 directamente no Europa com lock_timeout de 2 s
4. `02:25:30` (a) docker compose start coordenador -> recuperacao de arranque
5. `02:25:38` (a) o cliente pergunta o resultado pela chave: GET /api/v1/transferencias?chave=...
6. `02:25:38` (b) Pausa de 20 s depois de preparar (antes da decisao); ana envia 40.00 EU-1001 -> US-2001
7. `02:25:41` docker compose kill coordenador
8. `02:25:43` docker compose start coordenador -> abort presumido

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
      "gs-ac0a9010-c97e-49f2-bb6d-c5d99a3d52c9-europa"
    ],
    "america": [
      "gs-ac0a9010-c97e-49f2-bb6d-c5d99a3d52c9-america"
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
00:25:24.234  INICIADA                 ordem de api-1: EU-1002 -> US-2002, 3000 centimos
00:25:24.528  PREPARADO                europa: PREPARE TRANSACTION 'gs-ac0a9010-c97e-49f2-bb6d-c5d99a3d52c9-europa'
00:25:24.681  PREPARADO                america: PREPARE TRANSACTION 'gs-ac0a9010-c97e-49f2-bb6d-c5d99a3d52c9-america'
00:25:24.779  DECISAO_COMMIT           todos os participantes prepararam
00:25:24.843  PAUSA_LABORATORIO        apos_decisao: 20.0 s
00:25:33.387  RECUPERACAO              decisao COMMIT gravada: repetir nos participantes
00:25:33.602  CONFIRMADO               america: COMMIT PREPARED 'gs-ac0a9010-c97e-49f2-bb6d-c5d99a3d52c9-america'
00:25:33.626  CONFIRMADO               europa: COMMIT PREPARED 'gs-ac0a9010-c97e-49f2-bb6d-c5d99a3d52c9-europa'
00:25:33.735  CONCLUIDA                decisao aplicada em todos os participantes
00:25:34.070  PARCEIRO_CONFIRMOU       referencia BP-000012 (HTTP 201)
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
      "gs-6d8fb855-2a39-4c95-9165-999708b4a3f2-europa"
    ],
    "america": [
      "gs-6d8fb855-2a39-4c95-9165-999708b4a3f2-america"
    ]
  }
}
```

## (b) Diario do coordenador

```
00:25:40.428  INICIADA                 ordem de api-1: EU-1001 -> US-2001, 4000 centimos
00:25:40.674  PREPARADO                europa: PREPARE TRANSACTION 'gs-6d8fb855-2a39-4c95-9165-999708b4a3f2-europa'
00:25:40.844  PREPARADO                america: PREPARE TRANSACTION 'gs-6d8fb855-2a39-4c95-9165-999708b4a3f2-america'
00:25:40.933  PAUSA_LABORATORIO        apos_preparar: 20.0 s
00:25:45.931  RECUPERACAO              sem decisao gravada: abort presumido
00:25:45.989  DECISAO_ABORT            o coordenador reiniciou antes de decidir; nada foi confirmado (abort presumido)
00:25:46.228  DESFEITO                 america: ROLLBACK PREPARED 'gs-6d8fb855-2a39-4c95-9165-999708b4a3f2-america'
00:25:46.253  DESFEITO                 europa: ROLLBACK PREPARED 'gs-6d8fb855-2a39-4c95-9165-999708b4a3f2-europa'
00:25:46.370  ABORTADA                 decisao aplicada em todos os participantes
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
