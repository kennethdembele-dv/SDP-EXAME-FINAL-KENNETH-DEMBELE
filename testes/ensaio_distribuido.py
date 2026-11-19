"""Ensaio da configuracao de dois computadores num so PC (distribuido/pc-a.yml + pc-b.yml).

    python testes/ensaio_distribuido.py        (com distribuido/enderecos.env em modo host-gateway)

Arranca o projecto gs-pc-a e o gs-pc-b, faz transferencias nos dois sentidos e mostra que o trafego
entre os "dois PCs" passa pelas portas publicadas: o coordenador (PC A) prepara no db-america (PC B),
o api-2 (PC B) monta o NFS do PC A e le a auditoria escrita no PC A. Grava
evidencias/13_ensaio_dois_pcs.md. Com dois computadores reais, os mesmos comandos correm um em cada PC.
"""
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from cliente import Cliente  # noqa: E402

ARGS = {"a": ["-p", "gs-pc-a", "-f", "distribuido/pc-a.yml"], "b": ["-p", "gs-pc-b", "-f", "distribuido/pc-b.yml"]}
ENV = ["--env-file", ".env", "--env-file", "distribuido/enderecos.env"]
linhas: list[str] = []
verificacoes: list[tuple[str, bool]] = []


def dc(pc, *args, timeout=900):
    r = subprocess.run(["docker", "compose", *ARGS[pc], *ENV, *args], cwd=RAIZ, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def registar(titulo, texto):
    print(f"--- {titulo}")                     # no ecra so as primeiras linhas; o ficheiro tem tudo
    for l in [l for l in texto.splitlines() if l.strip()][:4]:
        print(f"    {l[:104]}")
    linhas.extend([f"## {titulo}", "", "```", texto, "```", ""])


def verificar(descricao, ok):
    print(("OK  " if ok else "FALHOU ") + descricao)
    verificacoes.append((descricao, bool(ok)))


def saudaveis(pc, n):
    for _ in range(60):
        if dc(pc, "ps", "--format", "{{.Health}}").count("healthy") >= n:
            return True
        time.sleep(5)
    return False


registar("Enderecos usados", (RAIZ / "distribuido" / "enderecos.env").read_text(encoding="utf-8").strip())
print(dc("a", "up", "-d", "--build")[-300:])
verificar("PC A: 6 servicos healthy", saudaveis("a", 6))
print(dc("b", "up", "-d", "--build")[-300:])
verificar("PC B: 3 servicos healthy", saudaveis("b", 3))
registar("PC A: docker compose ps", dc("a", "ps", "--format", "table {{.Name}}\t{{.Status}}\t{{.Ports}}"))
registar("PC B: docker compose ps", dc("b", "ps", "--format", "table {{.Name}}\t{{.Status}}\t{{.Ports}}"))
hosts = dc("a", "exec", "-T", "coordenador", "getent", "hosts", "db-america", "banco-parceiro")
registar("PC A: o coordenador resolve os nomes do PC B (extra_hosts)", hosts)
verificar("db-america e banco-parceiro resolvidos por extra_hosts no PC A", "db-america" in hosts and "banco-parceiro" in hosts)

ana = Cliente(apis=["https://localhost:8001"], mostrar=False)       # api-1 no PC A
ana.login("ana", "Ana#2026")
r1 = ana.transferir("EU-1001", "US-2001", "50.00")
carlos = Cliente(apis=["https://localhost:8002"], mostrar=False)    # api-2 no PC B
carlos.login("carlos", "Carlos#2026")
r2 = carlos.transferir("US-2001", "EU-1002", "20.00")
registar("Transferencias entre os dois PCs", f"ana EU-1001 -> US-2001 via api-1 (PC A): HTTP {r1.status_code} {r1.json()['estado']}\n"
         f"carlos US-2001 -> EU-1002 via api-2 (PC B): HTTP {r2.status_code} {r2.json()['estado']} "
         f"(ordem assinada por {r2.json()['instancia_api']})")
verificar("Europa (PC A) -> America (PC B): CONCLUIDA", r1.status_code == 201 and r1.json()["estado"] == "CONCLUIDA")
verificar("America (PC B) -> Europa (PC A) via api-2: CONCLUIDA", r2.status_code == 201 and r2.json()["estado"] == "CONCLUIDA")

tid = r1.json()["id"]
logs = "\n".join(l.split("LOG:", 1)[-1].strip() for l in dc("b", "logs", "--no-color", "db-america").splitlines()
                 if tid in l and "PREPARE" in l)
registar("PC B: comandos 2PC recebidos pelo db-america (vindos do coordenador no PC A)", logs)
verificar("o db-america do PC B recebeu PREPARE TRANSACTION e COMMIT PREPARED",
          "PREPARE TRANSACTION" in logs and "COMMIT PREPARED" in logs)
# O coordenador abre uma ligacao por operacao; para a observar no servidor, abre-se uma de 6 s com o seu DSN.
dc("a", "exec", "-d", "coordenador", "python", "-c",
   "import os, psycopg; from comum import bd; c = psycopg.connect(bd.dsn_no('america', 'gs_transaccoes', "
   "os.environ['PG_SENHA_TRANSACCOES'])); c.execute('SELECT pg_sleep(6)')")
time.sleep(2.5)
ssl = dc("b", "exec", "-T", "db-america", "psql", "-U", "postgres", "-p", "5434", "-d", "globalscale", "-At", "-F", " | ",
         "-c", "SELECT a.application_name, a.usename, host(a.client_addr), s.ssl, s.version FROM pg_stat_ssl s "
               "JOIN pg_stat_activity a USING (pid) WHERE a.application_name = 'coordenador'")
registar("PC B: ligacao do coordenador (PC A) vista pelo db-america: servico | papel | origem | ssl | versao", ssl)
verificar("a ligacao do coordenador do PC A ao db-america do PC B usa TLS 1.3", "| t | TLSv1.3" in ssl)
montagem = dc("b", "exec", "-T", "api-2", "sh", "-c", "grep ' /mnt/dfs ' /proc/mounts")
registar("PC B: o api-2 monta o NFS do PC A", montagem)
verificar("api-2 (PC B) monta /mnt/dfs por nfs4", " nfs4 " in montagem)
time.sleep(6)
aud = carlos.pedido("GET", f"/api/v1/transferencias/{r2.json()['id']}/auditoria").json()
registar("PC B: auditoria lida pelo api-2 no DFS do PC A",
         "\n".join(f"{e['servico']:<12} {e['evento']:<22} {e['ficheiro']}" for e in aud["eventos"]))
verificar("o api-2 (PC B) le eventos escritos pelo coordenador (PC A) e por si proprio",
          {"coordenador", "api-2"} <= {e["servico"] for e in aud["eventos"]})

if "--manter" not in sys.argv:
    dc("b", "down", "-v")
    dc("a", "down", "-v")
ok = sum(1 for _, o in verificacoes if o)
md = ["# Ensaio da configuracao de dois computadores num so PC", "",
      f"**Resultado: {'PASSOU' if ok == len(verificacoes) else 'FALHOU'}** ({ok}/{len(verificacoes)} verificacoes, "
      f"executado em {time.strftime('%Y-%m-%d %H:%M:%S')}).", "",
      "Os dois projectos (gs-pc-a e gs-pc-b) correm no mesmo Docker, mas so comunicam pelas portas publicadas, "
      "atraves de `host-gateway`, como fariam dois computadores. Com dois PCs reais troca-se `host-gateway` pelos IP "
      "(docs/DOIS_COMPUTADORES.md); este ensaio nao substitui a prova fisica com duas maquinas.", ""] + linhas + \
     ["## Verificacoes", ""] + [f"- {'[x]' if o else '[ ] FALHOU:'} {d}" for d, o in verificacoes]
(RAIZ / "evidencias" / "13_ensaio_dois_pcs.md").write_text("\n".join(md) + "\n", encoding="utf-8")
sys.exit(0 if ok == len(verificacoes) else 1)
