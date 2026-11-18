# Guia de estudo para a defesa

Para cada requisito do exame: o conceito em duas linhas, onde esta no codigo e como se prova.
No fim, perguntas provaveis do docente com respostas curtas.

## 1. Mapa requisito → implementacao → evidencia

### Parte 1: arquitectura, redes e SO (120 pontos)

| Requisito | Conceito | Onde | Prova |
|---|---|---|---|
| Limitacoes de um sistema centralizado | Um so servidor: ponto unico de falha, latencia para quem esta longe, limite de escala vertical | Relatorio, seccao 2 | - |
| Ambiente com SO modernos | Cada servico corre num contentor Linux (Alpine/Debian) | `docker-compose.yml` | `evidencias/00_ambiente_rede_tls.md` |
| IP, portas, DNS local | Duas redes bridge com IP fixos; o Docker resolve os nomes dos servicos | `docker-compose.yml` (`networks`), `docs/ARQUITECTURA.md` | Cenario 0: `docker network inspect` e `getaddrinfo` |
| Dois computadores | `extra_hosts` mapeia os nomes do outro PC para o seu IP | `distribuido/pc-a.yml`, `pc-b.yml` | `docs/DOIS_COMPUTADORES.md` |
| DFS para auditoria e relatorios | NFSv4 (NFS-Ganesha) montado em `/mnt/dfs` por 3 servicos | `nfs/`, volume `dfs`, `servicos/comum/auditoria.py` | Cenario 12 |
| Transparencia de localizacao | Os servicos so veem `/mnt/dfs`; nao sabem em que maquina estao os ficheiros | volume `dfs` | Cenario 12: api-1 escreve, api-2 le |
| Acesso concorrente | Um ficheiro por evento + escrita temporaria e `rename` atomico | `auditoria.py` (`_escrever_atomico`) | Cenario 12: 0 ficheiros `.tmp`, contagem por servico |

### Parte 2: processamento, transaccoes e BD (150 pontos)

| Requisito | Conceito | Onde | Prova |
|---|---|---|---|
| BD distribuida fragmentada | Fragmentacao horizontal: contas `EU-` no no Europa, `US-` no no America | `bd/europa/`, `bd/america/`, `config.no_da_conta` | Cenario 1 (movimentos em nos diferentes) |
| Transferencia entre nos diferentes | Um debito num no e um credito no outro, na mesma transaccao distribuida | `coordenador/dois_fases.py` | Cenario 1 |
| 2PC garante ACID | Fase 1: todos preparam (votam); decisao duravel; fase 2: todos confirmam | `dois_fases.py` (`preparar`, `decidir`, `aplicar_decisao`) | Cenarios 1, 5, 6, 7 |
| Transaccoes preparadas reais | `PREPARE TRANSACTION`, `COMMIT PREPARED`, `ROLLBACK PREPARED`, `pg_prepared_xacts` | `dois_fases.py`; `max_prepared_transactions=40` no compose | Logs dos nos no cenario 1 |
| Registo duravel da decisao | A decisao e gravada (COMMIT local com fsync) antes de ser comunicada | `decidir()` | Cenario 7a: coordenador morto com decisao COMMIT; ao voltar conclui |
| Recuperacao | Repetir decisoes gravadas; abort presumido sem decisao; desfazer orfas | `recuperar()`, `ciclo_recuperacao()` | Cenarios 6 e 7 |
| Concorrencia sem saldo negativo | `UPDATE ... WHERE saldo >= m` bloqueia a linha; `CHECK (saldo >= 0)` | `_operacao()`, `bd/regional/01-esquema.sql` | Cenario 3 |
| Idempotencia | `UNIQUE (utilizador, chave)`; mesma chave com outros dados → 409 | `registar_ou_obter()`, `hash_pedido()` | Cenario 4 |
| Linguagem e concorrencia | Python: threads (API), asyncio (coordenador), pools, bloqueios na BD | Relatorio, seccao 5 | - |

### Parte 3: interoperabilidade e servicos Web (120 pontos)

