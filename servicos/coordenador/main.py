"""Coordenador de transaccoes distribuidas: interface HTTPS.

So aceita ordens de transferencia assinadas por uma instancia da API (api-1 ou api-2) e
acompanhadas do JWT do utilizador, que tambem e validado aqui de forma independente.
O protocolo esta em dois_fases.py.

Concorrencia: o servico e assincrono (asyncio). Um unico ciclo de eventos atende muitos pedidos
ao mesmo tempo: enquanto um pedido espera pela rede ou pela base de dados ("await"), outro avanca.
Varias transferencias avancam ao mesmo tempo; dentro de cada uma, a confirmacao dos dois nos e
feita em paralelo (asyncio.gather).
"""
import asyncio
import hmac
import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Literal

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, Field

from comum import assinatura, config, dinheiro, servidor, tokens
from coordenador import dois_fases as tpc

utilizador_actual = tokens.dependencia(config.ler_segredo("jwt-publica.pem"))
CHAVES_API = {n: config.ler_segredo(f"assinatura-{n}.pub.pem") for n in ("api-1", "api-2")}
LABORATORIO = os.environ.get("LABORATORIO", "0") == "1"
CHAVE_LABORATORIO = os.environ.get("CHAVE_LABORATORIO", "")
CONTA = re.compile(r"^(EU|US)-\d{4}$")

EXPLICACAO = {
    "INICIADA": "registada; a preparar os participantes",
    "PREPARADA": "todos os participantes prepararam; a gravar a decisao",
    "COMMIT_DECIDIDO": "decisao COMMIT gravada; falta aplica-la nos participantes pendentes "
                       "(o credito/debito aparece quando o no responder; a recuperacao repete automaticamente)",
    "CONCLUIDA": "confirmada em todos os participantes: um debito e um credito",
    "ABORT_DECIDIDO": "decisao ABORT gravada; a desfazer nos participantes pendentes (nenhum saldo muda)",
    "ABORTADA": "abortada em todos os participantes: nenhum saldo foi alterado",
}
HTTP_ERRO = {"SALDO_INSUFICIENTE": 422, "CONTA_INEXISTENTE": 422, "MOEDA_DIFERENTE": 422,
             "SEM_AUTORIZACAO": 403, "CONFLITO_BLOQUEIO": 409, "NO_INDISPONIVEL": 503, "RECUPERACAO": 503}


@asynccontextmanager
async def ciclo_de_vida(app):
    await tpc.log_bd.open(wait=False)
    for p in (*tpc.pools_preparar.values(), *tpc.pools_decidir.values()):
        await p.open(wait=False)
    recuperacao = asyncio.create_task(tpc.ciclo_recuperacao())   # primeiro ciclo = recuperacao de arranque
    yield
    recuperacao.cancel()


app = FastAPI(title="Global-Scale: coordenador 2PC", lifespan=ciclo_de_vida)


async def corpo(t: dict, repetido: bool = False) -> dict:
    ps = await tpc.participantes(t["id"])
    return {
        "id": str(t["id"]), "estado": t["estado"], "explicacao": EXPLICACAO[t["estado"]],
        "decisao": t["decisao"], "codigo_erro": t["codigo_erro"], "motivo": t["motivo"],
        "conta_origem": t["conta_origem"], "conta_destino": t["conta_destino"],
        "montante": dinheiro.formatar(t["montante_centimos"]), "montante_centimos": t["montante_centimos"],
        "moeda": t["moeda"], "utilizador": t["utilizador"], "chave_idempotencia": t["chave_idempotencia"],
        "instancia_api": t["instancia_api"],
        "participantes": [dict(p) for p in ps],
        "pendente_em": [p["no"] for p in ps if p["estado"] in ("PREPARADO", "INCERTO")
                        and t["estado"] in ("COMMIT_DECIDIDO", "ABORT_DECIDIDO")],
        "parceiro": {"estado": t["parceiro_estado"], "referencia": t["parceiro_referencia"]},
        "criada_em": t["criada_em"].isoformat(),
        "decidida_em": t["decidida_em"] and t["decidida_em"].isoformat(),
        "concluida_em": t["concluida_em"] and t["concluida_em"].isoformat(),
        "repetido": repetido,
    }


def codigo_http(t: dict, repetido: bool) -> int:
    if t["estado"] == "CONCLUIDA":
        return 200 if repetido else 201
    if t["estado"] in ("INICIADA", "PREPARADA", "COMMIT_DECIDIDO"):
        return 202                                   # aceite, ainda a concluir
    return HTTP_ERRO.get(t["codigo_erro"], 409)


class OrdemAssinada(BaseModel):
    mensagem: dict
    assinatura: str


