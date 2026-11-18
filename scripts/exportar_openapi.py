"""Exporta a documentacao OpenAPI dos servicos para docs/openapi/ (sem precisar do Docker).

    python scripts/exportar_openapi.py

Importa cada aplicacao FastAPI e grava app.openapi() em JSON. Nao abre ligacoes a bases de dados
(os pools so abrem no arranque do servidor). Precisa de segredos/ (python seguranca/gerar_materiais.py).
Com o sistema a correr, a mesma especificacao esta em https://localhost:8001/openapi.json e em /docs.
"""
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "servicos"))
os.environ.update({"SEGREDOS": str(RAIZ / "segredos"), "SPOOL": tempfile.mkdtemp(), "DFS": tempfile.mkdtemp(),
                   "PG_SENHA_LEITURA": "x", "PG_SENHA_TRANSACCOES": "x", "PG_SENHA_COORDENADOR": "x",
                   "INSTANCIA": "api-1", "PORTA": "8001"})
destino = RAIZ / "docs" / "openapi"
destino.mkdir(parents=True, exist_ok=True)
for modulo, ficheiro in (("api.main", "api.json"), ("autenticacao.main", "autenticacao.json"),
                         ("coordenador.main", "coordenador.json")):
    app = importlib.import_module(modulo).app
    especificacao = app.openapi()
    (destino / ficheiro).write_text(json.dumps(especificacao, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{destino / ficheiro}: {len(especificacao['paths'])} caminhos")
