"""Configuracao comum, lida das variaveis de ambiente (definidas no docker-compose.yml)."""
import os
import ssl
from pathlib import Path

# Os segredos chegam como "secrets" do Docker Compose, montados so de leitura em /run/secrets.
SEGREDOS = Path(os.environ.get("SEGREDOS", "/run/secrets"))
CA = SEGREDOS / "ca.crt"

# Fragmentacao: o prefixo da conta indica o no onde ela esta guardada.
NOS = {
    "europa": {"host": os.environ.get("DB_EUROPA_HOST", "db-europa"),
               "porta": int(os.environ.get("DB_EUROPA_PORTA", "5433"))},
    "america": {"host": os.environ.get("DB_AMERICA_HOST", "db-america"),
                "porta": int(os.environ.get("DB_AMERICA_PORTA", "5434"))},
}
PREFIXOS = {"EU": "europa", "US": "america"}
BASE_DADOS = "globalscale"
MOEDA = "EUR"          # moeda comum da demonstracao (ver README, "Decisoes")

# JWT: o emissor e o destinatario sao verificados pelas APIs e pelo coordenador.
JWT_EMISSOR = "https://auth:8000"
JWT_AUDIENCIA = "global-scale-api"
JWT_VALIDADE_S = int(os.environ.get("JWT_VALIDADE_S", "900"))

COORDENADOR_URL = os.environ.get("COORDENADOR_URL", "https://coordenador:8100")
BANCO_PARCEIRO_URL = os.environ.get("BANCO_PARCEIRO_URL", "https://banco-parceiro:8200")
DFS = Path(os.environ.get("DFS", "/mnt/dfs"))
SPOOL = Path(os.environ.get("SPOOL", "/var/spool/gs-auditoria"))


class ErroConfiguracao(Exception):
    pass


def no_da_conta(conta: str) -> str:
    """Devolve o no (fragmento) que guarda a conta: EU-xxxx -> europa, US-xxxx -> america."""
    try:
        return PREFIXOS[conta[:2]]
    except KeyError:
        raise ValueError(f"conta {conta!r} nao pertence a nenhuma regiao") from None


def contexto_tls_cliente() -> ssl.SSLContext:
    """TLS do lado do cliente: confia so na CA do laboratorio e verifica o nome do servidor."""
    ctx = ssl.create_default_context(cafile=str(CA))
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def ler_segredo(nome: str) -> bytes:
    return (SEGREDOS / nome).read_bytes()
