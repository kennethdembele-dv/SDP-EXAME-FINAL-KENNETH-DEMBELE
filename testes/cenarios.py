"""Cenarios de demonstracao com evidencias (sistema a correr em Docker no proprio PC).

    python testes/cenarios.py            todos (0 a 12)
    python testes/cenarios.py 5 6 7      so alguns

Cada cenario grava evidencias/NN_nome.md (legivel) e evidencias/NN_nome.json (dados).
Os saldos sao lidos DIRECTAMENTE nos nos PostgreSQL (docker compose exec ... psql), de forma
independente da API, e no fim verifica-se em todo o sistema:
  - a soma dos saldos nao mudou (conservacao dos fundos);
  - cada transferencia CONCLUIDA tem exactamente um DEBITO e um CREDITO;
  - cada transferencia ABORTADA nao tem movimentos;
  - nao ficou nenhuma transaccao preparada por resolver.
"""
import base64
import concurrent.futures as cf
import datetime as dt
import json
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

import httpx
import jwt as pyjwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "servicos"))
import os  # noqa: E402

os.environ.setdefault("SEGREDOS", str(RAIZ / "segredos"))
from cliente import Cliente  # noqa: E402
from comum import assinatura  # noqa: E402

os.environ.setdefault("GS_APIS", f"https://{os.environ.get('GS_HOST', 'localhost')}:8001,"
                                 f"https://{os.environ.get('GS_HOST', 'localhost')}:8002")

EVID = RAIZ / "evidencias"
CA = str(RAIZ / "segredos" / "ca.crt")
HOST = os.environ.get("GS_HOST", "localhost")
API1, API2 = f"https://{HOST}:8001", f"https://{HOST}:8002"
COORD = f"https://{HOST}:8100"
PARCEIRO = f"https://{HOST}:8200"
SENHAS = {"ana": "Ana#2026", "bruno": "Bruno#2026", "carlos": "Carlos#2026", "diana": "Diana#2026"}
ENV = dict(l.split("=", 1) for l in (RAIZ / ".env").read_text(encoding="utf-8").splitlines()
           if "=" in l and not l.startswith("#"))
NOS = {"europa": ("db-europa", 5433), "america": ("db-america", 5434)}
CONTEXTO: dict = {}


