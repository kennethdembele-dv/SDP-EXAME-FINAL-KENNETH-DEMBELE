"""Ligacoes ao PostgreSQL, sempre com TLS e verificacao do certificado do servidor.

sslmode=verify-full: o cliente exige TLS, verifica que o certificado foi assinado pela CA do
laboratorio (sslrootcert) e que o nome no certificado coincide com o host a que se liga
(db-europa, db-america ou db-coordenador). Sem isto, um intermediario poderia fazer-se passar pela BD.
"""
import os

from psycopg.conninfo import make_conninfo

from comum import config


def dsn(host: str, porta: int, utilizador: str, senha: str, base: str = config.BASE_DADOS) -> str:
    # make_conninfo poe aspas nos valores que precisam (caminhos com espacos, simbolos na senha).
    return make_conninfo(host=host, port=porta, dbname=base, user=utilizador, password=senha,
                         sslmode="verify-full", sslrootcert=str(config.CA), connect_timeout=3,
                         application_name=os.environ.get("INSTANCIA", "servico"))


def dsn_no(no: str, utilizador: str, senha: str) -> str:
    n = config.NOS[no]
    return dsn(n["host"], n["porta"], utilizador, senha)
