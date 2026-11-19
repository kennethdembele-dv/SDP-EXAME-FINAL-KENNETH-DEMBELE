# Cenario 11: Comunicacao entre Python e Java (XML sobre HTTPS)

**Resultado: PASSOU** (10/10 verificacoes, 30.1 s, executado em 2026-11-19 02:18:16)

**Objectivo:** O coordenador (Python) confirma cada transferencia concluida no banco parceiro (Java) com XML; a API consulta o registo no Java. Testa-se a validacao do XML e a indisponibilidade do Java.

## Procedimento executado

1. `02:17:46` GET /api/v1/parceiro/transferencias/{id}: a API (Python) consulta o banco parceiro (Java)
2. `02:17:46` XML invalido enviado directamente ao Java
3. `02:17:59` docker compose stop banco-parceiro; nova transferencia de 7.00
4. `02:18:06` docker compose start banco-parceiro; o coordenador repete a confirmacao

## Resposta (o campo xml_recebido e o XML devolvido pelo Java)

```
{
  "fonte": "banco-parceiro (Java)",
  "formato": "XML",
  "registo": {
    "id": "05948f69-7ede-4341-82e2-bfd2846bd6de",
    "referenciaParceiro": "BP-000001",
    "estado": "REGISTADA",
    "contaOrigem": "EU-1001",
    "contaDestino": "US-2001",
    "montanteCentimos": "12550",
    "moeda": "EUR",
    "concluidaEm": "2026-11-19T00:13:36.973Z",
    "recebidaEm": "2026-11-19T00:13:37.826037400Z"
  },
  "xml_recebido": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<registoParceiro versao=\"1\"><id>05948f69-7ede-4341-82e2-bfd2846bd6de</id><referenciaParceiro>BP-000001</referenciaParceiro><estado>REGISTADA</estado><contaOrigem>EU-1001</contaOrigem><contaDestino>US-2001</contaDestino><montanteCentimos>12550</montanteCentimos><moeda>EUR</moeda><concluidaEm>2026-11-19T00:13:36.973Z</concluidaEm><recebidaEm>2026-11-19T00:13:37.826037400Z</recebidaEm></registoParceiro>"
}
```

## Validacao no Java

```
--- montante negativo: HTTP 400
<?xml version="1.0" encoding="UTF-8"?>
<erro><codigo>DADOS_INVALIDOS</codigo><mensagem>campo montanteCentimos invalido: -5</mensagem></erro>
--- falta a conta de destino: HTTP 400
<?xml version="1.0" encoding="UTF-8"?>
<erro><codigo>DADOS_INVALIDOS</codigo><mensagem>falta o campo contaDestino</mensagem></erro>
--- XML mal formado: HTTP 400
<?xml version="1.0" encoding="UTF-8"?>
<erro><codigo>DADOS_INVALIDOS</codigo><mensagem>XML mal formado: XML document structures must start and end within the same entity.</mensagem></erro>
--- DTD com entidade externa (XXE): HTTP 400
<?xml version="1.0" encoding="UTF-8"?>
<erro><codigo>DADOS_INVALIDOS</codigo><mensagem>XML mal formado: DOCTYPE is disallowed when the feature &quot;http://apache.org/xml/features/disallow-doctype-decl&quot; set to true.</mensagem></erro>
```

## Com o Java em baixo

```
{
  "transferencia": {
    "http": 201,
    "instancia": "api-1",
    "corpo": {
      "id": "b7fb186f-1d32-4b35-a4ef-15305728dce6",
      "estado": "CONCLUIDA",
      "explicacao": "confirmada em todos os participantes: um debito e um credito",
      "decisao": "COMMIT",
      "codigo_erro": null,
      "motivo": null,
      "conta_origem": "EU-1002",
      "conta_destino": "US-2001",
      "montante": "7.00",
      "montante_centimos": 700,
      "moeda": "EUR",
      "utilizador": "ana",
      "chave_idempotencia": "cli-17d900d9-1209-4a18-a1a5-e6d0657e6eb9",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-b7fb186f-1d32-4b35-a4ef-15305728dce6-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-b7fb186f-1d32-4b35-a4ef-15305728dce6-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T00:18:00.818999+00:00",
      "decidida_em": "2026-11-19T00:18:01.354843+00:00",
      "concluida_em": "2026-11-19T00:18:01.662447+00:00",
      "repetido": false
    }
  },
  "consulta ao parceiro": {
    "http": 503,
    "instancia": "api-1",
    "corpo": {
      "detail": "banco parceiro indisponivel (ConnectError); a confirmacao sera repetida pelo coordenador"
    }
  }
}
```

## Log do servico Java

```
banco-parceiro-1  | Confirmacao registada: f6d10734-cb57-4825-a810-0781abeb1c3c -> BP-000006 (5000 centimos)
banco-parceiro-1  | Confirmacao registada: e63df04b-3d40-4ada-95bd-37607f71af54 -> BP-000007 (5000 centimos)
banco-parceiro-1  | Confirmacao registada: 0512cf4f-5239-4e09-9fe8-e7584a2aced7 -> BP-000008 (1000 centimos)
banco-parceiro-1  | Confirmacao registada: e0c58742-937e-481b-8f79-497ba59bc8b2 -> BP-000009 (100 centimos)
banco-parceiro-1  | Confirmacao registada: 8ca334da-7f8c-49a0-a7ff-a9fbf0c8f4da -> BP-000010 (2000 centimos)
banco-parceiro-1  | Confirmacao registada: 07477465-e8cc-4a01-8adf-ce8c7bc59a4e -> BP-000011 (800 centimos)
banco-parceiro-1  | Confirmacao registada: 75ad0527-36aa-4bff-8fed-2999acc15670 -> BP-000012 (3000 centimos)
banco-parceiro-1  | Confirmacao registada: 7d6d42c3-6c02-48df-831a-70688d76239b -> BP-000013 (500 centimos)
banco-parceiro-1  | Confirmacao registada: d96fed09-de03-4bee-af35-cfad084f12da -> BP-000014 (100 centimos)
banco-parceiro-1  | Pedido recusado: campo montanteCentimos invalido: -5
banco-parceiro-1  | Pedido recusado: falta o campo contaDestino
banco-parceiro-1  | Pedido recusado: XML mal formado: XML document structures must start and end within the same entity.
banco-parceiro-1  | Pedido recusado: XML mal formado: DOCTYPE is disallowed when the feature "http://apache.org/xml/features/disallow-doctype-decl" set to true.
banco-parceiro-1  | Banco parceiro (Java 21.0.13+9-LTS) a ouvir em HTTPS na porta 8200; 14 registo(s) carregado(s)
banco-parceiro-1  | Confirmacao registada: b7fb186f-1d32-4b35-a4ef-15305728dce6 -> BP-000015 (700 centimos)
```

## Verificacoes

- [x] o Java tem a transferencia com a mesma referencia que o coordenador guardou
- [x] montante no Java igual ao do coordenador
- [x] montante negativo: HTTP 400 com <erro>
- [x] falta a conta de destino: HTTP 400 com <erro>
- [x] XML mal formado: HTTP 400 com <erro>
- [x] DTD com entidade externa (XXE): HTTP 400 com <erro>
- [x] a transferencia conclui na mesma (o Java nao faz parte do 2PC)
- [x] confirmacao ao parceiro fica POR_ENVIAR
- [x] a consulta ao Java devolve HTTP 503 (indisponivel)
- [x] depois de o Java voltar: CONFIRMADA
