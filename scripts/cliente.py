"""Cliente de demonstracao do Global-Scale, com failover entre as duas instancias da API.

    python scripts/cliente.py -u ana -p Ana#2026 contas
    python scripts/cliente.py -u ana -p Ana#2026 saldo EU-1001
    python scripts/cliente.py -u ana -p Ana#2026 transferir EU-1001 US-2001 25.00 [--chave minha-chave-1]
    python scripts/cliente.py -u ana -p Ana#2026 estado <id>
    python scripts/cliente.py -u ana -p Ana#2026 historico EU-1001
    python scripts/cliente.py -u ana -p Ana#2026 parceiro <id>      (consulta no banco Java)
    python scripts/cliente.py -u ana -p Ana#2026 auditoria <id>     (eventos no DFS)

Failover: os enderecos das APIs vem de GS_APIS (por omissao api-1 e depois api-2). Se uma instancia
nao aceitar a ligacao, o pedido segue para a outra. Um POST de transferencia so e repetido noutra
instancia com a MESMA Idempotency-Key, por isso nunca e executado duas vezes.
"""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
HOST = os.environ.get("GS_HOST", "localhost")
APIS = os.environ.get("GS_APIS", f"https://{HOST}:8001,https://{HOST}:8002").split(",")
AUTH = os.environ.get("GS_AUTH", f"https://{HOST}:8000")
CA = os.environ.get("GS_CA", str(RAIZ / "segredos" / "ca.crt"))


class Cliente:
    def __init__(self, apis=None, auth=AUTH, mostrar=True):
        self.apis = list(apis or APIS)
        self.auth = auth
        self.token = None
        self.mostrar = mostrar
        self.http = httpx.Client(verify=CA, timeout=httpx.Timeout(40, connect=3))
        self.ultima_instancia = None

    def _log(self, texto):
        if self.mostrar:
            print(texto, file=sys.stderr)

    def login(self, utilizador, palavra_passe):
        r = self.http.post(f"{self.auth}/api/v1/autenticacao/token",
                           json={"utilizador": utilizador, "palavra_passe": palavra_passe})
        r.raise_for_status()
        self.token = r.json()["access_token"]
        return self.token

    def pedido(self, metodo, caminho, idempotente=True, **kw) -> httpx.Response:
        cabecalhos = kw.pop("headers", {})
        if self.token:
            cabecalhos.setdefault("Authorization", f"Bearer {self.token}")
        ultimo_erro = None
        for base in self.apis:
            try:
                r = self.http.request(metodo, base + caminho, headers=cabecalhos, **kw)
                self.ultima_instancia = r.headers.get("X-Instancia", base)
                return r
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                self._log(f"[failover] {base} nao aceita ligacoes ({type(e).__name__}); a tentar a proxima instancia")
                ultimo_erro = e
            except httpx.TransportError as e:
                if not idempotente:
                    raise
                self._log(f"[failover] {base} sem resposta ({type(e).__name__}); repetir noutra instancia e seguro")
                ultimo_erro = e
        raise ultimo_erro

    def transferir(self, origem, destino, montante, chave=None) -> httpx.Response:
        chave = chave or f"cli-{uuid.uuid4()}"
        return self.pedido("POST", "/api/v1/transferencias", headers={"Idempotency-Key": chave},
                           json={"conta_origem": origem, "conta_destino": destino, "montante": montante})


def main():
    ap = argparse.ArgumentParser(description="Cliente do Global-Scale")
    ap.add_argument("-u", "--utilizador", required=True)
    ap.add_argument("-p", "--palavra-passe", required=True)
    ap.add_argument("comando", choices=["contas", "saldo", "historico", "transferir", "estado", "parceiro",
                                        "auditoria", "transferencias"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--chave", help="Idempotency-Key (por omissao, uma nova)")
    a = ap.parse_args()
    c = Cliente()
    c.login(a.utilizador, a.palavra_passe)
    rotas = {
        "contas": lambda: c.pedido("GET", "/api/v1/contas"),
        "saldo": lambda: c.pedido("GET", f"/api/v1/contas/{a.args[0]}/saldo"),
        "historico": lambda: c.pedido("GET", f"/api/v1/contas/{a.args[0]}/movimentos"),
        "transferir": lambda: c.transferir(a.args[0], a.args[1], a.args[2], a.chave),
        "estado": lambda: c.pedido("GET", f"/api/v1/transferencias/{a.args[0]}"),
        "transferencias": lambda: c.pedido("GET", "/api/v1/transferencias"),
        "parceiro": lambda: c.pedido("GET", f"/api/v1/parceiro/transferencias/{a.args[0]}"),
        "auditoria": lambda: c.pedido("GET", f"/api/v1/transferencias/{a.args[0]}/auditoria"),
    }
    r = rotas[a.comando]()
    print(f"HTTP {r.status_code} (respondeu {c.ultima_instancia})", file=sys.stderr)
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print(r.text)


if __name__ == "__main__":
    main()