| Requisito | Conceito | Onde | Prova |
|---|---|---|---|
| API REST/JSON | FastAPI com OpenAPI automatico em `/docs` | `servicos/api/main.py` | Swagger, todos os cenarios |
| Modulo noutra tecnologia | Java 21 so com o JDK (HttpsServer, DOM) | `banco-parceiro/src/BancoParceiro.java` | Cenario 11 |
| Troca de XML | Contrato `confirmacaoTransferencia` / `registoParceiro` com XSD | `comum/contrato_parceiro.py`, `banco-parceiro/contrato.xsd` | Cenario 11 |
| Validacao e indisponibilidade | Java valida campos e recusa DTD (XXE); Python valida a resposta; Java em baixo → POR_ENVIAR e reenvio | `lerPedido()`, `ler_registo()`, `confirmar_parceiro()` | Cenario 11 |
| OMA/OMG | ORB ≈ HTTP + gateway/descoberta; IDL ≈ OpenAPI/Protobuf; servicos de objectos ≈ servicos de plataforma | Relatorio, seccao 8 | - |

### Parte 4: seguranca (120 pontos)

| Requisito | Conceito | Onde | Prova |
|---|---|---|---|
| TLS em todos os servicos Web | HTTPS no uvicorn e no Java, com certificados da CA do laboratorio | `comum/servidor.py`, `BancoParceiro.java` | Cenario 0 (sem a CA e recusado; HTTP simples recusado) |
| TLS na BD | `ssl=on`, `hostnossl ... reject`, cliente `verify-full` | `bd/pg_hba.conf`, `comum/bd.py` | Cenario 0 (`pg_stat_ssl`; sem TLS e com IP errado: recusado) |
| No emissor de tokens | Servico `auth` com a chave privada RS256 | `servicos/autenticacao/main.py` | Cenario 9 |
| Validacao independente | APIs e coordenador validam com a chave publica, sem contactar o `auth` | `comum/tokens.py` | Cenario 9: `auth` parado e o token continua valido |
| Autorizacao | So o titular consulta ou movimenta a conta (API e de novo no `UPDATE ... AND titular = ...`) | `conta_autorizada()`, `_operacao()` | Cenario 9 (403) |
| Hash de palavras-passe | scrypt com sal aleatorio e comparacao em tempo constante | `comum/palavras_passe.py` | Testes unitarios |
| Assinatura das ordens | JSON canonico → SHA-256 → RSA-PSS com a chave da instancia | `comum/assinatura.py` | Cenario 10 |
| Repeticao de mensagens | `emitido_em` (janela de 120 s) + id + chave de idempotencia | `verificar_janela()` | Cenario 10 |
| Segredos fora do Git | `segredos/` e `.env` no `.gitignore`; `.env.example`; Docker secrets | `seguranca/gerar_materiais.py` | `git status` |

## 2. Conceitos que tem de saber explicar

**2PC em tres frases.** O coordenador pede a todos os participantes que preparem (cada um faz o
trabalho, grava-o no disco e promete que consegue confirmar). Se todos disserem sim, grava a decisao
COMMIT no seu registo e manda confirmar; se algum disser nao ou nao responder, a decisao e ABORT.
Depois de preparar, um participante ja nao pode desistir sozinho: espera pela decisao.

**Porque e que o dinheiro nao desaparece.** O debito no Europa e o credito no America so ficam
visiveis com COMMIT PREPARED, e esse comando so e enviado depois de os dois terem preparado e de a
decisao estar gravada. Se a rede falhar depois disso, a decisao continua gravada e e repetida.

**Bloqueio do 2PC.** Se o coordenador cair depois de os participantes prepararem, estes ficam com as
linhas bloqueadas ate ele voltar (cenario 7a). E a principal desvantagem do 2PC. O 3PC ou protocolos
de consenso (Paxos/Raft) reduzem este problema, a custo de mais mensagens.

**Timeout e decisao.** Um timeout diz "nao sei o que aconteceu", nao "falhou". A API devolve 504 com
"resultado desconhecido" e o cliente repete com a mesma chave. No coordenador, um timeout na fase 2
nunca muda a decisao: o comando fica pendente e e repetido.

**Abort presumido.** Se o coordenador reinicia e encontra uma transferencia sem decisao gravada,
ninguem pode ter confirmado (o COMMIT so e enviado depois de gravado), por isso e seguro abortar.

