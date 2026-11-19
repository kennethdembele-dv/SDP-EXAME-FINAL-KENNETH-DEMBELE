# Roteiro da demonstracao laboratorial

Duracao prevista: 15 a 20 minutos. Abrir dois terminais na pasta do projecto: **T1** para os comandos e
**T2** com `docker compose logs -f coordenador` (mostra cada passo do 2PC em tempo real).

Antes da defesa:

```sh
docker compose down -v                  # comecar com os dados de demonstracao
docker compose up -d --build
docker compose ps                       # todos "healthy"
alias gs='python scripts/cliente.py'    # no PowerShell: function gs { python scripts/cliente.py @args }
```

Comandos uteis para mostrar o estado interno (podem ser repetidos a qualquer momento):

```sh
# Transaccoes preparadas em cada no (deve estar vazio fora dos momentos de falha)
docker compose exec db-europa  psql -U postgres -p 5433 -d globalscale -c "SELECT gid, prepared FROM pg_prepared_xacts"
docker compose exec db-america psql -U postgres -p 5434 -d globalscale -c "SELECT gid, prepared FROM pg_prepared_xacts"
# Registo do coordenador
docker compose exec db-coordenador psql -U postgres -p 5435 -d globalscale \
  -c "SELECT left(id::text,8) id, estado, decisao, codigo_erro, parceiro_estado FROM transferencias ORDER BY criada_em DESC LIMIT 5"
# Soma de todos os saldos (deve ser sempre 10600.00)
docker compose exec db-europa  psql -U postgres -p 5433 -d globalscale -tAc "SELECT sum(saldo_centimos) FROM contas"
docker compose exec db-america psql -U postgres -p 5434 -d globalscale -tAc "SELECT sum(saldo_centimos) FROM contas"
```

## 0. Interface Web (durante toda a defesa)

Abrir <https://localhost:8001/> e entrar como `ana`. Manter visiveis o **Estado do sistema** (cada `docker compose
stop` fica vermelho em menos de 3 s) e o **Monitor 2PC** (as transferencias pendentes passam a CONCLUIDA quando o no
volta). Todas as demonstracoes abaixo podem ser feitas pela vista **Transferir**, que mostra as fases do 2PC.

## 1. Arquitectura, rede e TLS (2 min)

```sh
docker compose ps
docker network inspect global-scale_interna --format "{{range .Containers}}{{.IPv4Address}} {{.Name}}{{println}}{{end}}"
docker compose exec api-1 getent hosts db-europa db-america coordenador nfs
```

Mostrar no PostgreSQL que as ligacoes usam TLS e explicar o `pg_hba.conf` (`hostnossl ... reject`):

```sh
docker compose exec db-europa psql -U postgres -p 5433 -d globalscale \
  -c "SELECT a.application_name, s.ssl, s.version FROM pg_stat_ssl s JOIN pg_stat_activity a USING (pid) WHERE a.client_addr IS NOT NULL"
