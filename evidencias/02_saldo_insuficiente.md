# Cenario 2: Saldo insuficiente e outras validacoes

**Resultado: PASSOU** (9/9 verificacoes, 6.6 s, executado em 2026-11-19 03:01:53)

**Objectivo:** bruno (EU-1003, 300.00) tenta transferir 1000.00: o no Europa vota NAO e a decisao e ABORT.

## Procedimento executado

1. `03:01:48` bruno envia 1000.00 de EU-1003 para US-2002
2. `03:01:51` Outras validacoes: conta inexistente, montante negativo, 3 casas decimais, mesma conta

## Saldos (lidos directamente nos nos PostgreSQL)

| Conta | antes | depois |
|---|---:|---:|
| EU-1003 | 300.00 | 300.00 |
| US-2002 | 800.00 | 800.00 |

## Resposta (HTTP 422)

```
{
  "id": "c70b950c-b7ac-4ae4-8e25-7a39d2696f06",
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
  "chave_idempotencia": "cli-fd757fb0-d40e-4b42-90c2-e59c340a80aa",
  "instancia_api": "api-1",
  "participantes": [
    {
      "no": "america",
      "gid": "gs-c70b950c-b7ac-4ae4-8e25-7a39d2696f06-america",
      "estado": "POR_PREPARAR"
    },
    {
      "no": "europa",
      "gid": "gs-c70b950c-b7ac-4ae4-8e25-7a39d2696f06-europa",
      "estado": "NAO_PREPARADO"
    }
  ],
  "pendente_em": [],
  "parceiro": {
    "estado": "NAO_APLICAVEL",
    "referencia": null
  },
  "criada_em": "2026-11-19T01:01:48.329235+00:00",
  "decidida_em": "2026-11-19T01:01:48.603686+00:00",
  "concluida_em": "2026-11-19T01:01:48.741144+00:00",
  "repetido": false
}
```

## Diario do coordenador

```
01:01:48.329  INICIADA                 ordem de api-1: EU-1003 -> US-2002, 100000 centimos
01:01:48.553  VOTO_NAO                 europa: SALDO_INSUFICIENTE (saldo insuficiente em EU-1003)
01:01:48.603  DECISAO_ABORT            saldo insuficiente em EU-1003
01:01:48.784  ABORTADA                 decisao aplicada em todos os participantes
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