**Concorrencia.** O `UPDATE contas SET saldo = saldo - m WHERE id = x AND saldo >= m` bloqueia a linha;
outra transferencia sobre a mesma conta espera. Quando a primeira termina, o PostgreSQL reavalia a
condicao com o saldo novo. Com 10 pedidos simultaneos e saldo para 6, passam exactamente 6.

**Bloqueio mutuo distribuido.** Se as preparacoes fossem em paralelo, A podia bloquear EU-1003 e B
bloquear US-2001, cada uma a espera da outra noutro no; nenhum PostgreSQL ve o ciclo. Solucao: todos
preparam pela mesma ordem (Europa, depois America). Foi medido: em paralelo, 8 de 10 abortavam.

**Idempotencia.** A mesma `Idempotency-Key` devolve a mesma transferencia (o PostgreSQL garante com
`UNIQUE`); com dados diferentes, 409. Permite repetir um pedido depois de um timeout sem duplicar.

**JWT RS256.** Cabecalho.carga.assinatura em Base64URL. A assinatura e RSA sobre o SHA-256 dos dois
primeiros blocos. Quem tem a chave publica verifica; so o `auth` tem a privada e pode emitir.

**Assinatura das ordens.** Os campos relevantes em JSON canonico (chaves ordenadas, sem espacos) →
SHA-256 → assinado com RSA-PSS pela chave privada da instancia da API. O coordenador verifica com a
publica antes de tocar em saldos. Mudar o montante muda o SHA-256 e a verificacao falha.

**Python e concorrencia.** O GIL impede duas threads de executar bytecode Python ao mesmo tempo, mas e
libertado durante E/S (rede, base de dados). Como estes servicos passam quase todo o tempo a espera de
E/S, threads (API) e asyncio (coordenador) dao concorrencia real. Para calculo intensivo usar-se-iam
processos (`multiprocessing`) ou varias instancias, como as duas APIs.

## 3. Perguntas provaveis e respostas curtas

**P: Porque 2PC e nao Saga?**
R: O enunciado pede ACID. Uma Saga confirma cada passo localmente e compensa depois, por isso ha um
momento em que o dinheiro saiu e ainda nao entrou (falta de isolamento). Com 2PC isso nunca e visivel.
A Saga escala melhor e nao bloqueia; seria a escolha se as transferencias envolvessem muitos servicos.

**P: O que acontece se o no America cair a meio?**
R: Depende do momento. Antes de preparar: ABORT, o Europa faz ROLLBACK PREPARED (cenario 5). Depois da
decisao COMMIT: o Europa confirma, o America fica pendente, e quando volta a transaccao preparada
continua la e o coordenador faz COMMIT PREPARED (cenario 6).

**P: E se cair o coordenador?**
R: Com decisao gravada, ao reiniciar repete-a nos dois nos (cenario 7a). Sem decisao, abort presumido
(cenario 7b). Enquanto esta em baixo, as linhas ficam bloqueadas: e o bloqueio do 2PC.

**P: Onde esta a decisao do coordenador e porque e duravel?**
R: Na tabela `transferencias` da base `db-coordenador`, num volume persistente. O `UPDATE ... SET
decisao='COMMIT'` e confirmado (WAL com fsync) antes de enviar o primeiro COMMIT PREPARED.

**P: O que e `max_prepared_transactions` e porque e preciso?**
R: Numero maximo de transaccoes preparadas em simultaneo. Por omissao e 0, o que desactiva o
`PREPARE TRANSACTION`. Esta a 40 (igual a `max_connections`, como recomenda a documentacao).

**P: Como impede saldo negativo com dois pedidos ao mesmo tempo?**
R: Bloqueio de linha do `UPDATE` com a condicao `saldo >= montante`, reavaliada depois da espera, mais
a restricao `CHECK (saldo_centimos >= 0)` como ultima defesa. Cenario 3.

**P: Porque centimos inteiros?**
R: `float` nao representa 0.10 exactamente; somas acumulam erros. `BIGINT` em centimos e exacto.

**P: Como sabe que a transferencia gerou um debito e um credito e nao mais?**
R: `UNIQUE (transferencia_id, tipo)` em `movimentos` e a verificacao global dos testes (evidencia 99),
que confere todas as transferencias e a soma dos saldos (10 600.00 EUR do principio ao fim).

