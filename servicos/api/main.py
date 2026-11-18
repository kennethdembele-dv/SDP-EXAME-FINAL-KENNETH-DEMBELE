"""API financeira (REST/JSON). Correm duas instancias iguais: api-1 e api-2.

- Valida o JWT localmente com a chave publica (nao contacta o servico de autenticacao).
- Le saldos e historico directamente no no da regiao da conta (fragmentacao por prefixo).
- Para transferir, assina a ordem com a sua chave privada e envia-a ao coordenador 2PC.

Concorrencia: os endpoints sao funcoes normais (def). O FastAPI corre cada pedido numa thread
de um pool; enquanto uma thread espera pela base de dados ou pela rede, o GIL e libertado e as
outras threads avancam. As ligacoes a BD vem de um pool partilhado e seguro entre threads.
"""
import csv
import io
import os
import re
import uuid
from contextlib import asynccontextmanager

import httpx
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from psycopg_pool import NullConnectionPool, PoolTimeout
from pydantic import BaseModel, Field

from comum import assinatura, auditoria, bd, config, contrato_parceiro, dinheiro, servidor, tokens

INSTANCIA = os.environ["INSTANCIA"]                 # api-1 ou api-2
PORTA = int(os.environ["PORTA"])
utilizador_actual = tokens.dependencia(config.ler_segredo("jwt-publica.pem"))
CHAVE_ASSINATURA = config.ler_segredo(f"assinatura-{INSTANCIA}.pem")
CONTA = r"^(EU|US)-\d{4}$"

# Pool "nulo" por no: limita a 5 ligacoes simultaneas e abre uma ligacao por pedido, para que a API
# volte a ler um no logo que ele regresse de uma falha (sem esperar pelo atraso de religacao).
pools = {no: NullConnectionPool(bd.dsn_no(no, "gs_leitura", os.environ["PG_SENHA_LEITURA"]), max_size=5,
                                timeout=4, open=False)
         for no in config.NOS}
tls = config.contexto_tls_cliente()
# Timeout de comunicacao: se o coordenador nao responder em 30 s, o resultado fica DESCONHECIDO
# (nao e uma decisao de abortar: a transferencia pode ter sido confirmada).
coordenador = httpx.Client(base_url=config.COORDENADOR_URL, verify=tls, timeout=httpx.Timeout(30, connect=3))
parceiro = httpx.Client(base_url=config.BANCO_PARCEIRO_URL, verify=tls, timeout=httpx.Timeout(5, connect=3))
registo = auditoria.Auditoria(INSTANCIA)


@asynccontextmanager
async def ciclo_de_vida(app):
    for p in pools.values():
        p.open(wait=False)
    yield
    for p in pools.values():
        p.close()


app = FastAPI(title=f"Global-Scale: API financeira ({INSTANCIA})", version="1.0", lifespan=ciclo_de_vida,
              description="Consulta de contas, saldo, historico e transferencias entre regioes. "
                          "Autenticacao: Bearer JWT obtido em https://localhost:8000/api/v1/autenticacao/token")


@app.middleware("http")
async def identificar_instancia(request: Request, call_next):
    resposta = await call_next(request)
    resposta.headers["X-Instancia"] = INSTANCIA       # mostra qual das instancias respondeu
    return resposta


# ---------------------------------------------------------------- leitura nos fragmentos
def consultar(no: str, sql: str, parametros=()) -> list:
    try:
        with pools[no].connection() as c:
            return c.execute(sql, parametros).fetchall()
    except (PoolTimeout, psycopg.OperationalError):
        raise HTTPException(503, f"o no {no} esta indisponivel")


def conta_autorizada(conta: str, u: tokens.Utilizador):
    """Autorizacao: so o titular pode consultar ou movimentar a conta."""
    linhas = consultar(config.no_da_conta(conta),
                       "SELECT id, titular, moeda, saldo_centimos, criada_em FROM contas WHERE id = %s", (conta,))
    if not linhas:
        raise HTTPException(404, f"a conta {conta} nao existe")
    if linhas[0][1] != u.id:
        registo.registar("sem-transferencia", "ACESSO_NEGADO", "RECUSADO", conta=conta, utilizador=u.id)
        raise HTTPException(403, f"a conta {conta} nao pertence ao utilizador {u.id}")
    return linhas[0]


