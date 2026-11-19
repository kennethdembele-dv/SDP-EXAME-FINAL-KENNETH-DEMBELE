"""A API serve a interface Web (sem bases de dados: so ficheiros estaticos e rotas)."""
import importlib
import os

from fastapi.testclient import TestClient


def _app():
    os.environ.update({"INSTANCIA": "api-1", "PORTA": "8001", "PG_SENHA_LEITURA": "x"})
    return importlib.import_module("api.main").app


def test_raiz_redirecciona_para_a_interface():
    r = TestClient(_app()).get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/app/"


def test_ficheiros_da_interface():
    c = TestClient(_app())
    pagina = c.get("/app/")
    assert pagina.status_code == 200 and "Global-Scale" in pagina.text and 'src="app.js"' in pagina.text
    assert c.get("/app/app.js").status_code == 200 and c.get("/app/app.css").status_code == 200
    assert pagina.headers["X-Instancia"] == "api-1"


def test_estado_do_sistema_exige_token():
    assert TestClient(_app()).get("/api/v1/sistema/estado").status_code == 401
