"""Pausas de laboratorio no coordenador, para derrubar um servico no momento exacto da defesa.

    python testes/lab.py pausa antes_commit_america 20

Pontos: antes_preparar_europa, antes_preparar_america, apos_preparar, apos_decisao,
        antes_commit_europa, antes_commit_america, antes_rollback_europa, antes_rollback_america
A pausa aplica-se uma vez, a proxima transferencia que chegar a esse ponto.
So funciona com LABORATORIO=1 no .env; a chave vem de CHAVE_LABORATORIO.
"""
import os
import sys
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
ENV = dict(l.split("=", 1) for l in (RAIZ / ".env").read_text(encoding="utf-8").splitlines()
           if "=" in l and not l.startswith("#"))

if len(sys.argv) != 4 or sys.argv[1] != "pausa":
    sys.exit(__doc__)
r = httpx.post(f"https://{os.environ.get('GS_HOST', 'localhost')}:8100/laboratorio/pausa",
               json={"ponto": sys.argv[2], "segundos": float(sys.argv[3])},
               headers={"X-Chave-Laboratorio": ENV["CHAVE_LABORATORIO"]}, verify=str(RAIZ / "segredos" / "ca.crt"))
print(r.status_code, r.text)