def conta_json(linha) -> dict:
    cid, titular, moeda, saldo, criada = linha
    return {"id": cid, "titular": titular, "moeda": moeda, "no": config.no_da_conta(cid),
            "saldo": dinheiro.formatar(saldo), "saldo_centimos": saldo, "criada_em": criada.isoformat()}


@app.get("/api/v1/contas", tags=["contas"])
def listar_contas(u: tokens.Utilizador = Depends(utilizador_actual)):
    no = config.PREFIXOS["EU" if u.regiao == "EU" else "US"]
    linhas = consultar(no, "SELECT id, titular, moeda, saldo_centimos, criada_em FROM contas "
                           "WHERE titular = %s ORDER BY id", (u.id,))
    return {"utilizador": u.id, "no": no, "contas": [conta_json(l) for l in linhas]}


@app.get("/api/v1/contas/{conta}", tags=["contas"])
def obter_conta(conta: str, u: tokens.Utilizador = Depends(utilizador_actual)):
    return conta_json(conta_autorizada(validar_conta(conta), u))


@app.get("/api/v1/contas/{conta}/saldo", tags=["contas"])
def saldo(conta: str, u: tokens.Utilizador = Depends(utilizador_actual)):
    linha = conta_autorizada(validar_conta(conta), u)
    return {"conta": conta, "saldo": dinheiro.formatar(linha[3]), "saldo_centimos": linha[3],
            "moeda": linha[2], "no": config.no_da_conta(conta)}


@app.get("/api/v1/contas/{conta}/movimentos", tags=["contas"])
def historico(conta: str, limite: int = 50, u: tokens.Utilizador = Depends(utilizador_actual)):
    conta_autorizada(validar_conta(conta), u)
    linhas = consultar(config.no_da_conta(conta),
                       "SELECT transferencia_id, tipo, montante_centimos, saldo_apos_centimos, contraparte, criado_em "
                       "FROM movimentos WHERE conta_id = %s ORDER BY criado_em DESC, id DESC LIMIT %s",
                       (conta, max(1, min(limite, 200))))
    return {"conta": conta, "movimentos": [
        {"transferencia_id": str(t), "tipo": tipo, "montante": dinheiro.formatar(m), "montante_centimos": m,
         "saldo_apos": dinheiro.formatar(s), "contraparte": cp, "data": d.isoformat()}
        for t, tipo, m, s, cp, d in linhas]}


def validar_conta(conta: str) -> str:
    if not re.match(CONTA, conta):
        raise HTTPException(422, "conta invalida: formato EU-0000 ou US-0000")
    return conta


# ---------------------------------------------------------------- transferencias
class PedidoTransferencia(BaseModel):
    conta_origem: str = Field(pattern=CONTA, examples=["EU-1001"])
    conta_destino: str = Field(pattern=CONTA, examples=["US-2001"])
    montante: str = Field(description="Texto decimal com ate 2 casas", examples=["125.50"])
    moeda: str = Field(default=config.MOEDA, pattern=r"^[A-Z]{3}$")


def falar_com_coordenador(metodo: str, caminho: str, u: tokens.Utilizador, **kw) -> httpx.Response:
    try:
        return coordenador.request(metodo, caminho, headers={"Authorization": f"Bearer {u.token}"}, **kw)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        # O pedido nem chegou ao coordenador: seguramente nada foi feito.
        raise HTTPException(503, "coordenador indisponivel: o pedido nao foi recebido; pode repetir com a mesma Idempotency-Key")
    except httpx.TransportError:
        # O pedido foi enviado mas a resposta perdeu-se (timeout ou ligacao cortada).
        # O resultado e DESCONHECIDO: a transferencia pode ter sido confirmada ou abortada.
        raise HTTPException(504, "sem resposta do coordenador: resultado DESCONHECIDO (nao significa falha). "
                                 "Repita com a mesma Idempotency-Key ou consulte GET /api/v1/transferencias?chave=...")


