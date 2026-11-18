# Execucao em dois computadores

O enunciado pede uma transferencia entre contas em nos **fisicamente diferentes**. Nesta
configuracao a conta europeia esta no PC A e a americana no PC B.

| PC A - "Europa" | PC B - "America" |
|---|---|
| `db-europa` (5433), `db-coordenador`, `coordenador` (8100) | `db-america` (5434) |
| `auth` (8000), `api-1` (8001) | `api-2` (8002) |
| `nfs` (2049): servidor do DFS | `banco-parceiro` (8200, Java) |

```
        PC A  192.168.1.10                              PC B  192.168.1.20
  ┌─────────────────────────────┐                ┌─────────────────────────────┐
  │ auth  api-1  coordenador    │── PREPARE ────►│ db-america                  │
  │ db-europa  db-coordenador   │◄── TLS 5433 ───│ api-2                       │
  │ nfs :2049                   │◄── NFS 2049 ───│ (monta /mnt/dfs do PC A)    │
  │                             │── XML 8200 ───►│ banco-parceiro (Java)       │
  └─────────────────────────────┘                └─────────────────────────────┘
```

## 1. Preparar (nos dois PCs)

1. Instalar o Docker Desktop (Windows) ou o Docker Engine (Linux) e o Python 3.12.
2. Copiar a pasta do projecto para os dois PCs (ou `git clone`).
3. **So no PC A**: `python seguranca/gerar_materiais.py`. Os certificados usam os nomes DNS dos
   servicos (`db-america`, `coordenador`, ...), por isso nao dependem dos IP e servem nos dois PCs.
4. Copiar do PC A para o PC B o ficheiro `.env` e a pasta `segredos/`. O PC B so precisa de:
   `ca.crt`, `db-america.crt/.key`, `api-2.crt/.key`, `jwt-publica.pem`, `assinatura-api-2.pem`,
   `banco-parceiro.p12`. A chave privada do JWT (`jwt-privada.pem`) e a da CA ficam so no PC A.
   Use uma pen USB ou `scp`; estes ficheiros nunca vao para o Git.
5. Descobrir os IP (`ipconfig` no Windows, `ip -4 addr` no Linux) e criar
   `distribuido/enderecos.env` a partir de `distribuido/enderecos.env.example`, igual nos dois PCs:

   ```
   IP_PC_A=192.168.1.10
   IP_PC_B=192.168.1.20
   NFS_ENDERECO=192.168.1.10
   ```

6. Abrir as portas na firewall (PowerShell como administrador, no Windows):

   ```powershell
   # PC A
   New-NetFirewallRule -DisplayName "Global-Scale PC A" -Direction Inbound -Protocol TCP -LocalPort 5433,8000,8001,8100,2049 -Action Allow
   # PC B
   New-NetFirewallRule -DisplayName "Global-Scale PC B" -Direction Inbound -Protocol TCP -LocalPort 5434,8002,8200 -Action Allow
   ```

   No Linux: `sudo ufw allow 5433,8000,8001,8100,2049/tcp` (PC A) e `sudo ufw allow 5434,8002,8200/tcp` (PC B).

## 2. Arrancar

```sh
# PC A (primeiro, porque tem o NFS e o coordenador)
docker compose -p gs-pc-a -f distribuido/pc-a.yml --env-file .env --env-file distribuido/enderecos.env up -d --build

# PC B
docker compose -p gs-pc-b -f distribuido/pc-b.yml --env-file .env --env-file distribuido/enderecos.env up -d --build
```

Como funciona a resolucao de nomes: cada contentor recebe, por `extra_hosts`, uma entrada no seu
ficheiro `/etc/hosts` com os nomes do outro PC (no PC A, `db-america` → IP do PC B; no PC B,
`db-europa`, `coordenador` e `auth` → IP do PC A). Os nomes locais continuam a ser resolvidos pelo
DNS interno do Docker. Os servicos usam sempre os mesmos nomes; so muda o endereco por tras deles,
por isso a verificacao TLS do nome do servidor continua a funcionar.

## 3. Comprovar a distribuicao na demonstracao

```sh
# No PC A: os contentores locais (nao ha db-america aqui)
docker compose -p gs-pc-a -f distribuido/pc-a.yml ps

# No PC A: o coordenador resolve db-america para o IP do PC B
docker compose -p gs-pc-a -f distribuido/pc-a.yml exec coordenador getent hosts db-america

# No PC B: o servidor PostgreSQL ve as ligacoes TLS que vem do PC A (client_addr = IP do PC A)
docker compose -p gs-pc-b -f distribuido/pc-b.yml exec db-america psql -U postgres -p 5434 -d globalscale \
  -c "SELECT a.client_addr, a.usename, s.ssl, s.version FROM pg_stat_ssl s JOIN pg_stat_activity a USING (pid) WHERE a.client_addr IS NOT NULL"

# Transferencia Europa (PC A) -> America (PC B), a partir de qualquer PC
GS_APIS=https://<IP_PC_A>:8001,https://<IP_PC_B>:8002 GS_AUTH=https://<IP_PC_A>:8000 \
  python scripts/cliente.py -u ana -p Ana#2026 transferir EU-1001 US-2001 50.00

# No PC B: o PREPARE e o COMMIT PREPARED chegaram ao no America
docker compose -p gs-pc-b -f distribuido/pc-b.yml logs db-america | grep PREPARE
```

Para o cliente aceitar `https://<IP>:8001`, os certificados tem de incluir o IP, ou entao acrescenta-se
ao ficheiro hosts do computador do cliente `192.168.1.10 api-1 auth` e `192.168.1.20 api-2`, e usa-se
`GS_APIS=https://api-1:8001,https://api-2:8002 GS_AUTH=https://auth:8000`. A segunda opcao nao obriga a
gerar certificados novos e e a recomendada.