def validar_ordem(m: dict) -> None:
    """A assinatura prova a origem; mesmo assim os dados sao validados antes de tocar em saldos."""
    erros = []
    if not isinstance(m.get("montante_centimos"), int) or not 0 < m["montante_centimos"] <= dinheiro.MAXIMO_CENTIMOS:
        erros.append("montante_centimos invalido")
    for campo in ("conta_origem", "conta_destino"):
        if not isinstance(m.get(campo), str) or not CONTA.match(m[campo]):
            erros.append(f"{campo} invalida")
    if m.get("conta_origem") == m.get("conta_destino"):
        erros.append("origem e destino iguais")
    if m.get("moeda") != config.MOEDA:
        erros.append("moeda nao suportada")
    if not isinstance(m.get("chave_idempotencia"), str) or not 8 <= len(m["chave_idempotencia"]) <= 100:
        erros.append("chave de idempotencia invalida")
    try:
        uuid.UUID(m.get("id", ""))
    except (ValueError, TypeError, AttributeError):
        erros.append("id invalido")
    if erros:
        raise HTTPException(422, "; ".join(erros))


@app.post("/transferencias")
async def receber_ordem(ordem: OrdemAssinada, u: tokens.Utilizador = Depends(utilizador_actual)):
    m = ordem.mensagem
    # 1. Integridade e autenticidade da ordem: verificar a assinatura ANTES de qualquer alteracao.
    try:
        chave = CHAVES_API.get(m.get("instancia"))
        if chave is None:
            raise assinatura.AssinaturaInvalida("ordem assinada por uma instancia desconhecida")
        assinatura.verificar(m, ordem.assinatura, chave)
        assinatura.verificar_janela(m)
    except assinatura.AssinaturaInvalida as e:
        tpc.registo.registar(str(m.get("id", "desconhecida")), "ORDEM_RECUSADA", "ASSINATURA_INVALIDA",
                             motivo=str(e), montante_centimos=m.get("montante_centimos"), utilizador=u.id)
        raise HTTPException(401, str(e))
    # 2. O utilizador da ordem tem de ser o do token (a API nao pode agir em nome de outro).
    if m["utilizador"] != u.id:
        raise HTTPException(403, "a ordem e de outro utilizador")
    validar_ordem(m)
    # 3. Idempotencia e 2PC.
    try:
        t, nova = await tpc.registar_ou_obter(m)
        if not nova:
            if t["hash_pedido"] != tpc.hash_pedido(m):
                raise HTTPException(409, "chave de idempotencia ja usada com dados diferentes")
            return JSONResponse(await corpo(t, repetido=True), status_code=codigo_http(t, True))
        await tpc.executar(t)
        t = await tpc.carregar(t["id"])
    except (PoolTimeout, psycopg.OperationalError):
        raise HTTPException(503, "registo do coordenador indisponivel")
    return JSONResponse(await corpo(t), status_code=codigo_http(t, False))


@app.get("/transferencias/{tid}")
async def obter(tid: uuid.UUID, u: tokens.Utilizador = Depends(utilizador_actual)):
    t = await tpc.carregar(tid)
    if t is None or t["utilizador"] != u.id:          # nao revela transferencias de outros
        raise HTTPException(404, "transferencia inexistente")
    return await corpo(t)


@app.get("/transferencias")
async def listar(chave: str | None = None, u: tokens.Utilizador = Depends(utilizador_actual)):
    async with tpc.log_bd.connection() as c:
        linhas = await (await c.execute(
            "SELECT * FROM transferencias WHERE utilizador = %s AND (%s::text IS NULL OR chave_idempotencia = %s) "
            "ORDER BY criada_em DESC LIMIT 50", (u.id, chave, chave))).fetchall()
    return {"transferencias": [await corpo(t) for t in linhas]}


class Pausa(BaseModel):
    ponto: Literal["antes_preparar_europa", "antes_preparar_america", "apos_preparar", "apos_decisao",
                   "antes_commit_europa", "antes_commit_america", "antes_rollback_europa", "antes_rollback_america"]
    segundos: float = Field(gt=0, le=60)


@app.post("/laboratorio/pausa")
async def pausa(p: Pausa, chave: str = Header("", alias="X-Chave-Laboratorio")):
    """So para a demonstracao: a proxima transferencia para neste ponto durante N segundos."""
    if not LABORATORIO or not hmac.compare_digest(chave, CHAVE_LABORATORIO):
        raise HTTPException(403, "modo laboratorio desligado ou chave errada")
    tpc.pausas[p.ponto] = p.segundos
    return {"ponto": p.ponto, "segundos": p.segundos}


@app.get("/saude")
async def saude():
    return {"servico": "coordenador", "estado": "ok", "em_curso": len(tpc.em_curso)}


if __name__ == "__main__":
    servidor.arrancar(app, "coordenador", 8100)