@app.post("/api/v1/transferencias", tags=["transferencias"], status_code=201)
def transferir(pedido: PedidoTransferencia, u: tokens.Utilizador = Depends(utilizador_actual),
               chave: str = Header(alias="Idempotency-Key", min_length=8, max_length=100,
                                   description="Chave unica do pedido; repetir com a mesma chave nao duplica")):
    try:
        centimos = dinheiro.para_centimos(pedido.montante)
    except dinheiro.MontanteInvalido as e:
        raise HTTPException(422, str(e))
    if pedido.conta_origem == pedido.conta_destino:
        raise HTTPException(422, "a conta de origem e a de destino sao a mesma")
    if pedido.moeda != config.MOEDA:
        raise HTTPException(422, f"moeda nao suportada: a demonstracao usa apenas {config.MOEDA}")
    conta_autorizada(pedido.conta_origem, u)

    # Ordem assinada: o coordenador so altera saldos se a assinatura for valida.
    mensagem = {"id": str(uuid.uuid4()), "chave_idempotencia": chave, "utilizador": u.id,
                "conta_origem": pedido.conta_origem, "conta_destino": pedido.conta_destino,
                "montante_centimos": centimos, "moeda": pedido.moeda,
                "emitido_em": assinatura.agora_utc(), "instancia": INSTANCIA}
    corpo = {"mensagem": mensagem, "assinatura": assinatura.assinar(mensagem, CHAVE_ASSINATURA)}
    r = falar_com_coordenador("POST", "/transferencias", u, json=corpo)
    resultado = r.json()
    registo.registar(resultado.get("id", mensagem["id"]), "ORDEM_ENVIADA", resultado.get("estado", f"HTTP {r.status_code}"),
                     utilizador=u.id, sha256=assinatura.resumo_sha256(mensagem), http=r.status_code)
    return JSONResponse(resultado, status_code=r.status_code)


@app.get("/api/v1/transferencias", tags=["transferencias"])
def listar_transferencias(chave: str | None = None, u: tokens.Utilizador = Depends(utilizador_actual)):
    r = falar_com_coordenador("GET", "/transferencias", u, params={"chave": chave} if chave else None)
    return JSONResponse(r.json(), status_code=r.status_code)


@app.get("/api/v1/transferencias/{tid}", tags=["transferencias"])
def estado_transferencia(tid: uuid.UUID, u: tokens.Utilizador = Depends(utilizador_actual)):
    r = falar_com_coordenador("GET", f"/transferencias/{tid}", u)
    return JSONResponse(r.json(), status_code=r.status_code)


def transferencia_do_utilizador(tid: uuid.UUID, u: tokens.Utilizador) -> dict:
    r = falar_com_coordenador("GET", f"/transferencias/{tid}", u)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.json().get("detail", "transferencia inexistente"))
    return r.json()


@app.get("/api/v1/transferencias/{tid}/auditoria", tags=["dfs"])
def auditoria_transferencia(tid: uuid.UUID, u: tokens.Utilizador = Depends(utilizador_actual)):
    """Eventos desta transferencia escritos no DFS por todos os servicos (de qualquer computador)."""
    transferencia_do_utilizador(tid, u)
    try:
        eventos = auditoria.ler_eventos(str(tid))
    except OSError as e:
        raise HTTPException(503, f"DFS indisponivel: {e}")
    return {"transferencia_id": str(tid), "lido_por": INSTANCIA, "eventos": eventos}


