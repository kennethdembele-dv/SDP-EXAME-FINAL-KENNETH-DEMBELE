"""Servico emissor de tokens (no de autenticacao).

Verifica a palavra-passe no no regional onde o utilizador esta guardado e devolve um JWT
assinado com a chave privada RS256. E o unico servico que tem essa chave.
"""
import os
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException
from psycopg_pool import NullConnectionPool, PoolTimeout
from pydantic import BaseModel, Field

from comum import bd, config, palavras_passe, servidor, tokens

CHAVE_PRIVADA = config.ler_segredo("jwt-privada.pem")
SENHA_LEITURA = os.environ["PG_SENHA_LEITURA"]

# Um pool por no regional: no maximo 3 ligacoes simultaneas, abertas por pedido (pool "nulo"),
# para a autenticacao voltar a funcionar logo que um no regresse de uma falha.
pools = {no: NullConnectionPool(bd.dsn_no(no, "gs_leitura", SENHA_LEITURA), max_size=3, timeout=3, open=False)
         for no in config.NOS}

@asynccontextmanager
async def ciclo_de_vida(app):
    for p in pools.values():
        p.open(wait=False)      # nao bloqueia o arranque se um no estiver em baixo
    yield
    for p in pools.values():
        p.close()


app = FastAPI(title="Global-Scale: autenticacao", lifespan=ciclo_de_vida,
              description="Emissor de JWT RS256. As APIs validam os tokens com a chave publica.")


class Credenciais(BaseModel):
    utilizador: str = Field(min_length=1, max_length=64, examples=["ana"])
    palavra_passe: str = Field(min_length=1, max_length=128, examples=["Ana#2026"])


def procurar(utilizador: str):
    """Procura o utilizador nos dois fragmentos. Devolve (linha, nos_indisponiveis)."""
    indisponiveis = []
    for no, pool in pools.items():
        try:
            with pool.connection() as c:
                linha = c.execute("SELECT id, nome, regiao, hash_palavra_passe FROM utilizadores WHERE id = %s",
                                  (utilizador,)).fetchone()
        except (PoolTimeout, psycopg.OperationalError):   # no em baixo: tenta o outro
            indisponiveis.append(no)
            continue
        if linha:
            return linha, indisponiveis
    return None, indisponiveis


@app.post("/api/v1/autenticacao/token")
def emitir_token(cred: Credenciais):
    linha, indisponiveis = procurar(cred.utilizador)
    if linha is None:
        palavras_passe.verificar(cred.palavra_passe, palavras_passe.HASH_FICTICIO)  # mesmo tempo de resposta
        if indisponiveis:
            raise HTTPException(503, f"no(s) {', '.join(indisponiveis)} indisponivel(is); tente mais tarde")
        raise HTTPException(401, "utilizador ou palavra-passe errados")
    uid, nome, regiao, h = linha
    if not palavras_passe.verificar(cred.palavra_passe, h):
        raise HTTPException(401, "utilizador ou palavra-passe errados")
    token = tokens.emitir(CHAVE_PRIVADA, uid, nome, regiao)
    return {"access_token": token, "token_type": "bearer", "expires_in": config.JWT_VALIDADE_S,
            "utilizador": uid, "regiao": regiao}


@app.get("/saude")
def saude():
    return {"servico": "auth", "estado": "ok"}


if __name__ == "__main__":
    servidor.arrancar(app, "auth", 8000)
