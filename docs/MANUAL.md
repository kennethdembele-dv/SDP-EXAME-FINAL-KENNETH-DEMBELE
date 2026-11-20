# Manual de utilização do Global-Scale System

Manual prático: como arrancar o sistema, usar cada ecrã, demonstrar as falhas na defesa e desligar tudo.

---

## 1. O que precisa de estar instalado

| Programa | Para quê |
|---|---|
| Docker Desktop | Corre os 9 contentores (bases de dados, serviços, Java, NFS) |
| Python 3.12 | Gera os certificados e corre os testes e o cliente de linha de comandos |
| Um navegador (Edge, Chrome) | Usa a interface Web |

Neste computador o Docker Desktop está em `D:\Docker\Programa`. Se o Windows disser
*"Not enough memory to start the virtual machine"*, feche o navegador e outros programas pesados e
arranque o Docker Desktop de novo (a máquina virtual precisa de 2 GB livres).

---

## 2. Arrancar o sistema

Abra um terminal (PowerShell ou Git Bash) na pasta do projecto:

```sh
cd "D:\3ANO\SDP VSCODE\Global-Scale"
```

**Só da primeira vez** (cria a autoridade certificadora, os certificados, as chaves e as palavras-passe):

```sh
python seguranca/gerar_materiais.py
```

**Sempre:**

1. Abra o **Docker Desktop** e espere que, em baixo à esquerda, apareça *Engine running*.
2. Arranque os contentores:

   ```sh
   docker compose up -d
   ```

3. Confirme que os 9 estão `healthy` (demora cerca de 30 segundos):

   ```sh
   docker compose ps
   ```

| Contentor | O que é |
|---|---|
| `db-europa`, `db-america` | Bases de dados das contas europeias e americanas |
| `db-coordenador` | Livro de registos das decisões do coordenador |
| `auth` | Faz o login e emite o token JWT |
| `api-1`, `api-2` | As duas instâncias da API (e da interface Web) |
| `coordenador` | Coordena as transferências (Two-Phase Commit) |
| `banco-parceiro` | Banco externo em Java (XML) |
| `nfs` | Pasta partilhada com auditoria e relatórios |

---

## 3. Entrar na interface Web

1. Abra **https://localhost:8001/** (ou https://localhost:8002/, a outra instância).
2. Na primeira vez o navegador avisa que o certificado não é de confiança, porque é do laboratório.
   Clique em **Avançadas → Continuar para localhost**. Para não voltar a ver o aviso, corra uma vez:

   ```powershell
   certutil -addstore -user Root segredos\ca.crt
   ```

3. Clique num dos botões de demonstração, ou escreva o utilizador e a palavra-passe:

| Utilizador | Palavra-passe | Região | Contas |
|---|---|---|---|
| ana | Ana#2026 | Europa | EU-1001, EU-1002 |
| bruno | Bruno#2026 | Europa | EU-1003 |
| carlos | Carlos#2026 | América | US-2001 |
| diana | Diana#2026 | América | US-2002 |

No topo aparece sempre: a instância que respondeu (`api-1` ou `api-2`), o tempo que falta até o
token expirar (15 minutos) e o botão **Sair**.

---

## 4. Os ecrãs, um a um

### Painel
Resumo: saldo total, número de transferências concluídas, pendentes e abortadas, as suas contas e
uma bolinha verde ou vermelha por cada componente do sistema.

### Contas
Um cartão por conta: azul para a Europa, verde para a América. Clicar num cartão mostra o
**histórico** (débitos a vermelho, créditos a verde). O botão **Gerar extracto no DFS** grava um CSV
na pasta partilhada.

### Transferir
1. Escolha a **conta de origem** (só aparecem as suas).
2. Escreva a **conta de destino**, por exemplo `US-2001`. Por baixo aparece se é entre regiões
   (dois participantes no 2PC) ou na mesma região.
3. Escreva o **montante** (por exemplo `125,50`).
4. A **chave de idempotência** é gerada sozinha. Serve para que repetir o pedido nunca duplique.
5. Clique em **Transferir**.

À direita aparece o **percurso da transacção distribuída** em 5 passos:

| Passo | O que significa |
|---|---|
| 1. Ordem assinada e registada | A API assinou a ordem (RSA-PSS/SHA-256) e o coordenador aceitou-a |
| 2. Fase 1 — preparação | Cada nó reservou a sua parte (`PREPARE TRANSACTION`) e respondeu "pronto" |
| 3. Decisão global | O coordenador gravou COMMIT (ou ABORT) no seu registo |
| 4. Fase 2 — confirmação | Os nós tornaram a operação definitiva (`COMMIT PREPARED`) |
| 5. Banco parceiro | O banco Java confirmou com uma referência `BP-…` |

Cores: **verde** feito, **amarelo a piscar** à espera, **vermelho** falhou ou foi abortado.

- **Repetir com a mesma chave**: envia o mesmo pedido outra vez. Aparece *"repetido (idempotência)"*
  e o saldo não muda segunda vez.
- **↻** ao lado da chave: gera uma chave nova (para uma transferência nova).
- **Detalhe, auditoria e XML**: abre o painel lateral (ver Monitor 2PC).