**Falha de rede real:** durante uma transferencia, desligar o cabo ou o Wi-Fi do PC B produz o mesmo
efeito que `docker compose stop db-america` nos cenarios 5 e 6: a transferencia fica ABORTADA (se o
PC B caiu antes de preparar) ou COMMIT_DECIDIDO (se caiu depois da decisao) e conclui quando a rede
voltar.

## Testes que dependem dos dois computadores

| Cenario | Num PC | Com dois PCs |
|---|---|---|
| 1 Transferencia Europa → America | Contentores diferentes no mesmo PC | Nos em maquinas diferentes (prova fisica) |
| 5 Falha durante a preparacao | `docker compose stop db-america` | Desligar a rede do PC B |
| 6 Falha durante a confirmacao | `docker compose stop db-america` | Desligar a rede do PC B durante a pausa |
| 8 Queda da API | Parar api-1 | Desligar o PC A da rede do cliente: o cliente usa api-2 no PC B |
| 12 DFS | Varios contentores montam o NFS | api-2 no PC B monta o NFS do PC A pela rede |

Os cenarios automaticos (`testes/cenarios.py`) correm na configuracao de um PC. Com dois PCs os
mesmos passos fazem-se a mao, pelo roteiro em [ROTEIRO_DEFESA.md](ROTEIRO_DEFESA.md).

## Ensaio num so PC

Para verificar os dois ficheiros sem segundo computador, corre-se os dois projectos no mesmo Docker
(depois de `docker compose down` da configuracao local, porque as portas sao as mesmas):

```
# distribuido/enderecos.env
IP_PC_A=host-gateway
IP_PC_B=host-gateway
NFS_ENDERECO=127.0.0.1
```

`host-gateway` e o endereco do proprio anfitriao visto de dentro dos contentores, por isso o trafego
entre os "dois PCs" sai do contentor e volta a entrar pelas portas publicadas, como numa rede real.

## Servidor e clientes NFS

**No ambiente de desenvolvimento (Windows com Docker Desktop)** o anfitriao nao monta NFSv4: o
Windows 10 nao tem servidor NFS e o "Cliente para NFS" do Windows so fala NFSv2/v3. Por isso o servidor
e o contentor `nfs` (NFS-Ganesha, NFSv4 em espaco de utilizador) e a montagem e feita pelo Docker, que
corre numa maquina virtual Linux: o volume `dfs` (tipo `nfs`) e montado pelo cliente NFS do kernel Linux
dessa maquina e entregue aos contentores em `/mnt/dfs`. Pode confirmar-se com
`docker compose exec api-1 grep /mnt/dfs /proc/mounts` (tipo `nfs4`).

**Numa instalacao real em Linux (sem Docker para o NFS)**, os comandos equivalentes sao:

```sh
# PC A - servidor NFS do kernel
sudo apt install nfs-kernel-server
sudo mkdir -p /srv/dfs/auditoria /srv/dfs/relatorios
sudo chown -R nobody:nogroup /srv/dfs && sudo chmod -R 0775 /srv/dfs
echo "/srv/dfs 192.168.1.0/24(rw,sync,no_subtree_check,fsid=0)" | sudo tee -a /etc/exports
sudo exportfs -ra && sudo systemctl enable --now nfs-server
sudo exportfs -v                                    # confirma a exportacao

# PC A e PC B - cliente NFS (montado onde correm as APIs e o coordenador)
sudo apt install nfs-common
sudo mkdir -p /mnt/dfs
sudo mount -t nfs4 -o rw,soft,timeo=50,retrans=2 192.168.1.10:/ /mnt/dfs
echo "192.168.1.10:/ /mnt/dfs nfs4 rw,soft,timeo=50,retrans=2,_netdev 0 0" | sudo tee -a /etc/fstab
mount | grep /mnt/dfs                               # tipo nfs4
```

Com o NFS do sistema montado em `/mnt/dfs`, o volume `dfs` dos ficheiros Compose pode ser trocado por
uma montagem directa (`- /mnt/dfs:/mnt/dfs`). As opcoes `soft,timeo=50,retrans=2` fazem as escritas
falharem com erro ao fim de alguns segundos se o servidor cair, em vez de bloquearem; o servico guarda
entao os eventos na pasta de espera local e publica-os quando o NFS voltar.

## Confianca na CA

Para o navegador (Swagger) e o `curl` aceitarem os certificados sem `--cacert`:

- **Windows:** `certutil -addstore -user Root segredos\ca.crt` (ou abrir o ficheiro e escolher
  "Instalar certificado" → "Autoridades de Certificacao de Raiz Fidedigna").
- **Linux (Debian/Ubuntu):** `sudo cp segredos/ca.crt /usr/local/share/ca-certificates/global-scale.crt && sudo update-ca-certificates`.

Os contentores nao precisam disto: recebem `ca.crt` como segredo e verificam os servidores com ela.
No fim do laboratorio, remover a CA: `certutil -delstore -user Root "Global-Scale Laboratorio CA"`.

## Limites desta configuracao

- O coordenador e o NFS ficam so no PC A: se o PC A cair, nao se fazem transferencias novas e o
  DFS fica indisponivel (o PC B guarda os eventos de auditoria na pasta de espera local).
- O NFS nao tem autenticacao forte (`sec=sys`); deve ficar numa rede de laboratorio fechada. Em
  producao usar-se-ia Kerberos (`sec=krb5p`) ou uma VPN entre os dois PCs.
