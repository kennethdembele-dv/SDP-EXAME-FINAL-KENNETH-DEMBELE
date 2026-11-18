"""JWT com assinatura assimetrica RS256 (RSA + SHA-256).

- O servico de autenticacao e o unico que tem a chave PRIVADA: so ele emite tokens.
- As APIs e o coordenador tem apenas a chave PUBLICA: validam o token localmente,
  sem contactar o emissor (validacao descentralizada).
"""
import time
import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from comum import config

ALGORITMO = "RS256"


def emitir(chave_privada: bytes, utilizador: str, nome: str, regiao: str,
           validade_s: int = config.JWT_VALIDADE_S) -> str:
    agora = int(time.time())
    reivindicacoes = {
        "iss": config.JWT_EMISSOR, "aud": config.JWT_AUDIENCIA,
        "sub": utilizador, "nome": nome, "regiao": regiao,
        "iat": agora, "nbf": agora, "exp": agora + validade_s,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(reivindicacoes, chave_privada, algorithm=ALGORITMO, headers={"kid": "gs-auth-1"})


@dataclass
class Utilizador:
    id: str
    nome: str
    regiao: str
    token: str


def validar(token: str, chave_publica: bytes) -> Utilizador:
    """Verifica assinatura, expiracao, emissor e destinatario. Lanca HTTPException 401."""
    try:
        r = jwt.decode(token, chave_publica, algorithms=[ALGORITMO],   # lista fixa: recusa "none" e HS256
                       audience=config.JWT_AUDIENCIA, issuer=config.JWT_EMISSOR, leeway=5,
                       options={"require": ["exp", "iat", "iss", "aud", "sub"]})
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token expirado", headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidAudienceError:
        raise HTTPException(401, "token emitido para outro destinatario", headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidIssuerError:
        raise HTTPException(401, "token de um emissor desconhecido", headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidSignatureError:
        raise HTTPException(401, "assinatura do token invalida", headers={"WWW-Authenticate": "Bearer"})
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"token invalido: {e}", headers={"WWW-Authenticate": "Bearer"})
    return Utilizador(id=r["sub"], nome=r.get("nome", r["sub"]), regiao=r.get("regiao", ""), token=token)


_esquema = HTTPBearer(auto_error=False)


def dependencia(chave_publica: bytes):
    """Dependencia FastAPI que exige um token valido em Authorization: Bearer <token>."""
    def utilizador_actual(cred: HTTPAuthorizationCredentials | None = Depends(_esquema)) -> Utilizador:
        if cred is None:
            raise HTTPException(401, "falta o token (Authorization: Bearer ...)",
                                headers={"WWW-Authenticate": "Bearer"})
        return validar(cred.credentials, chave_publica)
    return utilizador_actual
