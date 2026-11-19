# Cenario 2: Saldo insuficiente e outras validacoes

**Resultado: PASSOU** (9/9 verificacoes, 6.2 s, executado em 2026-11-19 02:13:48)

**Objectivo:** bruno (EU-1003, 300.00) tenta transferir 1000.00: o no Europa vota NAO e a decisao e ABORT.

## Procedimento executado

1. `02:13:43` bruno envia 1000.00 de EU-1003 para US-2002
2. `02:13:46` Outras validacoes: conta inexistente, montante negativo, 3 casas decimais, mesma conta

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1003 | 300.00 | 300.00 |
| US-2002 | 800.00 | 800.00 |

## Resposta (HTTP 422)

```
{
  "id": "e2862d75-3cc2-46e3-963b-78c54ecbb8d0",
  "estado": "ABORTADA",
  "explicacao": "abortada em todos os participantes: nenhum saldo foi alterado",
  "decisao": "ABORT",
  "codigo_erro": "SALDO_INSUFICIENTE",
  "motivo": "saldo insuficiente em EU-1003",
  "conta_origem": "EU-1003",
  "conta_destino": "US-2002",
  "montante": "1000.00",
  "montante_centimos": 100000,
  "moeda": "EUR",
  "utilizador": "bruno",
  "chave_idempotencia": "cli-0eb85405-0abc-49b6-9583-b9db270c53bd",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-e2862d75-3cc2-46e3-963b-78c54ecbb8d0-america",
      "estado": "POR_PREPARAR"
    },
    {
      "no": "europa",
      "gid": "gs-e2862d75-3cc2-46e3-963b-78c54ecbb8d0-europa",
      "estado": "NAO_PREPARADO"
    }
  ],
  "pendente_em": [],
  "parceiro": {
    "estado": "NAO_APLICAVEL",
    "referencia": null
  },
  "criada_em": "2026-11-19T00:13:43.148555+00:00",
  "decidida_em": "2026-11-19T00:13:43.354778+00:00",
  "concluida_em": "2026-11-19T00:13:43.470686+00:00",
  "repetido": false
}
```

## Diario do coordenador

```
00:13:43.148  INICIADA                 ordem de api-1: EU-1003 -> US-2002, 100000 centimos
00:13:43.301  VOTO_NAO                 europa: SALDO_INSUFICIENTE (saldo insuficiente em EU-1003)
00:13:43.354  DECISAO_ABORT            saldo insuficiente em EU-1003
00:13:43.507  ABORTADA                 decisao aplicada em todos os participantes
```

## Validacoes

```
conta destino inexistente (US-9999)    HTTP 422  CONTA_INEXISTENTE
montante negativo (-5)                 HTTP 422  o montante tem de ser positivo
tres casas decimais (1.005)            HTTP 422  o montante tem no maximo 2 casas decimais
origem igual ao destino                HTTP 422  a conta de origem e a de destino sao a mesma
moeda diferente (USD)                  HTTP 422  moeda nao suportada: a demonstracao usa apenas EUR
```

## Verificacoes

- [x] HTTP 422, estado ABORTADA, codigo SALDO_INSUFICIENTE
- [x] saldos inalterados
- [x] nenhum movimento registado
- [x] conta destino inexistente (US-9999): recusado com HTTP 422
- [x] montante negativo (-5): recusado com HTTP 422
- [x] tres casas decimais (1.005): recusado com HTTP 422
- [x] origem igual ao destino: recusado com HTTP 422
- [x] moeda diferente (USD): recusado com HTTP 422
- [x] saldos continuam inalterados