Experimente também um montante maior do que o saldo: o resultado é **ABORTADA** (saldo insuficiente)
e nenhum saldo muda.

### Monitor 2PC
Tabela com todas as suas transferências: estado, estado de cada nó (EU e US) e confirmação do banco
parceiro. Actualiza-se sozinha a cada 3 segundos. Clicar numa linha abre o detalhe:
- **Consultar por XML**: pergunta ao banco Java e mostra o XML que ele devolveu;
- **Ler eventos**: mostra a auditoria guardada no NFS (que serviço fez o quê e quando);
- **Resposta JSON completa**: o que a API devolveu.

### Relatórios (DFS)
Escolha a conta e clique em **Gerar extracto CSV no DFS**. O ficheiro é escrito na pasta partilhada
(NFS) e aparece na lista. Clicar num ficheiro mostra o conteúdo e indica que instância o leu. Um
ficheiro escrito pela api-1 pode ser lido pela api-2 (transparência de localização).

### Estado do sistema
Um cartão por componente, verificado a cada 3 segundos pela API que está a responder: verde = a
funcionar, vermelho = em baixo. É o ecrã a deixar aberto durante a demonstração das falhas.
O botão **Usar a outra instância** passa os pedidos para a outra API.

### Segurança
Mostra o token JWT dividido em três partes (cabeçalho, dados, assinatura) e o significado de cada
campo (`iss` quem emitiu, `aud` para quem, `exp` quando expira...). Depois de uma transferência
mostra também o **SHA-256** da ordem que a API assinou.

---

## 5. Demonstração das falhas (para a defesa)

Deixe a interface aberta no **Estado do sistema** ou no **Monitor 2PC** e use um terminal na pasta do
projecto.

| Demonstração | Comando | O que se vê |
|---|---|---|
| Derrubar um nó da base de dados | `docker compose stop db-america` | O nó fica vermelho; uma transferência para US-2001 fica **ABORTADA** e nenhum saldo muda |
| Repor o nó | `docker compose start db-america` | Volta a verde em poucos segundos |
| Falha de rede (nó vivo mas sem responder) | `docker compose pause db-america` / `docker compose unpause db-america` | Durante a pausa o nó fica vermelho |
| Derrubar uma API | `docker compose stop api-1` | A página passa sozinha para a api-2 (aviso em baixo); repor com `docker compose start api-1` |
| Derrubar o coordenador | `docker compose stop coordenador` | Não se fazem transferências novas; ao arrancar (`start`) conclui as pendentes |
| Derrubar o banco Java | `docker compose stop banco-parceiro` | A transferência conclui; a confirmação fica pendente e é reenviada quando o Java voltar |
| Derrubar o NFS | `docker compose stop nfs` | As transferências continuam; a auditoria fica em espera e é publicada quando o NFS voltar |

**O caso mais importante (nó cai a meio da confirmação):**

```sh
python testes/lab.py pausa antes_commit_america 20   # o coordenador espera 20 s antes do COMMIT no América
```

Faça uma transferência EU-1001 → US-2001 na interface e, durante os 20 segundos, corra
`docker compose stop db-america`. A transferência fica **COMMIT_DECIDIDO** (amarelo): a Europa já
debitou e o América está pendente. Corra `docker compose start db-america`: em menos de 5 segundos a
transferência passa a **CONCLUIDA** sozinha e o crédito aparece. O dinheiro nunca se perde.

Mais passos e explicações: [ROTEIRO_DEFESA.md](ROTEIRO_DEFESA.md).

---

## 6. Outras formas de usar

**Documentação da API (Swagger):** https://localhost:8001/docs

**Linha de comandos:**

```sh
python scripts/cliente.py -u ana -p Ana#2026 contas
python scripts/cliente.py -u ana -p Ana#2026 transferir EU-1001 US-2001 25.00
python scripts/cliente.py -u ana -p Ana#2026 historico EU-1001
```

**Testes automáticos:**

```sh
python -m pytest testes/unitarios -q     # 33 testes, sem Docker
python testes/cenarios.py                # 13 cenários com falhas reais (grava em evidencias/)
```

---

## 7. Desligar

```sh
docker compose stop        # pára tudo e guarda os dados
docker compose down -v     # pára e APAGA os dados (o próximo "up" volta aos saldos iniciais)
```

Depois pode fechar o Docker Desktop (ícone da baleia junto ao relógio → *Quit Docker Desktop*).

---

## 8. Problemas frequentes

| Problema | Solução |
|---|---|
| A página não abre | Confirme `docker compose ps` (9 × healthy) e use **https://** |
| Aviso de certificado | Normal: "Avançadas → Continuar", ou instale a CA (secção 3) |
| *Sessão terminada: token expirado* | O token dura 15 minutos: entre de novo |
| Transferência amarela (COMMIT_DECIDIDO) muito tempo | Algum nó está em baixo: veja o Estado do sistema e arranque-o |
| *Not enough memory* no Docker Desktop | Feche programas pesados e arranque o Docker Desktop outra vez |
| Saldos estranhos depois de muitas experiências | `docker compose down -v` e `docker compose up -d` (volta aos dados iniciais) |
