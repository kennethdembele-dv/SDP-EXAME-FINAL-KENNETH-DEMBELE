# Cenario 2: Saldo insuficiente e outras validacoes

**Resultado: PASSOU** (9/9 verificacoes, 6.1 s, executado em 2026-11-19 02:22:57)

**Objectivo:** bruno (EU-1003, 300.00) tenta transferir 1000.00: o no Europa vota NAO e a decisao e ABORT.

## Procedimento executado

1. `02:22:52` bruno envia 1000.00 de EU-1003 para US-2002
2. `02:22:55` Outras validacoes: conta inexistente, montante negativo, 3 casas decimais, mesma conta

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1003 | 300.00 | 300.00 |
| US-2002 | 800.00 | 800.00 |

## Resposta (HTTP 422)

```
{
  "id": "283c8a94-d062-43a6-94a3-febd9d67e12e",
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
  "chave_idempotencia": "cli-fc35708d-e19e-4356-b1f2-433150649f82",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-283c8a94-d062-43a6-94a3-febd9d67e12e-america",
      "estado": "POR_PREPARAR"
    },
    {
      "no": "europa",
      "gid": "gs-283c8a94-d062-43a6-94a3-febd9d67e12e-europa",
      "estado": "NAO_PREPARADO"
    }
  ],
  "pendente_em": [],
  "parceiro": {
    "estado": "NAO_APLICAVEL",
    "referencia": null
  },
  "criada_em": "2026-11-19T00:22:52.727194+00:00",
  "decidida_em": "2026-11-19T00:22:52.923466+00:00",
  "concluida_em": "2026-11-19T00:22:53.074672+00:00",
  "repetido": false
}
```

## Diario do coordenador

```
00:22:52.727  INICIADA                 ordem de api-1: EU-1003 -> US-2002, 100000 centimos
00:22:52.875  VOTO_NAO                 europa: SALDO_INSUFICIENTE (saldo insuficiente em EU-1003)
00:22:52.923  DECISAO_ABORT            saldo insuficiente em EU-1003
00:22:53.115  ABORTADA                 decisao aplicada em todos os participantes
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
