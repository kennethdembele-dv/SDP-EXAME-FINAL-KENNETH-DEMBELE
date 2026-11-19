# Cenario 3: Transferencias concorrentes sobre a mesma conta

**Resultado: PASSOU** (7/7 verificacoes, 10.8 s, executado em 2026-11-19 02:13:58)

**Objectivo:** 10 transferencias simultaneas de 50.00 a partir de EU-1003, metade por api-1 e metade por api-2. Com o saldo disponivel so algumas podem passar; o saldo nunca pode ficar negativo.

## Procedimento executado

1. `02:13:49` Lancar 10 pedidos em paralelo (saldo inicial 300.00; cabem 6)

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1003 | 300.00 | 0.00 |
| US-2001 | 3 125.50 | 3 425.50 |

## Resultado de cada pedido (i, HTTP, estado, codigo, instancia, segundos)

```
(0, 422, 'ABORTADA', 'SALDO_INSUFICIENTE', 'api-1', 8.342)
(1, 201, 'CONCLUIDA', None, 'api-2', 5.229)
(2, 201, 'CONCLUIDA', None, 'api-1', 4.34)
(3, 201, 'CONCLUIDA', None, 'api-2', 6.245)
(4, 422, 'ABORTADA', 'SALDO_INSUFICIENTE', 'api-1', 8.262)
(5, 422, 'ABORTADA', 'SALDO_INSUFICIENTE', 'api-2', 8.34)
(6, 201, 'CONCLUIDA', None, 'api-1', 2.531)
(7, 201, 'CONCLUIDA', None, 'api-2', 7.858)
(8, 201, 'CONCLUIDA', None, 'api-1', 3.424)
(9, 422, 'ABORTADA', 'SALDO_INSUFICIENTE', 'api-2', 8.324)
```

## Verificacoes

- [x] exactamente 6 concluidas
- [x] as restantes abortadas por SALDO_INSUFICIENTE (ou conflito de bloqueio)
- [x] os pedidos foram atendidos pelas duas instancias
- [x] saldo final = inicial - 50.00 x concluidas
- [x] saldo nunca negativo
- [x] dinheiro conservado entre as duas contas
- [x] numero de debitos de EU-1003 igual ao numero de concluidas (sem duplicados)
