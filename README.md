# Global-Scale System

Plataforma financeira distribuida (prototipo) para a Global Scale Corporation.
Exame pratico de Sistemas Distribuidos e Paralelos, ISUTC, LECC. Kenneth Dembele.

O sistema faz transferencias de dinheiro entre contas guardadas em nos de base de dados diferentes
(Europa e America) com **Two-Phase Commit** sobre transaccoes preparadas reais do PostgreSQL. Tem
duas instancias da API REST, autenticacao JWT descentralizada, assinaturas digitais nas ordens,
TLS em todas as ligacoes, auditoria num sistema de ficheiros distribuido (NFS) e um modulo legado em Java.

## Arquitectura

```
                         clientes (scripts/cliente.py, Swagger, curl) - HTTPS
                 ┌──────────────────────┬──────────────────────┬────────────────────┐
                 ▼                      ▼                      ▼                    │
          auth :8000             api-1 :8001            api-2 :8002                 │
          emite JWT RS256        valida JWT localmente (chave publica)              │
          (chave privada)        assina a ordem (RSA-PSS + SHA-256)                 │
                 │                      │  HTTPS            │                       │
                 │                      └────────┬──────────┘                       │
                 │                               ▼                                  │
                 │                      coordenador :8100 ── HTTPS + XML ──► banco-parceiro :8200
                 │                      2PC + recuperacao                    (Java, legado)
                 │                       │        │      │
                 │      PostgreSQL TLS (verify-full)     └──► db-coordenador :5435 (decisoes 2PC)
                 ▼                       ▼        ▼
          db-europa :5433  ◄──────  PREPARE TRANSACTION / COMMIT PREPARED  ──────►  db-america :5434
          contas EU-xxxx                                                            contas US-xxxx

          nfs :2049 (NFSv4) ── montado em /mnt/dfs por api-1, api-2 e coordenador (auditoria e relatorios)
```

Diagrama detalhado, redes e modelo de dados: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

| Servico | Tecnologia | Porta | Funcao |
|---|---|---|---|
| `auth` | Python, FastAPI | 8000 HTTPS | Verifica a palavra-passe (scrypt) e emite JWT RS256 |
| `api-1`, `api-2` | Python, FastAPI | 8001, 8002 HTTPS | API REST: contas, saldo, historico, transferencias, relatorios |
| `coordenador` | Python, FastAPI, asyncio | 8100 HTTPS | Coordenador 2PC, idempotencia, recuperacao |
| `db-europa` | PostgreSQL 17 | 5433 TLS | Fragmento Europa (contas `EU-xxxx`) |
| `db-america` | PostgreSQL 17 | 5434 TLS | Fragmento America (contas `US-xxxx`) |
| `db-coordenador` | PostgreSQL 17 | 5435 TLS | Registo duravel das decisoes do coordenador |
| `banco-parceiro` | Java 21 (so JDK) | 8200 HTTPS | Banco parceiro legado, contrato XML |
| `nfs` | NFS-Ganesha (NFSv4) | 2049 | Sistema de ficheiros distribuido |

## Requisitos

- Docker Desktop (Windows) ou Docker Engine (Linux) com Docker Compose v2.20 ou mais recente.
  Testado com Docker Desktop 4.99 (backend Hyper-V, VM com 2 GB e 2 CPUs), Docker 29.9.3 e Compose v5.7.0.
- Python 3.12 no anfitriao, para gerar os certificados e correr os testes:
  `pip install cryptography==50.0.2 httpx==0.28.1 PyJWT==2.15.1 pytest==9.2.0`
- Cerca de 1,5 GB de RAM livre para os contentores (todos tem limite de memoria).

## Instalacao e arranque (um computador)

```sh
python seguranca/gerar_materiais.py     # 1. CA, certificados, chaves JWT e de assinatura, .env
docker compose up -d --build            # 2. constroi e arranca os 9 contentores
docker compose ps                       # 3. todos devem ficar "healthy"
```

O primeiro arranque demora alguns minutos (descarrega as imagens e compila o Java). Os dados de
demonstracao sao carregados automaticamente:

| Utilizador | Palavra-passe | Regiao | Contas (saldo inicial, EUR) |
|---|---|---|---|
| `ana` | `Ana#2026` | Europa | EU-1001 (5000.00), EU-1002 (1500.00) |
| `bruno` | `Bruno#2026` | Europa | EU-1003 (300.00) |
| `carlos` | `Carlos#2026` | America | US-2001 (3000.00) |
| `diana` | `Diana#2026` | America | US-2002 (800.00) |

Estas palavras-passe sao ficticias e so existem para o laboratorio.

## Utilizacao