# ---------------------------------------------------------------- interoperabilidade (Java)
@app.get("/api/v1/parceiro/transferencias/{tid}", tags=["interoperabilidade"])
def consultar_parceiro(tid: uuid.UUID, u: tokens.Utilizador = Depends(utilizador_actual)):
    """Consulta o registo da transferencia no banco parceiro (servico Java, XML sobre HTTPS)."""
    transferencia_do_utilizador(tid, u)
    try:
        r = parceiro.get(f"/legado/transferencias/{tid}")
    except httpx.TransportError as e:
        raise HTTPException(503, f"banco parceiro indisponivel ({type(e).__name__}); a confirmacao sera repetida pelo coordenador")
    if r.status_code == 404:
        raise HTTPException(404, "o banco parceiro ainda nao tem esta transferencia")
    try:
        dados = contrato_parceiro.ler_registo(r.content, str(tid))
    except contrato_parceiro.ErroContrato as e:
        raise HTTPException(502, f"resposta do banco parceiro recusada: {e}")
    return {"fonte": "banco-parceiro (Java)", "formato": "XML", "registo": dados,
            "xml_recebido": r.content.decode("utf-8")}


# ---------------------------------------------------------------- relatorios no DFS
NOME_RELATORIO = re.compile(r"^(EU|US)-\d{4}_\d{8}T\d{6}Z_api-[12]\.csv$")


class PedidoExtracto(BaseModel):
    conta: str = Field(pattern=CONTA, examples=["EU-1001"])


@app.post("/api/v1/relatorios/extracto", tags=["dfs"], status_code=201)
def gerar_extracto(p: PedidoExtracto, u: tokens.Utilizador = Depends(utilizador_actual)):
    linha = conta_autorizada(p.conta, u)
    movs = historico(p.conta, 200, u)["movimentos"]
    texto = io.StringIO()
    w = csv.writer(texto)
    w.writerow(["conta", "titular", "saldo_actual", "gerado_por"])
    w.writerow([p.conta, linha[1], dinheiro.formatar(linha[3]), INSTANCIA])
    w.writerow([])
    w.writerow(["data", "tipo", "montante", "saldo_apos", "contraparte", "transferencia_id"])
    for m in movs:
        w.writerow([m["data"], m["tipo"], m["montante"], m["saldo_apos"], m["contraparte"], m["transferencia_id"]])
    nome = f"{p.conta}_{assinatura.agora_utc()[:19].replace('-', '').replace(':', '')}Z_{INSTANCIA}.csv"
    try:
        auditoria._escrever_atomico(config.DFS / "relatorios" / nome, texto.getvalue().encode())
    except OSError as e:
        raise HTTPException(503, f"DFS indisponivel: o relatorio nao foi gravado ({e})")
    return {"nome": nome, "caminho_dfs": f"/mnt/dfs/relatorios/{nome}", "escrito_por": INSTANCIA,
            "movimentos": len(movs)}


@app.get("/api/v1/relatorios", tags=["dfs"])
def listar_relatorios(u: tokens.Utilizador = Depends(utilizador_actual)):
    contas = {c["id"] for c in listar_contas(u)["contas"]}
    try:
        nomes = sorted(f.name for f in (config.DFS / "relatorios").glob("*.csv") if f.name[:7] in contas)
    except OSError as e:
        raise HTTPException(503, f"DFS indisponivel: {e}")
    return {"lido_por": INSTANCIA, "relatorios": nomes}


@app.get("/api/v1/relatorios/{nome}", tags=["dfs"], response_class=PlainTextResponse)
def ler_relatorio(nome: str, u: tokens.Utilizador = Depends(utilizador_actual)):
    if not NOME_RELATORIO.match(nome):           # impede caminhos como ../../etc/passwd
        raise HTTPException(422, "nome de relatorio invalido")
    conta_autorizada(nome[:7], u)
    try:
        conteudo = (config.DFS / "relatorios" / nome).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(404, "relatorio inexistente")
    except OSError as e:
        raise HTTPException(503, f"DFS indisponivel: {e}")
    return PlainTextResponse(conteudo, headers={"X-Lido-Por": INSTANCIA})


@app.get("/saude", tags=["sistema"])
def saude():
    return {"servico": INSTANCIA, "estado": "ok", "auditoria_por_publicar": registo.pendentes()}


if __name__ == "__main__":
    servidor.arrancar(app, INSTANCIA, PORTA)
