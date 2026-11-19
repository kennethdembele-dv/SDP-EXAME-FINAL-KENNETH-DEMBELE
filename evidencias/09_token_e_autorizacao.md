# Cenario 9: Token invalido ou expirado e acesso sem autorizacao

**Resultado: PASSOU** (13/13 verificacoes, 14.5 s, executado em 2026-11-19 02:17:27)

**Objectivo:** As APIs validam assinatura, expiracao, emissor e destinatario do JWT, e so deixam o titular consultar ou movimentar a conta.

## Procedimento executado

1. `02:17:14` Palavra-passe errada no servico de autenticacao
2. `02:17:14` bruno, com token valido, tenta usar a conta da ana
3. `02:17:15` Validacao descentralizada: parar o servico de autenticacao e usar o token ja emitido

## Pedidos a GET /api/v1/contas/EU-1001/saldo

```
sem token                      HTTP 401  falta o token (Authorization: Bearer ...)
assinado com outra chave       HTTP 401  assinatura do token invalida
expirado (chave verdadeira)    HTTP 401  token expirado
destinatario errado            HTTP 401  token emitido para outro destinatario
emissor errado                 HTTP 401  token de um emissor desconhecido
algoritmo none                 HTTP 401  token invalido: The specified alg value is not allowed
token adulterado (sub=bruno)   HTTP 401  assinatura do token invalida
```

## Autorizacao

```
consultar saldo de EU-1001       HTTP 403  a conta EU-1001 nao pertence ao utilizador bruno
historico de EU-1001             HTTP 403  a conta EU-1001 nao pertence ao utilizador bruno
transferir a partir de EU-1001   HTTP 403  a conta EU-1001 nao pertence ao utilizador bruno
ver a transferencia da ana       HTTP 404  transferencia inexistente
```

## Verificacoes

- [x] sem token: HTTP 401
- [x] assinado com outra chave: HTTP 401
- [x] expirado (chave verdadeira): HTTP 401
- [x] destinatario errado: HTTP 401
- [x] emissor errado: HTTP 401
- [x] algoritmo none: HTTP 401
- [x] token adulterado (sub=bruno): HTTP 401
- [x] palavra-passe errada: HTTP 401
- [x] bruno: consultar saldo de EU-1001 -> recusado (403/404)
- [x] bruno: historico de EU-1001 -> recusado (403/404)
- [x] bruno: transferir a partir de EU-1001 -> recusado (403/404)
- [x] bruno: ver a transferencia da ana -> recusado (403/404)
- [x] com o emissor em baixo, api-2 continua a aceitar o token valido (HTTP 200)
