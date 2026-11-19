# Cenario 11: Comunicacao entre Python e Java (XML sobre HTTPS)

**Resultado: PASSOU** (10/10 verificacoes, 32.2 s, executado em 2026-11-19 03:07:26)

**Objectivo:** O coordenador (Python) confirma cada transferencia concluida no banco parceiro (Java) com XML; a API consulta o registo no Java. Testa-se a validacao do XML e a indisponibilidade do Java.

## Procedimento executado

1. `03:06:54` GET /api/v1/parceiro/transferencias/{id}: a API (Python) consulta o banco parceiro (Java)
2. `03:06:54` XML invalido enviado directamente ao Java
3. `03:07:07` docker compose stop banco-parceiro; nova transferencia de 7.00
4. `03:07:13` docker compose start banco-parceiro; o coordenador repete a confirmacao

## Resposta (o campo xml_recebido e o XML devolvido pelo Java)

```
{
  "fonte": "banco-parceiro (Java)",
  "formato": "XML",
  "registo": {
    "id": "2b560500-48c7-4e65-8450-70bc3ea6db96",
    "referenciaParceiro": "BP-000001",
    "estado": "REGISTADA",
    "contaOrigem": "EU-1001",
    "contaDestino": "US-2001",
    "montanteCentimos": "12550",
    "moeda": "EUR",
    "concluidaEm": "2026-11-19T01:01:34.572Z",
    "recebidaEm": "2026-11-19T01:01:35.447361800Z"
  },
  "xml_recebido": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<registoParceiro versao=\"1\"><id>2b560500-48c7-4e65-8450-70bc3ea6db96</id><referenciaParceiro>BP-000001</referenciaParceiro><estado>REGISTADA</estado><contaOrigem>EU-1001</contaOrigem><contaDestino>US-2001</contaDestino><montanteCentimos>12550</montanteCentimos><moeda>EUR</moeda><concluidaEm>2026-11-19T01:01:34.572Z</concluidaEm><recebidaEm>2026-11-19T01:01:35.447361800Z</recebidaEm></registoParceiro>"
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
      "id": "cedb9505-31fc-4de3-a1f4-344d477ed4b2",
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
      "chave_idempotencia": "cli-6d810604-c5bc-4fca-bb60-47dbf2504a09",
      "instancia_api": "api-1",
      "participantes": [
        {
          "no": "america",
          "gid": "gs-cedb9505-31fc-4de3-a1f4-344d477ed4b2-america",
          "estado": "CONFIRMADO"
        },
        {
          "no": "europa",
          "gid": "gs-cedb9505-31fc-4de3-a1f4-344d477ed4b2-europa",
          "estado": "CONFIRMADO"
        }
      ],
      "pendente_em": [],
      "parceiro": {
        "estado": "POR_ENVIAR",
        "referencia": null
      },
      "criada_em": "2026-11-19T01:07:08.668531+00:00",
      "decidida_em": "2026-11-19T01:07:09.225240+00:00",
      "concluida_em": "2026-11-19T01:07:09.550167+00:00",
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
banco-parceiro-1  | Confirmacao registada: 709c4232-c998-459b-b990-81079a8e9039 -> BP-000006 (5000 centimos)
banco-parceiro-1  | Confirmacao registada: 4361745b-e422-45f6-8beb-2b81e00545ae -> BP-000007 (5000 centimos)
banco-parceiro-1  | Confirmacao registada: 98bd6157-17cf-410e-bfdc-511dbfcf8696 -> BP-000008 (1000 centimos)
banco-parceiro-1  | Confirmacao registada: 09babb89-5df3-45a4-a626-7bd0be11818c -> BP-000009 (100 centimos)
banco-parceiro-1  | Confirmacao registada: ab96e04a-ec39-4725-8b8b-37aadbfbeda7 -> BP-000010 (2000 centimos)
banco-parceiro-1  | Confirmacao registada: e12f62f8-f6d6-481b-a369-550bbd6a5d89 -> BP-000011 (800 centimos)
banco-parceiro-1  | Confirmacao registada: 5448caaf-b07a-4e99-b48c-d20706a48514 -> BP-000012 (3000 centimos)
banco-parceiro-1  | Confirmacao registada: cc6f1627-cd8b-46d0-9edc-f52816c7a6e8 -> BP-000013 (500 centimos)
banco-parceiro-1  | Confirmacao registada: 22cd0e0d-f6fd-4b4a-a2be-49b76a76d61e -> BP-000014 (100 centimos)
banco-parceiro-1  | Pedido recusado: campo montanteCentimos invalido: -5
banco-parceiro-1  | Pedido recusado: falta o campo contaDestino
banco-parceiro-1  | Pedido recusado: XML mal formado: XML document structures must start and end within the same entity.
banco-parceiro-1  | Pedido recusado: XML mal formado: DOCTYPE is disallowed when the feature "http://apache.org/xml/features/disallow-doctype-decl" set to true.
banco-parceiro-1  | Banco parceiro (Java 21.0.13+9-LTS) a ouvir em HTTPS na porta 8200; 14 registo(s) carregado(s)
banco-parceiro-1  | Confirmacao registada: cedb9505-31fc-4de3-a1f4-344d477ed4b2 -> BP-000015 (700 centimos)
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
