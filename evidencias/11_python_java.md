# Cenario 11: Comunicacao entre Python e Java (XML sobre HTTPS)

**Resultado: PASSOU** (10/10 verificacoes, 32.4 s, executado em 2026-11-19 02:27:22)

**Objectivo:** O coordenador (Python) confirma cada transferencia concluida no banco parceiro (Java) com XML; a API consulta o registo no Java. Testa-se a validacao do XML e a indisponibilidade do Java.

## Procedimento executado

1. `02:26:50` GET /api/v1/parceiro/transferencias/{id}: a API (Python) consulta o banco parceiro (Java)
2. `02:26:50` XML invalido enviado directamente ao Java
3. `02:27:03` docker compose stop banco-parceiro; nova transferencia de 7.00
4. `02:27:09` docker compose start banco-parceiro; o coordenador repete a confirmacao

## Resposta (o campo xml_recebido e o XML devolvido pelo Java)

```
{
  "fonte": "banco-parceiro (Java)",
  "formato": "XML",
  "registo": {
    "id": "912affad-a763-43d3-b17f-4f673c79e971",
    "referenciaParceiro": "BP-000001",
    "estado": "REGISTADA",
    "contaOrigem": "EU-1001",
    "contaDestino": "US-2001",
    "montanteCentimos": "12550",
    "moeda": "EUR",
    "concluidaEm": "2026-11-19T00:22:46.244Z",
    "recebidaEm": "2026-11-19T00:22:47.138079200Z"
  },
  "xml_recebido": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<registoParceiro versao=\"1\"><id>912affad-a763-43d3-b17f-4f673c79e971</id><referenciaParceiro>BP-000001</referenciaParceiro><estado>REGISTADA</estado><contaOrigem>EU-1001</contaOrigem><contaDestino>US-2001</contaDestino><montanteCentimos>12550</montanteCentimos><moeda>EUR</moeda><concluidaEm>2026-11-19T00:22:46.244Z</concluidaEm><recebidaEm>2026-11-19T00:22:47.138079200Z</recebidaEm></registoParceiro>"
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
      "id": "f0ac4f7e-38b1-45e5-9f55-df90fbe0ac4e",
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
      "chave_idempotencia": "cli-c2df8da2-8e1b-40b7-9b69-f357ce050f49",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-f0ac4f7e-38b1-45e5-9f55-df90fbe0ac4e-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-f0ac4f7e-38b1-45e5-9f55-df90fbe0ac4e-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T00:27:04.355776+00:00",
      "decidida_em": "2026-11-19T00:27:04.764836+00:00",
      "concluida_em": "2026-11-19T00:27:05.095515+00:00",
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
banco-parceiro-1  | Confirmacao registada: 8ef2b9e2-b854-4de9-b2a0-6a3f9ef65583 -> BP-000007 (5000 centimos)
banco-parceiro-1  | Confirmacao repetida: 8ef2b9e2-b854-4de9-b2a0-6a3f9ef65583 -> BP-000007 (5000 centimos)
banco-parceiro-1  | Confirmacao registada: e4677e18-ae43-4c3d-b8b0-18f442f44c83 -> BP-000008 (1000 centimos)
banco-parceiro-1  | Confirmacao registada: 93397ad8-a5c9-4a81-a5b1-ea96f6232959 -> BP-000009 (100 centimos)
banco-parceiro-1  | Confirmacao registada: f3d829cb-ab88-4a78-87b0-86dd8013e9d3 -> BP-000010 (2000 centimos)
banco-parceiro-1  | Confirmacao registada: 158efdd1-056e-48ea-bba5-2e1695a1409d -> BP-000011 (800 centimos)
banco-parceiro-1  | Confirmacao registada: ac0a9010-c97e-49f2-bb6d-c5d99a3d52c9 -> BP-000012 (3000 centimos)
banco-parceiro-1  | Confirmacao registada: ea670f49-5b30-4695-b2b0-a15326719f0e -> BP-000013 (500 centimos)
banco-parceiro-1  | Confirmacao registada: d1f7d73e-306a-424e-8f04-38ce14fb91bb -> BP-000014 (100 centimos)
banco-parceiro-1  | Pedido recusado: campo montanteCentimos invalido: -5
banco-parceiro-1  | Pedido recusado: falta o campo contaDestino
banco-parceiro-1  | Pedido recusado: XML mal formado: XML document structures must start and end within the same entity.
banco-parceiro-1  | Pedido recusado: XML mal formado: DOCTYPE is disallowed when the feature "http://apache.org/xml/features/disallow-doctype-decl" set to true.
banco-parceiro-1  | Banco parceiro (Java 21.0.13+9-LTS) a ouvir em HTTPS na porta 8200; 14 registo(s) carregado(s)
banco-parceiro-1  | Confirmacao registada: f0ac4f7e-38b1-45e5-9f55-df90fbe0ac4e -> BP-000015 (700 centimos)
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