```

## 2. Transferencia normal (2 min)

```sh
gs -u ana -p Ana#2026 contas
gs -u ana -p Ana#2026 transferir EU-1001 US-2001 100.00
```

Em T2 aparece: `INICIADA` → `PREPARADO europa` → `PREPARADO america` → `DECISAO_COMMIT` →
`CONFIRMADO` (x2) → `CONCLUIDA` → `PARCEIRO_CONFIRMOU`. Mostrar os comandos nos logs dos nos:

```sh
docker compose logs db-america | grep -E "PREPARE TRANSACTION|COMMIT PREPARED" | tail -2
gs -u ana -p Ana#2026 estado <id>          # participantes CONFIRMADO e referencia BP-... do banco Java
gs -u ana -p Ana#2026 parceiro <id>        # XML devolvido pelo Java
```

## 3. Derrubar um no da base de dados (4 min)

**a) Antes da preparacao:** o no America esta em baixo quando chega a transferencia.

```sh
docker compose stop db-america
gs -u ana -p Ana#2026 transferir EU-1001 US-2001 10.00      # HTTP 503, ABORTADA, NO_INDISPONIVEL
gs -u ana -p Ana#2026 saldo EU-1001                         # saldo nao mudou: o Europa fez ROLLBACK PREPARED
docker compose start db-america
```

**b) Durante a confirmacao (o caso dificil):** pedir ao coordenador para parar 20 s antes do
COMMIT no America e, durante a pausa, derrubar o no.

```sh
python testes/lab.py pausa antes_commit_america 20
gs -u ana -p Ana#2026 transferir EU-1001 US-2001 20.00 &   # fica a espera
docker compose stop db-america                              # durante a pausa
# resposta: HTTP 202, COMMIT_DECIDIDO, pendente_em ["america"]
#  -> o Europa ja debitou; a decisao COMMIT esta gravada e NAO muda
docker compose start db-america
docker compose exec db-america psql -U postgres -p 5434 -d globalscale -c "SELECT gid FROM pg_prepared_xacts"
#  -> a transaccao preparada sobreviveu ao reinicio do PostgreSQL
# em menos de 5 s a recuperacao faz COMMIT PREPARED e o estado passa a CONCLUIDA
gs -u ana -p Ana#2026 estado <id>
```

Explicar: o dinheiro saiu do Europa mas a entrada no America nao se perdeu, porque o America votou SIM
(preparou) antes de cair e a decisao estava gravada no coordenador. A transferencia esteve
**pendente** enquanto o no estava em baixo e ficou concluida quando voltou.

## 4. Derrubar o coordenador (3 min)

```sh
python testes/lab.py pausa apos_decisao 20
gs -u ana -p Ana#2026 transferir EU-1002 US-2002 30.00 &
docker compose kill coordenador                 # queda abrupta durante a pausa
# o cliente recebe 504: resultado DESCONHECIDO (timeout nao e decisao)
docker compose exec db-europa psql -U postgres -p 5433 -d globalscale -c "SELECT gid FROM pg_prepared_xacts"
#  -> os dois nos tem a transaccao preparada e as linhas bloqueadas (bloqueio do 2PC)
docker compose exec db-europa psql -U postgres -p 5433 -d globalscale \
  -c "SET lock_timeout='2s'; UPDATE contas SET saldo_centimos = saldo_centimos WHERE id='EU-1002'"
#  -> ERROR: canceling statement due to lock timeout
docker compose start coordenador                # recuperacao de arranque: COMMIT nos dois nos
gs -u ana -p Ana#2026 transferencias            # a transferencia aparece CONCLUIDA
```

Se a pausa for `apos_preparar` (antes da decisao), a recuperacao faz **abort presumido**: nao ha
decisao gravada, logo ninguem pode ter confirmado, e o seguro e desfazer.

## 5. Derrubar uma instancia da API (1 min)

```sh
docker compose stop api-1
gs -u ana -p Ana#2026 transferir EU-1001 US-2001 5.00      # [failover] api-1 nao aceita ligacoes -> api-2
docker compose start api-1
```

## 6. Seguranca (3 min)

```sh
python testes/cenarios.py 9 10      # tokens invalidos/expirados, acesso sem autorizacao, ordem adulterada
```

Abrir `evidencias/10_mensagem_adulterada.md`: mostra a representacao canonica, os dois SHA-256
diferentes e a resposta 401. Abrir `evidencias/09_token_e_autorizacao.md`: cada token invalido e 401,
o bruno recebe 403 ao tentar usar a conta da ana, e com o servico `auth` parado a api-2 continua a
aceitar tokens validos (validacao local).

## 7. DFS e Java (2 min)

```sh
gs -u ana -p Ana#2026 auditoria <id>                       # eventos de api-1 e do coordenador no NFS
docker compose exec nfs ls /exports/dfs/auditoria/
docker compose stop banco-parceiro
gs -u ana -p Ana#2026 transferir EU-1001 US-2001 2.00      # conclui; parceiro POR_ENVIAR
docker compose start banco-parceiro                        # o coordenador reenvia: CONFIRMADA
```

## Quando uma operacao fica pendente

| Situacao | Estado | O que a resolve |
|---|---|---|
| No participante em baixo depois de a decisao estar gravada | `COMMIT_DECIDIDO` / `ABORT_DECIDIDO` com `pendente_em` | O no voltar; o coordenador repete a decisao a cada 5 s |
| Coordenador em baixo depois de os nos prepararem | Transaccoes em `pg_prepared_xacts`, linhas bloqueadas | O coordenador voltar (com o seu registo intacto) |
| Resposta perdida entre o cliente e a API | Desconhecido para o cliente (HTTP 504) | O cliente repetir com a mesma `Idempotency-Key` ou consultar `?chave=` |
| Banco parceiro em baixo | `parceiro.estado = POR_ENVIAR` | O Java voltar; o coordenador reenvia a confirmacao |

## Se algo correr mal

| Problema | Accao |
|---|---|
| Um contentor ficou parado | `docker compose up -d` |
| Uma transferencia ficou pendente muito tempo | Verificar se todos os nos estao `healthy`; `docker compose logs coordenador` |
| Saldos estranhos | `docker compose down -v && docker compose up -d` recomeca com os dados de demonstracao |
