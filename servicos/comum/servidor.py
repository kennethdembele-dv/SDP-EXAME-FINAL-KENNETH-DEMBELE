"""Arranque HTTPS comum: todos os servicos Web so aceitam TLS."""
import logging
import ssl
import sys

import uvicorn

from comum import config


def arrancar(app, nome: str, porta: int) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # O psycopg assincrono nao funciona com o ProactorEventLoop do Windows (so importa fora do Docker).
    ciclo = "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto"
    uvicorn.run(app, host="0.0.0.0", port=porta, loop=ciclo,
                ssl_certfile=str(config.SEGREDOS / f"{nome}.crt"),
                ssl_keyfile=str(config.SEGREDOS / f"{nome}.key"),
                ssl_version=ssl.PROTOCOL_TLS_SERVER, log_level="info", access_log=True)