**P: Como e que a API valida o token sem falar com o servico de autenticacao?**
R: Tem a chave publica RS256. Verifica a assinatura, `exp`, `iss` e `aud` localmente. Prova: com o
`auth` parado, a api-2 aceita o token (cenario 9). Desvantagem: um token roubado vale ate expirar
(15 min); mitigacao: validade curta ou lista de revogacao.

**P: Para que serve o SHA-256 na assinatura?**
R: Resume a mensagem canonica em 32 bytes; o RSA-PSS assina esse resumo. Qualquer alteracao produz
outro resumo e a verificacao falha (integridade). Como so a API tem a chave privada, prova tambem quem
enviou (autenticidade). Um hash sozinho nao chegava: um atacante recalculava-o.

**P: E se alguem repetir uma ordem assinada valida?**
R: Se tiver a mesma chave de idempotencia, devolve a transferencia existente (nao duplica). Se for
mais antiga que 120 s, e recusada pela janela temporal (cenario 10).

**P: Como protege a BD na rede?**
R: `ssl=on`, `pg_hba.conf` com `hostssl ... scram-sha-256` e `hostnossl ... reject`; os clientes usam
`sslmode=verify-full`, que verifica a CA e o nome do servidor. Papeis com privilegios minimos.

**P: E os dados em repouso?**
R: Configurado: palavras-passe com scrypt, chaves privadas fora do Git e montadas como secrets so nos
servicos que precisam, papeis com privilegios minimos. Nao configurado: cifragem do disco das BD.
Em producao: BitLocker/LUKS nos volumes ou `pgcrypto` para colunas sensiveis.

**P: Como funciona o DFS e o acesso concorrente?**
R: Um servidor NFSv4; o Docker monta-o em `/mnt/dfs` em tres servicos. Cada evento e um ficheiro com
nome unico, escrito com nome temporario e renomeado (atomico), por isso nao ha duas escritas no mesmo
ficheiro e nao e preciso bloqueio distribuido.

**P: E se o NFS cair?**
R: As transferencias continuam; os eventos ficam na pasta de espera local (volume persistente) e uma
thread publica-os quando o NFS voltar (cenario 12). Limite: o NFS e um ponto unico de falha para a
leitura da auditoria; alternativa replicada: GlusterFS ou CephFS.

**P: O que e a OMA e como se relaciona com o projecto?**
R: Arquitectura da OMG para objectos distribuidos: ORB (encaminha invocacoes entre objectos remotos),
IDL (contrato independente da linguagem), servicos de objectos (nomes, eventos, transaccoes,
seguranca). No projecto: o HTTP com JSON/XML faz o papel do ORB; OpenAPI e o XSD sao o IDL; o DNS do
Docker e o servico de nomes; o coordenador 2PC corresponde ao Object Transaction Service; TLS e JWT
ao Security Service. Diferenca: REST troca documentos sem estado, CORBA invocava metodos de objectos
remotos com referencias e estado.

**P: Porque Python? E o GIL?**
R: Bibliotecas maduras (FastAPI, psycopg, cryptography), asyncio nativo e codigo curto. O GIL nao e
problema porque o trabalho e quase todo E/S, e o GIL e libertado durante a E/S. Escala-se com mais
instancias (api-1 e api-2) em vez de mais threads.

**P: Como mostra que esta em dois computadores?**
R: `docker compose ps` em cada PC mostra servicos diferentes; `getent hosts db-america` no PC A da o IP
do PC B; `pg_stat_activity` no PC B mostra ligacoes vindas do IP do PC A; o `PREPARE TRANSACTION`
aparece nos logs do PC B.

**P: Porque nao ha balanceador de carga?**
R: Para manter o prototipo simples: o cliente tem a lista das duas APIs e muda de instancia quando uma
nao aceita ligacoes. Em producao usar-se-ia nginx/HAProxy ou um Service do Kubernetes, que tambem
seriam replicados para nao serem ponto unico de falha.

**P: O que nao esta resolvido?**
R: O coordenador e o NFS sao instancias unicas (o 2PC bloqueia se o coordenador ficar em baixo); nao
ha conversao de moedas; o disco das BD nao esta cifrado; o mTLS entre servicos nao esta activo (a
autenticacao dos servicos e feita pelas assinaturas das ordens e pelo JWT).