# ================================================================ utilitarios
def compose(*args, timeout=180) -> str:
    r = subprocess.run(["docker", "compose", *args], cwd=RAIZ, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def psql(servico: str, porta: int, sql: str) -> list[list[str]]:
    r = subprocess.run(["docker", "compose", "exec", "-T", servico, "psql", "-U", "postgres", "-p", str(porta),
                        "-d", "globalscale", "-At", "-F", "|", "-c", sql],
                       cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"psql {servico}: {r.stderr.strip()}")
    return [l.split("|") for l in r.stdout.strip().splitlines() if l]


def coord_sql(sql: str):
    return psql("db-coordenador", 5435, sql)


def saldos() -> dict[str, int]:
    s = {}
    for servico, porta in NOS.values():
        for conta, saldo in psql(servico, porta, "SELECT id, saldo_centimos FROM contas ORDER BY id"):
            s[conta] = int(saldo)
    return s


def preparadas() -> dict[str, list[str]]:
    return {no: [g for (g,) in psql(s, p, "SELECT gid FROM pg_prepared_xacts WHERE gid LIKE 'gs-%'")]
            for no, (s, p) in NOS.items()}


def movimentos(tid: str) -> list[tuple]:
    m = []
    for no, (s, p) in NOS.items():
        for tipo, conta, montante in psql(s, p, f"SELECT tipo, conta_id, montante_centimos FROM movimentos "
                                                f"WHERE transferencia_id = '{tid}' ORDER BY tipo"):
            m.append((no, tipo, conta, int(montante)))
    return m


def estado_bd(tid: str) -> dict:
    linhas = coord_sql(f"SELECT estado, coalesce(decisao,''), coalesce(codigo_erro,''), parceiro_estado "
                       f"FROM transferencias WHERE id = '{tid}'")
    if not linhas:
        return {}
    e, d, c, p = linhas[0]
    parts = {no: est for no, est in coord_sql(f"SELECT no, estado FROM participantes WHERE transferencia_id = '{tid}'")}
    return {"estado": e, "decisao": d or None, "codigo_erro": c or None, "parceiro": p, "participantes": parts}


def eventos_2pc(tid: str) -> list[str]:
    return [f"{em[11:23]}  {ev:<24} {det}" for ev, det, em in coord_sql(
        f"SELECT evento, coalesce(detalhe,''), to_char(em, 'YYYY-MM-DD HH24:MI:SS.MS') FROM eventos "
        f"WHERE transferencia_id = '{tid}' ORDER BY id")]


def logs_2pc(tid: str) -> list[str]:
    linhas = []
    for no, (s, _) in NOS.items():
        for l in compose("logs", "--no-color", s, timeout=60).splitlines():
            if tid in l and ("PREPARE" in l or "PREPARED" in l):
                linhas.append(l.split("LOG:", 1)[-1].strip() if "LOG:" in l else l)
    return linhas


def esperar(condicao, timeout=60, intervalo=1.0, descricao="condicao"):
    fim = time.time() + timeout
    while time.time() < fim:
        try:
            v = condicao()
            if v:
                return v
        except Exception:
            pass
        time.sleep(intervalo)
    raise TimeoutError(f"tempo esgotado a esperar: {descricao}")


def esperar_saudavel(servico: str, timeout=120):
    def ok():
        return '"Health":"healthy"' in compose("ps", "--format", "json", servico).replace(" ", "")
    esperar(ok, timeout, 2, f"{servico} saudavel")


def pausa(ponto: str, segundos: float):
    r = httpx.post(f"{COORD}/laboratorio/pausa", json={"ponto": ponto, "segundos": segundos},
                   headers={"X-Chave-Laboratorio": ENV["CHAVE_LABORATORIO"]}, verify=CA)
    r.raise_for_status()


def cliente(utilizador: str, apis=None) -> Cliente:
    c = Cliente(apis=apis or [API1, API2], mostrar=False)
    c.login(utilizador, SENHAS[utilizador])
    return c


def eur(c: int) -> str:
    return f"{c / 100:,.2f}".replace(",", " ")


# ================================================================ registo das evidencias
class Evidencia:
    def __init__(self, numero: int, nome: str, titulo: str, objectivo: str, dois_pcs: str = ""):
        self.numero, self.nome, self.titulo, self.objectivo, self.dois_pcs = numero, nome, titulo, objectivo, dois_pcs
        self.passos: list[str] = []
        self.verificacoes: list[tuple[str, bool]] = []
        self.blocos: list[tuple[str, str]] = []
        self.dados: dict = {}
        self.inicio = time.time()

    def passo(self, texto: str):
        t = time.strftime("%H:%M:%S")
        self.passos.append(f"`{t}` {texto}")
        print(f"   {t} {texto}")

    def bloco(self, titulo: str, conteudo):
        if not isinstance(conteudo, str):
            conteudo = json.dumps(conteudo, indent=2, ensure_ascii=False, default=str)
        self.blocos.append((titulo, conteudo))

    def verificar(self, descricao: str, condicao: bool) -> bool:
        self.verificacoes.append((descricao, bool(condicao)))
        print(f"   {'OK ' if condicao else 'FALHOU'} {descricao}")
        return bool(condicao)

    def saldos(self, rotulo: str, valores: dict, contas: list[str]):
        self.dados.setdefault("saldos", {})[rotulo] = {c: valores[c] for c in contas}

    @property
    def passou(self) -> bool:
        return bool(self.verificacoes) and all(ok for _, ok in self.verificacoes)

    def gravar(self):
        EVID.mkdir(exist_ok=True)
        base = EVID / f"{self.numero:02d}_{self.nome}"
        md = [f"# Cenario {self.numero}: {self.titulo}", "",
              f"**Resultado: {'PASSOU' if self.passou else 'FALHOU'}** "
              f"({len([1 for _, o in self.verificacoes if o])}/{len(self.verificacoes)} verificacoes, "
              f"{time.time() - self.inicio:.1f} s, executado em {time.strftime('%Y-%m-%d %H:%M:%S')})", "",
              f"**Objectivo:** {self.objectivo}", ""]
        if self.dois_pcs:
            md += [f"**Dois computadores:** {self.dois_pcs}", ""]
        md += ["## Procedimento executado", ""] + [f"{i}. {p}" for i, p in enumerate(self.passos, 1)] + [""]
        if "saldos" in self.dados:
            rotulos = list(self.dados["saldos"])
            contas = list(self.dados["saldos"][rotulos[0]])
            md += ["## Saldos (lidos directamente nos nos PostgreSQL)", "",
                   "| Conta | " + " | ".join(rotulos) + " |", "|---|" + "---:|" * len(rotulos)]
            for c in contas:
                md.append(f"| {c} | " + " | ".join(eur(self.dados['saldos'][r][c]) for r in rotulos) + " |")
            md.append("")
        for titulo, conteudo in self.blocos:
            md += [f"## {titulo}", "", "```", conteudo, "```", ""]
        md += ["## Verificacoes", ""] + [f"- {'[x]' if ok else '[ ] FALHOU:'} {d}" for d, ok in self.verificacoes]
        base.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
        base.with_suffix(".json").write_text(json.dumps(
            {"cenario": self.numero, "titulo": self.titulo, "passou": self.passou, "passos": self.passos,
             "verificacoes": self.verificacoes, "dados": self.dados, "blocos": dict(self.blocos)},
            indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def em_fundo(funcao, *args):
    """Corre funcao(*args) numa thread e devolve um objecto com .resultado depois de .join()."""
    caixa = {}

    def alvo():
        try:
            caixa["r"] = funcao(*args)
        except Exception as e:
            caixa["r"] = e
    t = threading.Thread(target=alvo)
    t.start()
    t.caixa = caixa
    return t


def resposta(r) -> dict:
    if isinstance(r, Exception):
        return {"excepcao": repr(r)}
    try:
        corpo = r.json()
    except ValueError:
        corpo = r.text
    return {"http": r.status_code, "instancia": r.headers.get("X-Instancia"), "corpo": corpo}


# ================================================================ cenarios
def c00_ambiente():
    ev = Evidencia(0, "ambiente_rede_tls", "Ambiente, rede, DNS e TLS",
                   "Mostrar os nos, as redes, os IP, as portas e provar que as ligacoes a BD usam TLS verificado.")
    ev.passo("docker compose ps")
    ev.bloco("Contentores (docker compose ps)", compose("ps", "--format",
                                                       "table {{.Name}}\t{{.Status}}\t{{.Ports}}"))
    redes = []
    for rede in ("global-scale_frontal", "global-scale_interna"):
        info = json.loads(subprocess.run(["docker", "network", "inspect", rede], capture_output=True,
                                         text=True).stdout)[0]
        redes.append(f"{rede}  {info['IPAM']['Config'][0]['Subnet']}")
        for c in sorted(info["Containers"].values(), key=lambda c: c["IPv4Address"]):
            redes.append(f"   {c['IPv4Address']:<18} {c['Name']}")
    ev.bloco("Redes e enderecos IP (docker network inspect)", "\n".join(redes))
    ev.passo("Resolucao DNS a partir do contentor api-1")
    dns = compose("exec", "-T", "api-1", "python", "-c",
                  "import socket\nfor n in ['db-europa','db-america','db-coordenador','coordenador','auth',"
                  "'banco-parceiro','nfs']: print(f'{n:<16}', socket.gethostbyname(n))")
    ev.bloco("DNS interno (getaddrinfo dentro de api-1)", dns)
    ev.verificar("api-1 resolve todos os nomes dos servicos", dns.count("172.30.") == 7)

    ev.passo("Parametros do PostgreSQL relevantes para o 2PC e TLS")
    par = []
    for s, p in (("db-europa", 5433), ("db-america", 5434), ("db-coordenador", 5435)):
        v = psql(s, p, "SELECT current_setting('max_prepared_transactions'), current_setting('ssl'), "
                       "current_setting('port'), version()")
        par.append(f"{s:<15} max_prepared_transactions={v[0][0]}  ssl={v[0][1]}  porta={v[0][2]}  {v[0][3][:16]}")
    ev.bloco("Configuracao dos nos PostgreSQL", "\n".join(par))
    ev.verificar("max_prepared_transactions > 0 e ssl=on nos tres nos", all("ssl=on" in l and "=0 " not in l for l in par))

    # Os servicos abrem uma ligacao por operacao (pool nulo), por isso abre-se uma ligacao de 6 s a
    # partir de cada servico, com o DSN do proprio servico (comum/bd.py), e observa-se do lado do servidor.
    ev.passo("Cada servico abre uma ligacao ao db-europa com o seu DSN (TLS verify-full); o servidor mostra-as")
    for servico, papel, senha in (("auth", "gs_leitura", "PG_SENHA_LEITURA"), ("api-1", "gs_leitura", "PG_SENHA_LEITURA"),
                                  ("api-2", "gs_leitura", "PG_SENHA_LEITURA"),
                                  ("coordenador", "gs_transaccoes", "PG_SENHA_TRANSACCOES")):
        compose("exec", "-d", servico, "python", "-c",
                f"import os, psycopg; from comum import bd; "
                f"c = psycopg.connect(bd.dsn_no('europa', '{papel}', os.environ['{senha}'])); "
                f"c.execute('SELECT pg_sleep(6)')")
    time.sleep(2.5)
    tls = psql("db-europa", 5433, "SELECT a.application_name, a.usename, host(a.client_addr), s.ssl, s.version, s.cipher "
                                   "FROM pg_stat_ssl s JOIN pg_stat_activity a USING (pid) "
                                   "WHERE a.client_addr IS NOT NULL ORDER BY 1")
    ev.bloco("Ligacoes ao db-europa vistas pelo servidor (pg_stat_ssl): servico | papel | IP | ssl | versao | cifra",
             "\n".join(" | ".join(l) for l in tls))
    ev.verificar("as ligacoes de auth, api-1, api-2 e coordenador usam TLS 1.3",
                 {l[0] for l in tls} >= {"auth", "api-1", "api-2", "coordenador"}
                 and all(l[3] == "t" and l[4] == "TLSv1.3" for l in tls))

    ev.passo("Tentar ligar ao db-europa sem TLS e com o nome errado no certificado")
    teste = compose("exec", "-T", "api-1", "python", "-c", """
import psycopg, os
s = os.environ['PG_SENHA_LEITURA']
for nome, dsn in [('sem TLS', f'host=db-europa port=5433 dbname=globalscale user=gs_leitura password={s} sslmode=disable'),
                  ('IP em vez do nome', f'host=172.30.2.10 port=5433 dbname=globalscale user=gs_leitura password={s} sslmode=verify-full sslrootcert=/run/secrets/ca.crt'),
                  ('correcto', f'host=db-europa port=5433 dbname=globalscale user=gs_leitura password={s} sslmode=verify-full sslrootcert=/run/secrets/ca.crt')]:
    try:
        c = psycopg.connect(dsn, connect_timeout=3)
        print(nome, '-> ligou, TLS', c.execute('SELECT version FROM pg_stat_ssl WHERE pid = pg_backend_pid()').fetchone()[0]); c.close()
    except Exception as e: print(nome, '-> RECUSADO:', str(e).strip().splitlines()[-1][:150])
""")
    ev.bloco("Ligacoes de teste a partir de api-1", teste)
    ev.verificar("sem TLS: recusado pelo pg_hba.conf", "sem TLS -> RECUSADO" in teste)
    ev.verificar("certificado sem esse nome: recusado (verify-full)", "IP em vez do nome -> RECUSADO" in teste)
    ev.verificar("ligacao correcta usa TLSv1.3", "correcto -> ligou, TLS TLSv1.3" in teste)

    ev.passo("HTTPS: pedido sem a CA do laboratorio e pedido com a CA")
    try:
        httpx.get(f"{API1}/saude", verify=True)
        sem_ca = "aceite (inesperado)"
    except httpx.ConnectError as e:
        sem_ca = f"recusado: {str(e)[:120]}"
    com_ca = httpx.get(f"{API1}/saude", verify=CA)
    ev.bloco("HTTPS na API", f"sem a CA do laboratorio: {sem_ca}\ncom a CA: HTTP {com_ca.status_code} {com_ca.json()}")
    ev.verificar("o certificado da API so e aceite com a CA do laboratorio", sem_ca.startswith("recusado"))
    try:
        httpx.get("http://localhost:8001/saude", timeout=3)
        http_simples = "aceite (inesperado)"
    except httpx.HTTPError as e:
        http_simples = f"recusado ({type(e).__name__})"
    ev.verificar(f"HTTP sem TLS na porta 8001 e recusado: {http_simples}", http_simples.startswith("recusado"))
    return ev


def c01_sucesso():
    ev = Evidencia(1, "transferencia_sucesso", "Transferencia bem-sucedida entre Europa e America",
                   "Transferir 125.50 EUR de EU-1001 (no Europa) para US-2001 (no America) com 2PC.",
                   "Localmente os dois nos sao contentores no mesmo PC. Com distribuido/ o no Europa corre no PC A "
                   "e o no America no PC B; o procedimento e o mesmo.")
    contas = ["EU-1001", "US-2001"]
    antes = saldos()
    ev.saldos("antes", antes, contas)
    c = cliente("ana", [API1])
    ev.passo("ana autentica-se em https://localhost:8000 e envia POST /api/v1/transferencias a api-1")
    r = c.transferir("EU-1001", "US-2001", "125.50", chave=f"c01-{uuid.uuid4()}")
    corpo = r.json()
    tid = corpo["id"]
    CONTEXTO["tid_c01"] = tid
    ev.bloco("Resposta da API (HTTP %d)" % r.status_code, corpo)
    depois = saldos()
    ev.saldos("depois", depois, contas)
    ev.verificar("HTTP 201 e estado CONCLUIDA", r.status_code == 201 and corpo["estado"] == "CONCLUIDA")
    ev.verificar("EU-1001 debitada em 125.50", antes["EU-1001"] - depois["EU-1001"] == 12550)
    ev.verificar("US-2001 creditada em 125.50", depois["US-2001"] - antes["US-2001"] == 12550)
    ev.verificar("total das duas contas conservado", sum(antes[x] for x in contas) == sum(depois[x] for x in contas))
    m = movimentos(tid)
    ev.bloco("Movimentos desta transferencia nos dois nos", "\n".join(map(str, m)))
    ev.verificar("exactamente um DEBITO (europa) e um CREDITO (america)",
                 sorted(m) == [("america", "CREDITO", "US-2001", 12550), ("europa", "DEBITO", "EU-1001", 12550)])
    ev.bloco("Diario do coordenador (tabela eventos)", "\n".join(eventos_2pc(tid)))
    ev.bloco("Comandos 2PC nos logs dos participantes PostgreSQL", "\n".join(logs_2pc(tid)))
    ev.verificar("os dois participantes executaram PREPARE TRANSACTION e COMMIT PREPARED",
                 sum("PREPARE TRANSACTION" in l for l in logs_2pc(tid)) == 2
                 and sum("COMMIT PREPARED" in l for l in logs_2pc(tid)) == 2)
    ev.passo("Consultar o estado (GET /api/v1/transferencias/{id}) ate o banco parceiro confirmar")
    final = esperar(lambda: (x := c.pedido("GET", f"/api/v1/transferencias/{tid}").json())["parceiro"]["estado"]
                    == "CONFIRMADA" and x, 30, 1, "confirmacao do parceiro")
    ev.bloco("Estado final da transferencia", final)
    ev.verificar("confirmada pelo banco parceiro (Java) com referencia BP-xxxxxx",
                 (final["parceiro"]["referencia"] or "").startswith("BP-"))
    ev.verificar("nenhuma transaccao preparada ficou por resolver", preparadas() == {"europa": [], "america": []})
    return ev


def c02_saldo_insuficiente():
    ev = Evidencia(2, "saldo_insuficiente", "Saldo insuficiente e outras validacoes",
                   "bruno (EU-1003, 300.00) tenta transferir 1000.00: o no Europa vota NAO e a decisao e ABORT.")
    contas = ["EU-1003", "US-2002"]
    antes = saldos()
    ev.saldos("antes", antes, contas)
    c = cliente("bruno")
    ev.passo("bruno envia 1000.00 de EU-1003 para US-2002")
    r = c.transferir("EU-1003", "US-2002", "1000.00")
    corpo = r.json()
    ev.bloco("Resposta (HTTP %d)" % r.status_code, corpo)
    ev.saldos("depois", saldos(), contas)
    ev.verificar("HTTP 422, estado ABORTADA, codigo SALDO_INSUFICIENTE",
                 r.status_code == 422 and corpo["estado"] == "ABORTADA" and corpo["codigo_erro"] == "SALDO_INSUFICIENTE")
    ev.verificar("saldos inalterados", saldos() == antes)
    ev.verificar("nenhum movimento registado", movimentos(corpo["id"]) == [])
    ev.bloco("Diario do coordenador", "\n".join(eventos_2pc(corpo["id"])))
    ev.passo("Outras validacoes: conta inexistente, montante negativo, 3 casas decimais, mesma conta")
    casos = {"conta destino inexistente (US-9999)": c.transferir("EU-1003", "US-9999", "1.00"),
             "montante negativo (-5)": c.transferir("EU-1003", "US-2002", "-5"),
             "tres casas decimais (1.005)": c.transferir("EU-1003", "US-2002", "1.005"),
             "origem igual ao destino": c.transferir("EU-1003", "EU-1003", "1.00"),
             "moeda diferente (USD)": c.pedido("POST", "/api/v1/transferencias", headers={"Idempotency-Key": f"c02-{uuid.uuid4()}"},
                                               json={"conta_origem": "EU-1003", "conta_destino": "US-2002",
                                                     "montante": "1.00", "moeda": "USD"})}
    texto = []
    for nome, rr in casos.items():
        j = rr.json()
        texto.append(f"{nome:<38} HTTP {rr.status_code}  {j.get('codigo_erro') or j.get('detail')}")
        ev.verificar(f"{nome}: recusado com HTTP 422", rr.status_code == 422)
    ev.bloco("Validacoes", "\n".join(texto))
    ev.verificar("saldos continuam inalterados", saldos() == antes)
    return ev


def c03_concorrencia():
    ev = Evidencia(3, "concorrencia", "Transferencias concorrentes sobre a mesma conta",
                   "10 transferencias simultaneas de 50.00 a partir de EU-1003, metade por api-1 e metade por api-2. "
                   "Com o saldo disponivel so algumas podem passar; o saldo nunca pode ficar negativo.")
    contas = ["EU-1003", "US-2001"]
    antes = saldos()
    ev.saldos("antes", antes, contas)
    esperadas = min(10, antes["EU-1003"] // 5000)
    clientes = [cliente("bruno", [API1]), cliente("bruno", [API2])]
    barreira = threading.Barrier(10)

    def uma(i):
        barreira.wait()                      # todas partem ao mesmo tempo
        t0 = time.time()
        r = clientes[i % 2].transferir("EU-1003", "US-2001", "50.00", chave=f"c03-{i}-{uuid.uuid4()}")
        return i, r.status_code, r.json().get("estado"), r.json().get("codigo_erro"), r.headers.get("X-Instancia"), \
            round(time.time() - t0, 3), r.json().get("id")
    ev.passo(f"Lancar 10 pedidos em paralelo (saldo inicial {eur(antes['EU-1003'])}; cabem {esperadas})")
    with cf.ThreadPoolExecutor(10) as ex:
        res = sorted(ex.map(uma, range(10)))
    depois = saldos()
    ev.saldos("depois", depois, contas)
    ev.bloco("Resultado de cada pedido (i, HTTP, estado, codigo, instancia, segundos)",
             "\n".join(str(r[:6]) for r in res))
    ok = [r for r in res if r[2] == "CONCLUIDA"]
    ev.verificar(f"exactamente {esperadas} concluidas", len(ok) == esperadas)
    ev.verificar("as restantes abortadas por SALDO_INSUFICIENTE (ou conflito de bloqueio)",
                 all(r[3] in ("SALDO_INSUFICIENTE", "CONFLITO_BLOQUEIO") for r in res if r[2] != "CONCLUIDA"))
    ev.verificar("os pedidos foram atendidos pelas duas instancias", {r[4] for r in res} == {"api-1", "api-2"})
    ev.verificar("saldo final = inicial - 50.00 x concluidas",
                 depois["EU-1003"] == antes["EU-1003"] - 5000 * len(ok))
    ev.verificar("saldo nunca negativo", depois["EU-1003"] >= 0)
    ev.verificar("dinheiro conservado entre as duas contas",
                 sum(antes[x] for x in contas) == sum(depois[x] for x in contas))
    debitos = psql("db-europa", 5433, "SELECT count(*) FROM movimentos WHERE conta_id = 'EU-1003' AND tipo = 'DEBITO'")
    ev.verificar("numero de debitos de EU-1003 igual ao numero de concluidas (sem duplicados)",
                 int(debitos[0][0]) == len(ok) + CONTEXTO.get("debitos_eu1003_antes", 0))
    return ev


def c04_idempotencia():
    ev = Evidencia(4, "idempotencia", "Repeticao de um pedido com a mesma chave de idempotencia",
                   "O mesmo pedido enviado a api-1 e repetido em api-2 com a mesma Idempotency-Key produz uma so "
                   "transferencia; a mesma chave com outro montante e recusada.")
    contas = ["EU-1002", "US-2002"]
    antes = saldos()
    ev.saldos("antes", antes, contas)
    chave = f"c04-{uuid.uuid4()}"
    ev.passo(f"POST a api-1 com Idempotency-Key {chave}")
    r1 = cliente("ana", [API1]).transferir("EU-1002", "US-2002", "10.00", chave)
    ev.passo("Repetir o mesmo pedido em api-2 (como faria um cliente depois de um timeout)")
    r2 = cliente("ana", [API2]).transferir("EU-1002", "US-2002", "10.00", chave)
    ev.passo("Reutilizar a chave com outro montante (20.00)")
    r3 = cliente("ana", [API1]).transferir("EU-1002", "US-2002", "20.00", chave)
    depois = saldos()
    ev.saldos("depois", depois, contas)
    ev.bloco("Respostas", {"primeiro (api-1)": resposta(r1), "repeticao (api-2)": resposta(r2),
                           "chave reutilizada com 20.00": resposta(r3)})
    ev.verificar("primeiro pedido: HTTP 201 CONCLUIDA", r1.status_code == 201 and r1.json()["estado"] == "CONCLUIDA")
    ev.verificar("repeticao: HTTP 200, mesmo id, repetido=true",
                 r2.status_code == 200 and r2.json()["id"] == r1.json()["id"] and r2.json()["repetido"] is True)
    ev.verificar("chave reutilizada com dados diferentes: HTTP 409", r3.status_code == 409)
    ev.verificar("saldos alterados uma unica vez (10.00)",
                 antes["EU-1002"] - depois["EU-1002"] == 1000 and depois["US-2002"] - antes["US-2002"] == 1000)
    ev.verificar("so um debito e um credito", len(movimentos(r1.json()["id"])) == 2)

    chave2 = f"c04-paralelo-{uuid.uuid4()}"
    ev.passo(f"5 pedidos SIMULTANEOS com a mesma chave {chave2} (api-1 e api-2 alternadas)")
    cs = [cliente("ana", [API1]), cliente("ana", [API2])]
    barreira = threading.Barrier(5)

    def um(i):
        barreira.wait()
        r = cs[i % 2].transferir("EU-1002", "US-2002", "1.00", chave2)
        return r.status_code, r.json().get("id"), r.json().get("estado")
    with cf.ThreadPoolExecutor(5) as ex:
        res = list(ex.map(um, range(5)))
    ev.bloco("Pedidos simultaneos com a mesma chave (HTTP, id, estado)", "\n".join(map(str, res)))
    ids = {r[1] for r in res}
    n = coord_sql(f"SELECT count(*) FROM transferencias WHERE chave_idempotencia = '{chave2}'")[0][0]
    ev.verificar("todos os pedidos devolvem a mesma transferencia", len(ids) == 1)
    ev.verificar("o coordenador tem uma unica transferencia com esta chave", n == "1")
    tid2 = ids.pop()
    esperar(lambda: estado_bd(tid2)["estado"] == "CONCLUIDA", 20, 0.5, "conclusao")
    ev.verificar("um debito e um credito para a transferencia paralela", len(movimentos(tid2)) == 2)
    return ev


def c05_falha_preparacao():
    ev = Evidencia(5, "falha_na_preparacao", "Falha de um participante antes e durante a preparacao",
                   "(a) O no Europa esta em baixo quando chega uma transferencia US-2001 -> EU-1001: o primeiro "
                   "participante falha, nenhum prepara e a decisao e ABORT. (b) O no America cai depois de o Europa "
                   "ja ter preparado (PREPARE TRANSACTION): o Europa faz ROLLBACK PREPARED. Nenhum saldo muda.",
                   "Com dois PCs pode desligar-se o cabo/Wi-Fi do PC B em vez de parar o contentor.")
    contas = ["EU-1001", "US-2001"]
    antes = saldos()
    ev.saldos("antes", antes, contas)

    # (a) falha antes da preparacao
    carlos = cliente("carlos", [API1])
    ev.passo("(a) docker compose stop db-europa; carlos envia 12.00 de US-2001 para EU-1001")
    compose("stop", "db-europa")
    ra = carlos.transferir("US-2001", "EU-1001", "12.00", f"c05a-{uuid.uuid4()}")
    corpo_a = ra.json()
    ev.bloco("(a) Resposta com o no Europa em baixo antes da preparacao", resposta(ra))
    ev.verificar("(a) HTTP 503, ABORTADA, NO_INDISPONIVEL",
                 ra.status_code == 503 and corpo_a["estado"] == "ABORTADA" and corpo_a["codigo_erro"] == "NO_INDISPONIVEL")
    parts = {p["no"]: p["estado"] for p in corpo_a["participantes"]}
    ev.verificar(f"(a) nenhum participante preparou (europa {parts.get('europa')}, america {parts.get('america')})",
                 parts.get("europa") == "NAO_PREPARADO" and parts.get("america") == "POR_PREPARAR")
    ev.verificar("(a) America sem transaccao preparada e US-2001 sem alteracao",
                 psql("db-america", 5434, "SELECT count(*) FROM pg_prepared_xacts")[0][0] == "0" and
                 int(psql("db-america", 5434, "SELECT saldo_centimos FROM contas WHERE id='US-2001'")[0][0]) == antes["US-2001"])
    ev.passo("(a) docker compose start db-europa")
    compose("start", "db-europa")
    esperar_saudavel("db-europa")

    # (b) falha durante a preparacao
    c = cliente("ana", [API1])
    ev.passo("(b) Pausa de laboratorio de 8 s antes de preparar no America")
    pausa("antes_preparar_america", 8)
    ev.passo("(b) ana envia 15.00 de EU-1001 para US-2001 (em segundo plano)")
    t = em_fundo(c.transferir, "EU-1001", "US-2001", "15.00", f"c05-{uuid.uuid4()}")
    prep = esperar(lambda: (p := preparadas())["europa"] and p, 10, 0.3, "preparacao no Europa")
    ev.bloco("(b) pg_prepared_xacts durante a pausa", prep)
    ev.verificar("(b) o Europa ja tem a transaccao preparada", len(prep["europa"]) == 1 and prep["america"] == [])
    ev.passo("(b) docker compose stop db-america (queda do no America)")
    compose("stop", "db-america")
    t.join(60)
    r = t.caixa["r"]
    corpo = r.json()
    ev.bloco("(b) Resposta da API (HTTP %d)" % r.status_code, corpo)
    ev.verificar("(b) HTTP 503 e estado ABORTADA com codigo NO_INDISPONIVEL",
                 r.status_code == 503 and corpo["estado"] == "ABORTADA" and corpo["codigo_erro"] == "NO_INDISPONIVEL")
    ev.verificar("(b) Europa: transaccao preparada desfeita (ROLLBACK PREPARED)",
                 psql("db-europa", 5433, "SELECT count(*) FROM pg_prepared_xacts")[0][0] == "0")
    ev.verificar("(b) EU-1001 sem alteracao com o America em baixo",
                 int(psql("db-europa", 5433, "SELECT saldo_centimos FROM contas WHERE id='EU-1001'")[0][0]) == antes["EU-1001"])
    ev.bloco("(b) Diario do coordenador", "\n".join(eventos_2pc(corpo["id"])))
    ev.passo("(b) docker compose start db-america")
    compose("start", "db-america")
    esperar_saudavel("db-america")
    depois = saldos()
    ev.saldos("depois", depois, contas)
    ev.verificar("saldos inalterados nos dois nos", all(depois[x] == antes[x] for x in contas))
    ev.verificar("nenhum movimento e nenhuma transaccao preparada",
                 movimentos(corpo["id"]) == [] and movimentos(corpo_a["id"]) == []
                 and preparadas() == {"europa": [], "america": []})
    return ev


def c06_falha_confirmacao():
    ev = Evidencia(6, "falha_na_confirmacao", "Falha durante a confirmacao e posterior recuperacao",
                   "(a) A decisao COMMIT ja esta gravada e o Europa ja confirmou quando o America cai. A transferencia "
                   "fica COMMIT_DECIDIDO (pendente no America). A transaccao preparada sobrevive ao reinicio do "
                   "PostgreSQL e a recuperacao conclui o COMMIT. (b) Falha de rede: o America fica sem responder "
                   "(processos congelados com docker compose pause, como numa particao); o COMMIT esgota o tempo, "
                   "a decisao nao muda e a transferencia conclui quando a rede volta.",
                   "Com dois PCs pode desligar-se a rede do PC B durante a pausa.")
    contas = ["EU-1001", "US-2001"]
    antes = saldos()
    ev.saldos("antes", antes, contas)
    c = cliente("ana", [API1])
    chave = f"c06-{uuid.uuid4()}"
    ev.passo("(a) Pausa de laboratorio de 10 s antes do COMMIT PREPARED no America")
    pausa("antes_commit_america", 10)
    ev.passo("(a) ana envia 20.00 de EU-1001 para US-2001 (em segundo plano)")
    t = em_fundo(c.transferir, "EU-1001", "US-2001", "20.00", chave)
    tid = esperar(lambda: coord_sql(f"SELECT id FROM transferencias WHERE chave_idempotencia = '{chave}' "
                                    f"AND estado = 'COMMIT_DECIDIDO'")[0][0], 15, 0.3, "decisao COMMIT")
    time.sleep(1)
    ev.bloco("Estado no coordenador durante a pausa", estado_bd(tid))
    # A proxima tentativa de COMMIT no America sera a do ciclo de recuperacao: pausa-a 25 s para se
    # poder observar o no America depois de reiniciar, ainda com a transaccao preparada.
    pausa("antes_commit_america", 25)
    ev.passo("docker compose stop db-america (o America tem a transaccao preparada)")
    compose("stop", "db-america")
    t.join(60)
    r = t.caixa["r"]
    corpo = r.json()
    ev.bloco("Resposta da API (HTTP %d)" % r.status_code, corpo)
    ev.verificar("HTTP 202, estado COMMIT_DECIDIDO, pendente no america",
                 r.status_code == 202 and corpo["estado"] == "COMMIT_DECIDIDO" and corpo["pendente_em"] == ["america"])
    meio = int(psql("db-europa", 5433, "SELECT saldo_centimos FROM contas WHERE id='EU-1001'")[0][0])
    ev.verificar("Europa ja debitou (a decisao COMMIT e definitiva)", antes["EU-1001"] - meio == 2000)
    ev.passo("docker compose start db-america (a recuperacao tem uma pausa de 25 s para se observar o no)")
    compose("start", "db-america")
    esperar_saudavel("db-america")
    prep = preparadas()
    ev.bloco("pg_prepared_xacts no America logo apos o reinicio", prep)
    ev.verificar("a transaccao preparada sobreviveu ao reinicio do PostgreSQL",
                 prep["america"] == [f"gs-{tid}-america"])
    ev.passo("Esperar que o ciclo de recuperacao do coordenador repita o COMMIT PREPARED")
    esperar(lambda: estado_bd(tid)["estado"] == "CONCLUIDA", 60, 1, "CONCLUIDA")
    depois = saldos()
    ev.saldos("depois", depois, contas)
    ev.bloco("Diario do coordenador", "\n".join(eventos_2pc(tid)))
    ev.verificar("(a) estado final CONCLUIDA", estado_bd(tid)["estado"] == "CONCLUIDA")
    ev.verificar("(a) US-2001 creditada em 20.00", depois["US-2001"] - antes["US-2001"] == 2000)
    ev.verificar("(a) total conservado", sum(antes[x] for x in contas) == sum(depois[x] for x in contas))
    ev.verificar("(a) um debito e um credito", len(movimentos(tid)) == 2)

    # (b) falha de rede: o no continua vivo mas nao responde
    chave_b = f"c06b-{uuid.uuid4()}"
    ev.passo("(b) Pausa de 6 s antes do COMMIT no America; ana envia 8.00 de EU-1001 para US-2001")
    pausa("antes_commit_america", 6)
    t = em_fundo(c.transferir, "EU-1001", "US-2001", "8.00", chave_b)
    tid_b = esperar(lambda: coord_sql(f"SELECT id FROM transferencias WHERE chave_idempotencia = '{chave_b}' "
                                      f"AND estado = 'COMMIT_DECIDIDO'")[0][0], 15, 0.3, "decisao COMMIT (b)")
    ev.passo("(b) docker compose pause db-america (o no deixa de responder, sem perder ligacao de rede nem dados)")
    compose("pause", "db-america")
    t.join(60)
    rb = t.caixa["r"]
    ev.bloco("(b) Resposta da API com o America sem responder", resposta(rb))
    ev.verificar("(b) HTTP 202 COMMIT_DECIDIDO, pendente no america (o timeout nao mudou a decisao)",
                 rb.status_code == 202 and rb.json()["estado"] == "COMMIT_DECIDIDO" and rb.json()["pendente_em"] == ["america"])
    time.sleep(8)                                   # a recuperacao tenta e volta a esgotar o tempo
    ev.verificar("(b) durante a falha de rede a transferencia continua COMMIT_DECIDIDO",
                 estado_bd(tid_b)["estado"] == "COMMIT_DECIDIDO")
    ev.passo("(b) docker compose unpause db-america (a rede volta)")
    compose("unpause", "db-america")
    esperar(lambda: estado_bd(tid_b)["estado"] == "CONCLUIDA", 60, 1, "CONCLUIDA (b)")
    ev.bloco("(b) Diario do coordenador", "\n".join(eventos_2pc(tid_b)))
    ev.verificar("(b) o diario regista o COMMIT sem resposta (timeout) e a repeticao bem-sucedida",
                 any("DECISAO_PENDENTE" in l for l in eventos_2pc(tid_b)) and estado_bd(tid_b)["estado"] == "CONCLUIDA")
    final = saldos()
    ev.saldos("final", final, contas)
    ev.verificar("(b) um debito e um credito e total conservado",
                 len(movimentos(tid_b)) == 2 and sum(antes[x] for x in contas) == sum(final[x] for x in contas))
    ev.verificar("nenhuma transaccao preparada ficou por resolver", preparadas() == {"europa": [], "america": []})
    return ev


def c07_reinicio_coordenador():
    ev = Evidencia(7, "reinicio_coordenador", "Reinicio do coordenador com transaccoes pendentes",
                   "(a) O coordenador cai depois de gravar COMMIT: ao reiniciar conclui o COMMIT nos dois nos. "
                   "(b) O coordenador cai depois de preparar mas antes de decidir: ao reiniciar faz ABORT presumido.")
    contas = ["EU-1001", "EU-1002", "US-2001", "US-2002"]
    antes = saldos()
    ev.saldos("antes", antes, contas)
    c = cliente("ana", [API1])

    # (a) decisao COMMIT gravada
    chave_a = f"c07a-{uuid.uuid4()}"
    ev.passo("(a) Pausa de 20 s depois de gravar a decisao; ana envia 30.00 EU-1002 -> US-2002")
    pausa("apos_decisao", 20)
    t = em_fundo(c.transferir, "EU-1002", "US-2002", "30.00", chave_a)
    tid_a = esperar(lambda: coord_sql(f"SELECT id FROM transferencias WHERE chave_idempotencia = '{chave_a}' "
                                      f"AND decisao = 'COMMIT'")[0][0], 15, 0.3, "decisao")
    ev.passo("docker compose kill coordenador (queda abrupta, sem terminar o pedido)")
    compose("kill", "coordenador")
    t.join(60)
    ev.bloco("(a) Resposta da API ao cliente com o coordenador morto", resposta(t.caixa["r"]))
    ev.verificar("(a) a API responde 504/503: resultado DESCONHECIDO (timeout nao e decisao)",
                 not isinstance(t.caixa["r"], Exception) and t.caixa["r"].status_code in (503, 504))
    prep = preparadas()
    ev.bloco("(a) Estado com o coordenador em baixo", {"registo do coordenador": estado_bd(tid_a), "pg_prepared_xacts": prep})
    ev.verificar("(a) decisao COMMIT gravada e os dois nos com a transaccao preparada",
                 estado_bd(tid_a)["decisao"] == "COMMIT" and len(prep["europa"]) == 1 and len(prep["america"]) == 1)
    ev.passo("(a) Bloqueio do 2PC: tentar alterar EU-1002 directamente no Europa com lock_timeout de 2 s")
    try:
        psql("db-europa", 5433, "SET lock_timeout = '2s'; UPDATE contas SET saldo_centimos = saldo_centimos WHERE id = 'EU-1002'")
        bloqueio = "nao bloqueou"
    except RuntimeError as e:
        bloqueio = str(e)
    ev.bloco("(a) Linha bloqueada pela transaccao preparada", bloqueio)
    ev.verificar("(a) a conta fica bloqueada enquanto o coordenador nao volta", "lock timeout" in bloqueio)

    # (b) sem decisao: tem de ser testado com o coordenador vivo; primeiro reiniciar e recuperar (a)
    ev.passo("(a) docker compose start coordenador -> recuperacao de arranque")
    compose("start", "coordenador")
    esperar(lambda: estado_bd(tid_a)["estado"] == "CONCLUIDA", 90, 1, "recuperacao (a)")
    ev.bloco("(a) Diario do coordenador", "\n".join(eventos_2pc(tid_a)))
    ev.verificar("(a) concluida apos o reinicio: um debito e um credito", len(movimentos(tid_a)) == 2)
    esperar_saudavel("coordenador")
    ev.passo("(a) o cliente pergunta o resultado pela chave: GET /api/v1/transferencias?chave=...")
    consulta = c.pedido("GET", f"/api/v1/transferencias?chave={chave_a}").json()["transferencias"][0]
    ev.verificar("(a) o cliente descobre que a transferencia foi CONCLUIDA", consulta["estado"] == "CONCLUIDA")

    chave_b = f"c07b-{uuid.uuid4()}"
    ev.passo("(b) Pausa de 20 s depois de preparar (antes da decisao); ana envia 40.00 EU-1001 -> US-2001")
    pausa("apos_preparar", 20)
    t = em_fundo(c.transferir, "EU-1001", "US-2001", "40.00", chave_b)
    tid_b = esperar(lambda: coord_sql(f"SELECT id FROM transferencias WHERE chave_idempotencia = '{chave_b}' "
                                      f"AND estado = 'PREPARADA'")[0][0], 15, 0.3, "preparada")
    ev.passo("docker compose kill coordenador")
    compose("kill", "coordenador")
    t.join(60)
    ev.bloco("(b) Estado com o coordenador em baixo", {"registo do coordenador": estado_bd(tid_b),
                                                       "pg_prepared_xacts": preparadas()})
    ev.passo("docker compose start coordenador -> abort presumido")
    compose("start", "coordenador")
    esperar(lambda: estado_bd(tid_b)["estado"] == "ABORTADA", 90, 1, "recuperacao (b)")
    esperar_saudavel("coordenador")
    ev.bloco("(b) Diario do coordenador", "\n".join(eventos_2pc(tid_b)))
    ev.verificar("(b) ABORTADA com codigo RECUPERACAO e sem movimentos",
                 estado_bd(tid_b)["codigo_erro"] == "RECUPERACAO" and movimentos(tid_b) == [])
    depois = saldos()
    ev.saldos("depois", depois, contas)
    ev.verificar("so a transferencia (a) mudou saldos (30.00)",
                 antes["EU-1002"] - depois["EU-1002"] == 3000 and depois["US-2002"] - antes["US-2002"] == 3000
                 and depois["EU-1001"] == antes["EU-1001"] and depois["US-2001"] == antes["US-2001"])
    ev.verificar("nenhuma transaccao preparada ficou por resolver", preparadas() == {"europa": [], "america": []})
    return ev


def c08_queda_api():
    ev = Evidencia(8, "queda_da_api", "Queda de uma instancia da API e utilizacao da outra",
                   "Com api-1 parada, o cliente passa para api-2. O token emitido antes continua valido porque "
                   "api-2 o valida localmente com a chave publica.")
    contas = ["EU-1001", "US-2001"]
    antes = saldos()
    ev.saldos("antes", antes, contas)
    c = Cliente(apis=[API1, API2])
    c.login("ana", SENHAS["ana"])
    r0 = c.pedido("GET", "/api/v1/contas/EU-1001/saldo")
    ev.passo(f"Com as duas instancias activas, respondeu {r0.headers.get('X-Instancia')}")
    ev.passo("docker compose stop api-1")
    compose("stop", "api-1")
    avisos = []
    c._log = avisos.append
    r1 = c.pedido("GET", "/api/v1/contas/EU-1001/saldo")
    r2 = c.transferir("EU-1001", "US-2001", "5.00")
    ev.bloco("Mensagens do cliente (failover)", "\n".join(avisos))
    ev.bloco("Respostas com api-1 em baixo", {"saldo": resposta(r1), "transferencia": resposta(r2)})
    ev.verificar("saldo respondido por api-2", r1.status_code == 200 and r1.headers.get("X-Instancia") == "api-2")
    ev.verificar("transferencia concluida via api-2 (ordem assinada por api-2)",
                 r2.status_code == 201 and r2.json()["instancia_api"] == "api-2")
    ev.verificar("o token emitido antes da queda foi aceite por api-2 (sem novo login)", r1.status_code == 200)
    ev.passo("docker compose start api-1")
    compose("start", "api-1")
    esperar_saudavel("api-1")
    r3 = c.pedido("GET", "/api/v1/contas/EU-1001/saldo")
    ev.verificar("api-1 volta a responder", r3.headers.get("X-Instancia") == "api-1")
    depois = saldos()
    ev.saldos("depois", depois, contas)
    ev.verificar("saldos mudaram so pela transferencia de 5.00",
                 antes["EU-1001"] - depois["EU-1001"] == 500 and depois["US-2001"] - antes["US-2001"] == 500)
    return ev


def c09_tokens():
    ev = Evidencia(9, "token_e_autorizacao", "Token invalido ou expirado e acesso sem autorizacao",
                   "As APIs validam assinatura, expiracao, emissor e destinatario do JWT, e so deixam o titular "
                   "consultar ou movimentar a conta.")
    priv = (RAIZ / "segredos" / "jwt-privada.pem").read_bytes()
    falsa = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    agora = int(time.time())
    base = {"iss": "https://auth:8000", "aud": "global-scale-api", "sub": "ana", "regiao": "EU", "iat": agora}
    tokens = {
        "sem token": None,
        "assinado com outra chave": pyjwt.encode(base | {"exp": agora + 600}, falsa, algorithm="RS256"),
        "expirado (chave verdadeira)": pyjwt.encode(base | {"iat": agora - 7200, "exp": agora - 3600}, priv, algorithm="RS256"),
        "destinatario errado": pyjwt.encode(base | {"aud": "outro", "exp": agora + 600}, priv, algorithm="RS256"),
        "emissor errado": pyjwt.encode(base | {"iss": "https://intruso", "exp": agora + 600}, priv, algorithm="RS256"),
        "algoritmo none": pyjwt.encode(base | {"exp": agora + 600}, None, algorithm="none"),
        "token adulterado (sub=bruno)": None,
    }
    valido = cliente("ana").token
    cab, carga, sig = valido.split(".")
    dados = json.loads(base64.urlsafe_b64decode(carga + "=="))
    dados["sub"] = "bruno"
    tokens["token adulterado (sub=bruno)"] = cab + "." + base64.urlsafe_b64encode(
        json.dumps(dados).encode()).decode().rstrip("=") + "." + sig
    linhas = []
    for nome, tok in tokens.items():
        h = {"Authorization": f"Bearer {tok}"} if tok else {}
        r = httpx.get(f"{API1}/api/v1/contas/EU-1001/saldo", headers=h, verify=CA)
        linhas.append(f"{nome:<30} HTTP {r.status_code}  {r.json().get('detail')}")
        ev.verificar(f"{nome}: HTTP 401", r.status_code == 401)
    ev.bloco("Pedidos a GET /api/v1/contas/EU-1001/saldo", "\n".join(linhas))

    ev.passo("Palavra-passe errada no servico de autenticacao")
    r = httpx.post(f"https://{HOST}:8000/api/v1/autenticacao/token",
                   json={"utilizador": "ana", "palavra_passe": "errada"}, verify=CA)
    ev.verificar("palavra-passe errada: HTTP 401", r.status_code == 401)

    ev.passo("bruno, com token valido, tenta usar a conta da ana")
    b = cliente("bruno")
    casos = {"consultar saldo de EU-1001": b.pedido("GET", "/api/v1/contas/EU-1001/saldo"),
             "historico de EU-1001": b.pedido("GET", "/api/v1/contas/EU-1001/movimentos"),
             "transferir a partir de EU-1001": b.transferir("EU-1001", "EU-1003", "100.00")}
    if "tid_c01" in CONTEXTO:
        casos["ver a transferencia da ana"] = b.pedido("GET", f"/api/v1/transferencias/{CONTEXTO['tid_c01']}")
    texto = []
    for nome, rr in casos.items():
        texto.append(f"{nome:<32} HTTP {rr.status_code}  {rr.json().get('detail')}")
        ev.verificar(f"bruno: {nome} -> recusado (403/404)", rr.status_code in (403, 404))
    ev.bloco("Autorizacao", "\n".join(texto))

    ev.passo("Validacao descentralizada: parar o servico de autenticacao e usar o token ja emitido")
    compose("stop", "auth")
    a = Cliente(apis=[API2], mostrar=False)
    a.token = valido
    r = a.pedido("GET", "/api/v1/contas/EU-1001/saldo")
    ev.verificar("com o emissor em baixo, api-2 continua a aceitar o token valido (HTTP 200)", r.status_code == 200)
    compose("start", "auth")
    esperar_saudavel("auth")
    return ev


def c10_adulteracao():
    ev = Evidencia(10, "mensagem_adulterada", "Mensagem de transferencia adulterada",
                   "Um intermediario altera o montante de uma ordem assinada por api-1. O coordenador verifica a "
                   "assinatura RSA-PSS/SHA-256 antes de tocar nos saldos e recusa a ordem.")
    contas = ["EU-1001", "US-2001"]
    antes = saldos()
    ev.saldos("antes", antes, contas)
    token = cliente("ana").token
    priv = (RAIZ / "segredos" / "assinatura-api-1.pem").read_bytes()

    def ordem(montante, emitido=None):
        return {"id": str(uuid.uuid4()), "chave_idempotencia": f"c10-{uuid.uuid4()}", "utilizador": "ana",
                "conta_origem": "EU-1001", "conta_destino": "US-2001", "montante_centimos": montante,
                "moeda": "EUR", "emitido_em": emitido or assinatura.agora_utc(), "instancia": "api-1"}

    def enviar(m, s):
        return httpx.post(f"{COORD}/transferencias", json={"mensagem": m, "assinatura": s},
                          headers={"Authorization": f"Bearer {token}"}, verify=CA)
    original = ordem(100)
    sig = assinatura.assinar(original, priv)
    adulterada = dict(original, montante_centimos=99999900)
    ev.passo("Ordem de 1.00 assinada com a chave de api-1; o montante e alterado para 999 999.00")
    ev.bloco("Representacao canonica e SHA-256", {
        "original": assinatura.canonico(original).decode(), "sha256 original": assinatura.resumo_sha256(original),
        "adulterada": assinatura.canonico(adulterada).decode(), "sha256 adulterada": assinatura.resumo_sha256(adulterada)})
    r1 = enviar(adulterada, sig)
    falsa = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    m2 = ordem(99999900)
    r2 = enviar(m2, assinatura.assinar(m2, falsa))
    antiga = ordem(100, (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)).isoformat(timespec="milliseconds"))
    r3 = enviar(antiga, assinatura.assinar(antiga, priv))
    meio = saldos()
    r4 = enviar(original, sig)
    ev.bloco("Respostas do coordenador", {"montante adulterado": resposta(r1), "assinada por chave desconhecida": resposta(r2),
                                          "ordem antiga (repeticao)": resposta(r3), "ordem original intacta": resposta(r4)})
    ev.verificar("montante adulterado: HTTP 401 assinatura invalida", r1.status_code == 401)
    ev.verificar("assinada com outra chave: HTTP 401", r2.status_code == 401)
    ev.verificar("ordem com mais de 120 s: HTTP 401 (fora da janela)", r3.status_code == 401)
    ev.verificar("nenhum saldo mudou com as ordens recusadas", all(meio[x] == antes[x] for x in contas))
    ev.verificar("a ordem original intacta e aceite (HTTP 201)", r4.status_code == 201)
    depois = saldos()
    ev.saldos("depois", depois, contas)
    ev.verificar("so a ordem intacta (1.00) mudou saldos",
                 antes["EU-1001"] - depois["EU-1001"] == 100 and depois["US-2001"] - antes["US-2001"] == 100)
    time.sleep(6)
    recusas = compose("exec", "-T", "nfs", "sh", "-c", "cat /exports/dfs/auditoria/*/*ORDEM_RECUSADA*.json | tail -40")
    ev.bloco("Auditoria no DFS: ordens recusadas", recusas[-1500:])
    ev.verificar("a recusa ficou registada na auditoria do DFS", original["id"] in recusas)
    return ev


def c11_java():
    ev = Evidencia(11, "python_java", "Comunicacao entre Python e Java (XML sobre HTTPS)",
                   "O coordenador (Python) confirma cada transferencia concluida no banco parceiro (Java) com XML; "
                   "a API consulta o registo no Java. Testa-se a validacao do XML e a indisponibilidade do Java.")
    c = cliente("ana")
    if "tid_c01" not in CONTEXTO:
        CONTEXTO["tid_c01"] = c.transferir("EU-1001", "US-2001", "125.50").json()["id"]
    tid = CONTEXTO["tid_c01"]
    ev.passo("GET /api/v1/parceiro/transferencias/{id}: a API (Python) consulta o banco parceiro (Java)")
    r = c.pedido("GET", f"/api/v1/parceiro/transferencias/{tid}")
    ev.bloco("Resposta (o campo xml_recebido e o XML devolvido pelo Java)", r.json())
    est = c.pedido("GET", f"/api/v1/transferencias/{tid}").json()
    ev.verificar("o Java tem a transferencia com a mesma referencia que o coordenador guardou",
                 r.status_code == 200 and r.json()["registo"]["referenciaParceiro"] == est["parceiro"]["referencia"])
    ev.verificar("montante no Java igual ao do coordenador",
                 r.json()["registo"]["montanteCentimos"] == str(est["montante_centimos"]))

    ev.passo("XML invalido enviado directamente ao Java")
    invalidos = {
        "montante negativo": f'<confirmacaoTransferencia versao="1"><id>{uuid.uuid4()}</id><contaOrigem>EU-1001</contaOrigem>'
                             '<contaDestino>US-2001</contaDestino><montanteCentimos>-5</montanteCentimos><moeda>EUR</moeda>'
                             '<concluidaEm>2026-11-19T10:00:00Z</concluidaEm></confirmacaoTransferencia>',
        "falta a conta de destino": f'<confirmacaoTransferencia versao="1"><id>{uuid.uuid4()}</id><contaOrigem>EU-1001</contaOrigem>'
                                    '<montanteCentimos>5</montanteCentimos><moeda>EUR</moeda>'
                                    '<concluidaEm>2026-11-19T10:00:00Z</concluidaEm></confirmacaoTransferencia>',
        "XML mal formado": "<confirmacaoTransferencia><id>",
        "DTD com entidade externa (XXE)": '<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
                                          '<confirmacaoTransferencia versao="1"><id>&x;</id></confirmacaoTransferencia>',
    }
    texto = []
    for nome, xml in invalidos.items():
        rr = httpx.post(f"{PARCEIRO}/legado/confirmacoes", content=xml.encode(), verify=CA,
                        headers={"Content-Type": "application/xml"})
        texto.append(f"--- {nome}: HTTP {rr.status_code}\n{rr.text}")
        ev.verificar(f"{nome}: HTTP 400 com <erro>", rr.status_code == 400 and "<erro>" in rr.text)
    ev.bloco("Validacao no Java", "\n".join(texto))

    ev.passo("docker compose stop banco-parceiro; nova transferencia de 7.00")
    compose("stop", "banco-parceiro")
    r2 = c.transferir("EU-1002", "US-2001", "7.00")
    tid2 = r2.json()["id"]
    r3 = c.pedido("GET", f"/api/v1/parceiro/transferencias/{tid2}")
    ev.bloco("Com o Java em baixo", {"transferencia": resposta(r2), "consulta ao parceiro": resposta(r3)})
    ev.verificar("a transferencia conclui na mesma (o Java nao faz parte do 2PC)",
                 r2.status_code == 201 and r2.json()["estado"] == "CONCLUIDA")
    ev.verificar("confirmacao ao parceiro fica POR_ENVIAR", estado_bd(tid2)["parceiro"] == "POR_ENVIAR")
    ev.verificar("a consulta ao Java devolve HTTP 503 (indisponivel)", r3.status_code == 503)
    ev.passo("docker compose start banco-parceiro; o coordenador repete a confirmacao")
    compose("start", "banco-parceiro")
    esperar(lambda: estado_bd(tid2)["parceiro"] == "CONFIRMADA", 60, 1, "confirmacao do parceiro")
    ev.verificar("depois de o Java voltar: CONFIRMADA", estado_bd(tid2)["parceiro"] == "CONFIRMADA")
    ev.bloco("Log do servico Java", "\n".join(compose("logs", "--no-color", "--tail", "15", "banco-parceiro").splitlines()))
    return ev


def c12_dfs():
    ev = Evidencia(12, "dfs_nfs", "Escrita e leitura dos ficheiros partilhados (NFS)",
                   "api-1 escreve um relatorio no NFS e api-2 le-o; os eventos de auditoria de varios servicos "
                   "ficam no mesmo DFS; com o NFS em baixo os eventos ficam em espera e sao publicados depois.",
                   "Com dois PCs, o servidor NFS esta no PC A e o api-2 do PC B monta-o pela rede.")
    montagens = []
    for s in ("api-1", "api-2", "coordenador"):
        montagens.append(f"{s}: " + compose("exec", "-T", s, "sh", "-c", "grep ' /mnt/dfs ' /proc/mounts"))
    ev.bloco("Montagens de /mnt/dfs (/proc/mounts)", "\n".join(montagens))
    ev.verificar("os tres servicos montam /mnt/dfs por nfs4 a partir de 172.30.2.40",
                 all(" nfs4 " in m and "172.30.2.40" in m for m in montagens))
    ana1, ana2 = cliente("ana", [API1]), cliente("ana", [API2])
    ev.passo("api-1: POST /api/v1/relatorios/extracto (EU-1001)")
    r = ana1.pedido("POST", "/api/v1/relatorios/extracto", json={"conta": "EU-1001"})
    nome = r.json()["nome"]
    ev.passo(f"api-2: GET /api/v1/relatorios/{nome}")
    lido = ana2.pedido("GET", f"/api/v1/relatorios/{nome}")
    no_servidor = compose("exec", "-T", "nfs", "ls", "-l", "/exports/dfs/relatorios")
    ev.bloco("Relatorio escrito por api-1 e lido por api-2", f"{r.json()}\n\nlido por {lido.headers.get('X-Lido-Por')}:\n"
             + lido.text[:600] + f"\n\nNo disco do servidor NFS:\n{no_servidor}")
    ev.verificar("escrito por api-1 e lido por api-2 (transparencia de localizacao)",
                 r.json()["escrito_por"] == "api-1" and lido.headers.get("X-Lido-Por") == "api-2" and "EU-1001" in lido.text)
    ev.verificar("o ficheiro esta no disco do servidor NFS", nome in no_servidor)
    if "tid_c01" in CONTEXTO:
        aud = ana2.pedido("GET", f"/api/v1/transferencias/{CONTEXTO['tid_c01']}/auditoria").json()
        ev.bloco("Auditoria da transferencia do cenario 1, lida por api-2",
                 "\n".join(f"{e['data_utc']}  {e['servico']:<12} {e['evento']:<22} {e['resultado'][:60]}  ({e['ficheiro']})"
                           for e in aud["eventos"]))
        ev.verificar("eventos escritos por servicos diferentes (api-1 e coordenador) no mesmo DFS",
                     {"api-1", "coordenador"} <= {e["servico"] for e in aud["eventos"]})
        ev.verificar("cada evento tem id da transferencia, data UTC, servico e resultado",
                     all({"transferencia_id", "data_utc", "servico", "resultado"} <= set(e) for e in aud["eventos"]))
    contagem = compose("exec", "-T", "nfs", "sh", "-c",
                       "echo ficheiros: $(find /exports/dfs/auditoria -name '*.json' | wc -l); "
                       "echo temporarios: $(find /exports/dfs/auditoria -name '.*.tmp' | wc -l); "
                       "for s in api-1 api-2 coordenador; do echo $s: $(find /exports/dfs/auditoria -name \"*_${s}_*\" | wc -l); done")
    ev.bloco("Ficheiros de auditoria no servidor NFS (um ficheiro por evento)", contagem)
    ev.verificar("nenhum ficheiro incompleto (.tmp) no DFS", "temporarios: 0" in contagem)

    ev.passo("Falha do DFS: docker compose stop nfs; nova transferencia")
    compose("stop", "nfs")
    r2 = ana1.transferir("EU-1001", "US-2002", "3.00")
    tid2 = r2.json()["id"]
    time.sleep(3)
    espera = compose("exec", "-T", "coordenador", "sh", "-c", "ls /var/spool/gs-auditoria | wc -l")
    ev.verificar("com o NFS em baixo a transferencia conclui (HTTP 201)", r2.status_code == 201)
    ev.verificar(f"eventos guardados na pasta de espera local do coordenador ({espera})", int(espera.split()[-1]) > 0)
    ev.passo("docker compose start nfs; esperar que os eventos sejam publicados")
    compose("start", "nfs")
    esperar_saudavel("nfs")
    esperar(lambda: compose("exec", "-T", "coordenador", "sh", "-c", "ls /var/spool/gs-auditoria | wc -l").split()[-1] == "0",
            120, 3, "pasta de espera vazia")
    publicados = compose("exec", "-T", "nfs", "sh", "-c", f"ls /exports/dfs/auditoria/*/ | grep {tid2}")
    ev.bloco("Eventos da transferencia feita com o NFS em baixo, ja no DFS", publicados)
    ev.verificar("os eventos foram publicados no DFS depois de o NFS voltar", "coordenador_CONCLUIDA" in publicados)
    return ev


CENARIOS = {0: c00_ambiente, 1: c01_sucesso, 2: c02_saldo_insuficiente, 3: c03_concorrencia, 4: c04_idempotencia,
            5: c05_falha_preparacao, 6: c06_falha_confirmacao, 7: c07_reinicio_coordenador, 8: c08_queda_api,
            9: c09_tokens, 10: c10_adulteracao, 11: c11_java, 12: c12_dfs}


def invariantes(total_inicial: int) -> Evidencia:
    ev = Evidencia(99, "invariantes", "Verificacao global de consistencia",
                   "Conservacao dos fundos e um debito + um credito por transferencia, em todo o sistema.")
    s = saldos()
    ev.bloco("Saldos finais", {k: eur(v) for k, v in s.items()})
    ev.verificar(f"soma de todos os saldos = {eur(total_inicial)} (inicial)", sum(s.values()) == total_inicial)
    ev.verificar("nenhum saldo negativo", min(s.values()) >= 0)
    transf = coord_sql("SELECT id, estado, conta_origem, conta_destino, montante_centimos FROM transferencias")
    movs: dict[str, list] = {}
    for no, (sv, p) in NOS.items():
        for tid, tipo, conta, m in psql(sv, p, "SELECT transferencia_id, tipo, conta_id, montante_centimos FROM movimentos"):
            movs.setdefault(tid, []).append((tipo, conta, int(m)))
    erros = []
    for tid, estado, o, d, m in transf:
        mv = sorted(movs.get(tid, []))
        if estado == "CONCLUIDA" and mv != sorted([("DEBITO", o, int(m)), ("CREDITO", d, int(m))]):
            erros.append(f"{tid} CONCLUIDA com movimentos {mv}")
        if estado == "ABORTADA" and mv:
            erros.append(f"{tid} ABORTADA com movimentos {mv}")
        if estado not in ("CONCLUIDA", "ABORTADA"):
            erros.append(f"{tid} ainda em {estado}")
    orfaos = set(movs) - {t[0] for t in transf}
    resumo = {e: sum(1 for t in transf if t[1] == e) for e in {t[1] for t in transf}}
    ev.bloco("Transferencias no registo do coordenador", resumo)
    ev.verificar(f"{resumo.get('CONCLUIDA', 0)} concluidas: cada uma com exactamente um DEBITO e um CREDITO; "
                 f"abortadas sem movimentos", not erros)
    ev.verificar("nenhum movimento sem transferencia no coordenador", not orfaos)
    ev.verificar("nenhuma transaccao preparada por resolver", preparadas() == {"europa": [], "america": []})
    if erros:
        ev.bloco("Inconsistencias", "\n".join(erros))
    return ev


def main():
    escolhidos = [int(a) for a in sys.argv[1:]] or list(CENARIOS)
    EVID.mkdir(exist_ok=True)
    # Soma dos dados de demonstracao: Europa 5000 + 1500 + 300, America 3000 + 800 = 10 600.00 EUR.
    # As transferencias so movem dinheiro entre contas, por isso a soma nunca pode mudar.
    total_inicial = 1060000
    CONTEXTO["debitos_eu1003_antes"] = int(psql("db-europa", 5433, "SELECT count(*) FROM movimentos "
                                                                   "WHERE conta_id='EU-1003' AND tipo='DEBITO'")[0][0])
    resultados = []
    for n in escolhidos:
        print(f"\n=== Cenario {n}: {CENARIOS[n].__name__}")
        try:
            ev = CENARIOS[n]()
        except Exception:
            ev = Evidencia(n, CENARIOS[n].__name__[4:], CENARIOS[n].__name__, "erro na execucao")
            ev.bloco("Erro", traceback.format_exc())
            ev.verificar("o cenario executou sem erros", False)
            traceback.print_exc()
            compose("unpause", "db-america")
            for s in ("db-america", "db-europa", "coordenador", "api-1", "auth", "banco-parceiro", "nfs"):
                compose("start", s)
        ev.gravar()
        resultados.append(ev)
    print("\n=== Verificacao global")
    final = invariantes(total_inicial)
    final.gravar()
    linhas = ["# Resumo das evidencias", "", f"Executado em {time.strftime('%Y-%m-%d %H:%M:%S')} "
              f"(Docker Compose local, um computador). Cada linha indica a data da execucao no ficheiro do cenario.", "",
              "| # | Cenario | Resultado | Verificacoes | Dois PCs |", "|---|---|---|---|---|"]
    gravadas = sorted((json.loads(f.read_text(encoding="utf-8")) | {"ficheiro": f.stem} for f in EVID.glob("*.json")),
                      key=lambda d: d["cenario"])
    for d in gravadas:                   # todas as evidencias gravadas, incluindo as de execucoes anteriores
        ok = sum(1 for _, o in d["verificacoes"] if o)
        dois = any(p.startswith("**Dois") for p in (EVID / f"{d['ficheiro']}.md").read_text(encoding="utf-8").splitlines())
        linhas.append(f"| {d['cenario']} | [{d['titulo']}]({d['ficheiro']}.md) | {'PASSOU' if d['passou'] else 'FALHOU'} | "
                      f"{ok}/{len(d['verificacoes'])} | {'sim (ver nota)' if dois else ''} |")
    (EVID / "RESUMO.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("\n" + "\n".join(linhas))
    sys.exit(0 if all(ev.passou for ev in resultados + [final]) else 1)


if __name__ == "__main__":
    main()
