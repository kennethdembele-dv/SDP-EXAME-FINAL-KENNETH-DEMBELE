# Cenario 99: Verificacao global de consistencia

**Resultado: PASSOU** (5/5 verificacoes, 2.8 s, executado em 2026-11-19 02:27:39)

**Objectivo:** Conservacao dos fundos e um debito + um credito por transferencia, em todo o sistema.

## Procedimento executado


## Saldos finais

```
{
  "EU-1001": "4 837.50",
  "EU-1002": "1 452.00",
  "EU-1003": "0.00",
  "US-2001": "3 466.50",
  "US-2002": "844.00"
}
```

## Transferencias no registo do coordenador

```
{
  "ABORTADA": 9,
  "CONCLUIDA": 16
}
```

## Verificacoes

- [x] soma de todos os saldos = 10 600.00 (inicial)
- [x] nenhum saldo negativo
- [x] 16 concluidas: cada uma com exactamente um DEBITO e um CREDITO; abortadas sem movimentos
- [x] nenhum movimento sem transferencia no coordenador
- [x] nenhuma transaccao preparada por resolver