**Swagger (OpenAPI):** <https://localhost:8001/docs> e <https://localhost:8002/docs>.
Para o navegador aceitar o certificado, instale `segredos/ca.crt` como autoridade de confianca
(ver [docs/DOIS_COMPUTADORES.md](docs/DOIS_COMPUTADORES.md#confianca-na-ca)). A especificacao esta
em `/openapi.json` e exportada em [docs/openapi/](docs/openapi/) (`python scripts/exportar_openapi.py`).

**Cliente de linha de comandos** (com failover entre api-1 e api-2):

```sh
python scripts/cliente.py -u ana -p Ana#2026 contas
python scripts/cliente.py -u ana -p Ana#2026 transferir EU-1001 US-2001 125.50
python scripts/cliente.py -u ana -p Ana#2026 estado <id-da-transferencia>
python scripts/cliente.py -u ana -p Ana#2026 historico EU-1001
python scripts/cliente.py -u ana -p Ana#2026 parceiro <id>      # registo no banco Java (XML)
python scripts/cliente.py -u ana -p Ana#2026 auditoria <id>     # eventos no DFS
```

**curl:**

```sh
TOKEN=$(curl -s --cacert segredos/ca.crt https://localhost:8000/api/v1/autenticacao/token \
  -H "Content-Type: application/json" -d '{"utilizador":"ana","palavra_passe":"Ana#2026"}' | python -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
curl -s --cacert segredos/ca.crt https://localhost:8001/api/v1/contas -H "Authorization: Bearer $TOKEN"
curl -s --cacert segredos/ca.crt https://localhost:8001/api/v1/transferencias -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: demo-0001" -H "Content-Type: application/json" \
  -d '{"conta_origem":"EU-1001","conta_destino":"US-2001","montante":"125.50"}'
```

### Endpoints

| Metodo | Caminho | Descricao |
|---|---|---|
| POST | `/api/v1/autenticacao/token` (auth) | Login; devolve o JWT |
| GET | `/api/v1/contas` | Contas do utilizador |
| GET | `/api/v1/contas/{conta}` e `/saldo` | Detalhe e saldo |
| GET | `/api/v1/contas/{conta}/movimentos` | Historico |
| POST | `/api/v1/transferencias` | Transferencia (cabecalho `Idempotency-Key` obrigatorio) |
| GET | `/api/v1/transferencias?chave=` | Transferencias do utilizador (ou por chave) |
| GET | `/api/v1/transferencias/{id}` | Estado, participantes e confirmacao do parceiro |
| GET | `/api/v1/transferencias/{id}/auditoria` | Eventos da transferencia no DFS |
| GET | `/api/v1/parceiro/transferencias/{id}` | Consulta no banco parceiro (Java) |
| POST/GET | `/api/v1/relatorios/extracto`, `/api/v1/relatorios[/{nome}]` | Extractos CSV no DFS |

Estados de uma transferencia: `INICIADA` → `PREPARADA` → `COMMIT_DECIDIDO` → `CONCLUIDA`, ou
`ABORT_DECIDIDO` → `ABORTADA`. `COMMIT_DECIDIDO` (HTTP 202) significa que a decisao esta gravada e
que falta aplica-la num no que nao respondeu; a recuperacao conclui-a sozinha.

## Testes

```sh
python -m pytest testes/unitarios -q    # sem Docker: dinheiro, assinaturas, JWT, scrypt, XML (30 testes)
python testes/cenarios.py               # com o sistema a correr: cenarios 0 a 12 com evidencias
python testes/cenarios.py 6 7           # so alguns cenarios
python testes/ensaio_distribuido.py     # ensaio dos ficheiros de dois PCs num so PC (ver docs/DOIS_COMPUTADORES.md)
```

Resultados obtidos (Docker Desktop 4.99, Windows 10): os 13 cenarios e a verificacao global passaram numa
execucao a partir de um clone limpo ([evidencias/REPRODUCAO_LIMPA.md](evidencias/REPRODUCAO_LIMPA.md)), e o
ensaio de dois PCs passou nas 9 verificacoes ([evidencias/13_ensaio_dois_pcs.md](evidencias/13_ensaio_dois_pcs.md)).

Os resultados ficam em [evidencias/](evidencias/) (um `.md` e um `.json` por cenario, mais
`RESUMO.md`). Os cenarios param e arrancam contentores (`docker compose stop/kill/start`) para
provocar falhas reais.

| # | Cenario |
|---|---|
| 0 | Ambiente, redes, DNS e TLS (incluindo ligacoes recusadas sem TLS) |
| 1 | Transferencia bem-sucedida entre Europa e America |
| 2 | Saldo insuficiente e validacoes |
| 3 | 10 transferencias concorrentes sobre a mesma conta |
| 4 | Repeticao com a mesma chave de idempotencia (e chave reutilizada com outros dados) |
| 5 | Falha de um participante antes e durante a preparacao |
| 6 | Falha durante a confirmacao (queda do no e falha de rede) e recuperacao |
| 7 | Reinicio do coordenador com transaccoes pendentes (COMMIT gravado e abort presumido) |
| 8 | Queda de uma instancia da API e utilizacao da outra |
| 9 | Token invalido/expirado e acesso a conta de outro utilizador |
| 10 | Mensagem de transferencia adulterada |
| 11 | Comunicacao Python ↔ Java, XML invalido e Java indisponivel |
| 12 | Escrita e leitura no NFS e falha do NFS |

## Demonstracao e recuperacao

O roteiro da defesa, com os comandos para derrubar e recuperar cada servico, esta em
[docs/ROTEIRO_DEFESA.md](docs/ROTEIRO_DEFESA.md). Resumo:

```sh
docker compose stop db-america        # derrubar um no da base de dados
python scripts/cliente.py -u ana -p Ana#2026 transferir EU-1001 US-2001 10.00   # -> 503 ABORTADA
docker compose start db-america

docker compose pause db-america       # falha de rede: o no fica vivo mas nao responde
docker compose unpause db-america
docker compose stop api-1             # derrubar uma instancia da API: o cliente usa a api-2
docker compose kill coordenador       # queda abrupta do coordenador
docker compose start coordenador      # a recuperacao de arranque conclui ou aborta o que ficou pendente
docker compose logs -f coordenador    # ver PREPARADO, DECISAO_COMMIT, CONFIRMADO, ...
```

Para ver o estado do 2PC directamente nas bases de dados:

```sh
docker compose exec db-europa psql -U postgres -p 5433 -d globalscale -c "SELECT gid, prepared FROM pg_prepared_xacts"
docker compose exec db-coordenador psql -U postgres -p 5435 -d globalscale \
  -c "SELECT id, estado, decisao, codigo_erro FROM transferencias ORDER BY criada_em DESC LIMIT 5"
```

## Dois computadores

O enunciado pede contas em nos fisicamente diferentes. Os ficheiros `distribuido/pc-a.yml` (Europa,
coordenador, autenticacao, api-1, NFS) e `distribuido/pc-b.yml` (America, api-2, banco parceiro)
distribuem os servicos por dois PCs. Instrucoes completas: [docs/DOIS_COMPUTADORES.md](docs/DOIS_COMPUTADORES.md).

## Decisoes

| Decisao | Motivo |
|---|---|
| 2PC (e nao Saga) | O enunciado pede ACID: com 2PC nunca ha um estado intermedio visivel em que o dinheiro saiu e nao entrou. As transaccoes preparadas do PostgreSQL sobrevivem a reinicios |
| Moeda unica (EUR) | Simplifica a demonstracao; o campo `moeda` existe em todo o lado e contas noutra moeda sao recusadas |
| Centimos inteiros (`BIGINT`) | Sem erros de arredondamento; a API recebe texto decimal (`"125.50"`) |
| Registo do coordenador em PostgreSQL proprio | Decisao duravel (WAL com fsync) e independente dos participantes |
| Failover no cliente (sem balanceador) | Menos um servico; cada instancia e independente e o JWT e validado localmente |
| Java so com o JDK (sem Maven) | O modulo legado compila com `javac` e nao tem dependencias |
| Um ficheiro por evento no DFS | Evita escritas concorrentes no mesmo ficheiro e bloqueios distribuidos |

## Problemas frequentes

| Sintoma | Solucao |
|---|---|
| Docker Desktop: `Not enough memory to start the virtual machine` | Com o backend Hyper-V a VM reserva a memoria toda no arranque. Fechar programas (navegador) e baixar a memoria em Settings → Resources (2 GB chegam; foi o valor usado nos testes) |
| `invalid mount config` / ficheiros de `bd/` ou `segredos/` nao encontrados | Com o backend Hyper-V, acrescentar a pasta do projecto em Settings → Resources → File sharing (com WSL 2 nao e preciso) |
| `corra python seguranca/gerar_materiais.py` ao arrancar | Falta o `.env`: gere os materiais |
| `api-1`/`coordenador` nao arrancam: `mount.nfs: Connection refused` | O NFS ainda nao estava pronto: `docker compose up -d` outra vez |
| `certificate verify failed` no cliente | Use `--cacert segredos/ca.crt` (ou instale a CA); use `localhost` e nao o IP |
| `401 token expirado` | O token dura 15 minutos: faca login de novo |
| Transferencia fica `COMMIT_DECIDIDO` | Um no esta em baixo: arranque-o (`docker compose start db-america`); a recuperacao conclui em 5 s |
| `409 a conta esta bloqueada` | Existe uma transaccao preparada a espera do coordenador; arranque o coordenador |
| Os certificados mudaram (`--forcar`) | `docker compose down -v` e `up -d` (os volumes guardam dados antigos) |
| Recomecar do zero | `docker compose down -v` apaga os dados; o proximo `up` recarrega os dados de demonstracao |

## Estrutura

```
servicos/      autenticacao/, api/, coordenador/ (dois_fases.py = 2PC), comum/ (TLS, JWT, assinatura, DFS)
banco-parceiro/ BancoParceiro.java, contrato.xsd, Dockerfile
bd/            migracoes SQL (regional, europa, america, coordenador), pg_hba.conf, arranque com TLS
nfs/           servidor NFS-Ganesha
seguranca/     gerar_materiais.py (CA, certificados, chaves; nada disto vai para o Git)
distribuido/   pc-a.yml, pc-b.yml, enderecos.env.example
scripts/       cliente.py, exportar_openapi.py
testes/        unitarios/ (pytest), cenarios.py (12 cenarios com evidencias)
evidencias/    resultados reais dos testes
docs/          arquitectura, dois computadores, roteiro da defesa, guia de estudo, openapi/, relatorio (Word e PDF)
```
