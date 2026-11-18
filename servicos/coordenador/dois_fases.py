"""Two-Phase Commit com transaccoes preparadas reais do PostgreSQL.

Participantes: os nos regionais (europa, america). Coordenador: este servico.
Registo duravel do coordenador: a base db-coordenador (tabelas transferencias, participantes, eventos).

FASE 1 - PREPARACAO (um no de cada vez, sempre pela mesma ordem: europa e depois america):
    BEGIN; UPDATE contas ... (debito ou credito); INSERT INTO movimentos ...;
    PREPARE TRANSACTION 'gs-<id>-<no>';
  A ordem fixa evita bloqueios mutuos distribuidos: se duas transferencias preparassem os nos em
  paralelo, uma podia ficar com a linha no Europa e a outra com a linha no America, cada uma a espera
  da outra, sem que nenhum dos PostgreSQL detectasse o ciclo. Com todas a bloquear primeiro no Europa
  (e, dentro de cada no, as contas por ordem), nao ha ciclos de espera.
  Depois do PREPARE, o no garantiu que consegue confirmar: as alteracoes estao gravadas no disco
  e os bloqueios das linhas mantem-se, mesmo que o no reinicie, ate receber a decisao.
  Se algum no falhar ou recusar (saldo insuficiente, conta inexistente, timeout), a decisao e ABORT.

DECISAO - gravada no registo do coordenador (COMMIT da transaccao local, com fsync) ANTES de
  ser comunicada. A partir dai a decisao nunca muda.

FASE 2 - CONFIRMACAO: COMMIT PREPARED (ou ROLLBACK PREPARED) em cada participante, em paralelo
  (asyncio.gather): aqui ja nao se pedem bloqueios novos.
  Se um no nao responder, a transferencia fica com a decisao gravada e o no "pendente";
  o ciclo de recuperacao repete o comando ate o no voltar. Repetir e seguro (idempotente):
  primeiro consulta-se pg_prepared_xacts para saber se ainda ha algo a confirmar.

RECUPERACAO (no arranque e a cada 5 s):
  - decisao gravada mas nao aplicada em todos os nos -> repetir a decisao;
  - sem decisao (o coordenador caiu antes de decidir) -> ABORT presumido;
  - transaccao preparada num no sem registo no coordenador -> ROLLBACK PREPARED.

BLOQUEIO: um participante preparado NAO pode decidir sozinho (nao sabe se os outros prepararam).
  Se o coordenador cair depois de preparar, as linhas ficam bloqueadas ate o coordenador voltar.
  E o preco do 2PC; a recuperacao exige que o registo do coordenador sobreviva (volume persistente).
"""
import asyncio
import datetime as dt
import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass

import httpx
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncNullConnectionPool, PoolTimeout

from comum import auditoria, bd, config, contrato_parceiro

log = logging.getLogger("2pc")

TIMEOUT_PREPARAR_S = 10      # limite para um participante preparar
TIMEOUT_DECIDIR_S = 5        # limite para um participante confirmar; ao exceder, fica pendente
LOCK_TIMEOUT = "5s"          # espera maxima por uma linha bloqueada (resolve bloqueios mutuos)
INTERVALO_RECUPERACAO_S = 5

registo = auditoria.Auditoria("coordenador")

# Ligacoes: "pools nulos" (AsyncNullConnectionPool). Limitam quantas ligacoes podem estar abertas ao
# mesmo tempo (max_size; os pedidos a mais esperam na fila), mas abrem uma ligacao nova em cada
# operacao. Assim, quando um no volta depois de uma falha, a tentativa seguinte liga-se logo
# (um pool normal espera um intervalo crescente antes de voltar a tentar).
# As transaccoes preparadas nao dependem da ligacao: o COMMIT PREPARED pode vir de outra ligacao.

# Registo do coordenador (autocommit: cada escrita fica duravel quando o execute termina).
log_bd = AsyncNullConnectionPool(
    bd.dsn(os.environ.get("DB_COORDENADOR_HOST", "db-coordenador"), int(os.environ.get("DB_COORDENADOR_PORTA", "5435")),
           "gs_coordenador", os.environ["PG_SENHA_COORDENADOR"]),
    max_size=6, timeout=5, open=False, kwargs={"autocommit": True, "row_factory": dict_row})

# Dois pools por no: um para preparar e outro so para as decisoes. Assim um COMMIT PREPARED
# nunca fica a espera de ligacao enquanto outras preparacoes aguardam pelo bloqueio dessa linha.
_senha = os.environ["PG_SENHA_TRANSACCOES"]
pools_preparar = {no: AsyncNullConnectionPool(bd.dsn_no(no, "gs_transaccoes", _senha), max_size=8, timeout=5,
                                              open=False, kwargs={"autocommit": True}) for no in config.NOS}
pools_decidir = {no: AsyncNullConnectionPool(bd.dsn_no(no, "gs_transaccoes", _senha), max_size=3, timeout=5,
                                             open=False, kwargs={"autocommit": True}) for no in config.NOS}
cliente_parceiro = httpx.AsyncClient(base_url=config.BANCO_PARCEIRO_URL, verify=config.contexto_tls_cliente(),
                                     timeout=httpx.Timeout(5, connect=3))

# Estado em memoria. So e usado pela thread do ciclo de eventos asyncio, por isso nao precisa de lock.
em_curso: set[uuid.UUID] = set()       # transferencias a ser processadas por um pedido neste momento
pausas: dict[str, float] = {}          # pontos de pausa do laboratorio (uma vez cada)
a_confirmar: set[uuid.UUID] = set()    # confirmacoes ao banco parceiro em curso (evita envios duplicados)
_tarefas: set[asyncio.Task] = set()


class ErroNegocio(Exception):
    def __init__(self, codigo: str, mensagem: str):
        super().__init__(mensagem)
        self.codigo, self.mensagem = codigo, mensagem


@dataclass
class Falha:
    no: str
    codigo: str
    mensagem: str


def gid_de(tid, no: str) -> str:
    return f"gs-{tid}-{no}"


def hash_pedido(m: dict) -> str:
    """Resumo dos dados que definem o pedido. Mesma chave com outro resumo = reutilizacao indevida."""
    dados = {c: m[c] for c in ("utilizador", "conta_origem", "conta_destino", "montante_centimos", "moeda")}
    return hashlib.sha256(json.dumps(dados, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def plano(t: dict) -> dict[str, list[tuple[str, str, str]]]:
    """Que operacao fazer em cada no: {no: [(tipo, conta, contraparte)]}."""
    ops: dict[str, list] = {}
    ops.setdefault(config.no_da_conta(t["conta_origem"]), []).append(("DEBITO", t["conta_origem"], t["conta_destino"]))
    ops.setdefault(config.no_da_conta(t["conta_destino"]), []).append(("CREDITO", t["conta_destino"], t["conta_origem"]))
    return ops


# ---------------------------------------------------------------- registo do coordenador
async def evento(tid, nome: str, detalhe: str = "") -> None:
    async with log_bd.connection() as c:
        await c.execute("INSERT INTO eventos (transferencia_id, evento, detalhe) VALUES (%s, %s, %s)",
                        (tid, nome, detalhe))
    registo.registar(str(tid), nome, detalhe or nome)
    log.info("%s %s %s", tid, nome, detalhe)


async def carregar(tid) -> dict | None:
    async with log_bd.connection() as c:
        return await (await c.execute("SELECT * FROM transferencias WHERE id = %s", (tid,))).fetchone()


async def participantes(tid) -> list[dict]:
    async with log_bd.connection() as c:
        return await (await c.execute("SELECT no, gid, estado FROM participantes WHERE transferencia_id = %s "
                                      "ORDER BY no", (tid,))).fetchall()


async def estado_participante(tid, no: str, estado: str) -> None:
    async with log_bd.connection() as c:
        await c.execute("UPDATE participantes SET estado = %s, actualizado_em = now() "
                        "WHERE transferencia_id = %s AND no = %s", (estado, tid, no))


async def registar_ou_obter(m: dict) -> tuple[dict, bool]:
    """Idempotencia: insere a transferencia ou devolve a existente com a mesma chave.

    A restricao UNIQUE (utilizador, chave_idempotencia) e verificada pelo PostgreSQL: dois pedidos
    simultaneos com a mesma chave nunca criam duas transferencias (o segundo espera pelo primeiro).
    """
    tid = uuid.UUID(m["id"])
    async with log_bd.connection() as c:
        async with c.transaction():
            novo = await (await c.execute(
                "INSERT INTO transferencias (id, utilizador, chave_idempotencia, hash_pedido, conta_origem, "
                "conta_destino, montante_centimos, moeda, instancia_api, estado) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'INICIADA') "
                "ON CONFLICT (utilizador, chave_idempotencia) DO NOTHING RETURNING id",
                (tid, m["utilizador"], m["chave_idempotencia"], hash_pedido(m), m["conta_origem"],
                 m["conta_destino"], m["montante_centimos"], m["moeda"], m["instancia"]))).fetchone()
            if novo:
                for no in plano(m):
                    await c.execute("INSERT INTO participantes (transferencia_id, no, gid, estado) "
                                    "VALUES (%s, %s, %s, 'POR_PREPARAR')", (tid, no, gid_de(tid, no)))
                await c.execute("INSERT INTO eventos (transferencia_id, evento, detalhe) VALUES (%s, 'INICIADA', %s)",
                                (tid, f"ordem de {m['instancia']}: {m['conta_origem']} -> {m['conta_destino']}, "
                                      f"{m['montante_centimos']} centimos"))
                em_curso.add(tid)
                existente = None
            else:
                existente = await (await c.execute(
                    "SELECT * FROM transferencias WHERE utilizador = %s AND chave_idempotencia = %s",
                    (m["utilizador"], m["chave_idempotencia"]))).fetchone()
    if existente:
        return existente, False
    registo.registar(str(tid), "INICIADA", "REGISTADA", instancia=m["instancia"], utilizador=m["utilizador"],
                     origem=m["conta_origem"], destino=m["conta_destino"], montante_centimos=m["montante_centimos"])
    return await carregar(tid), True


async def ponto(nome: str, tid) -> None:
    """Ponto de pausa do laboratorio: da tempo para derrubar um servico no momento exacto."""
    segundos = pausas.pop(nome, None)
    if segundos:
        await evento(tid, "PAUSA_LABORATORIO", f"{nome}: {segundos} s")
        await asyncio.sleep(segundos)


# ---------------------------------------------------------------- fase 1: preparacao
async def _operacao(c, t: dict, tipo: str, conta: str, contraparte: str) -> None:
    m = t["montante_centimos"]
    if tipo == "DEBITO":
        # Controlo de concorrencia: o UPDATE bloqueia a linha (FOR UPDATE implicito) e so debita se
        # houver saldo. Se outra transaccao tiver a linha, esta espera e, quando a outra terminar,
        # o PostgreSQL reavalia "saldo_centimos >= m" com o saldo novo. Nunca fica negativo.
        cur = await c.execute(
            "UPDATE contas SET saldo_centimos = saldo_centimos - %s "
            "WHERE id = %s AND titular = %s AND moeda = %s AND saldo_centimos >= %s RETURNING saldo_centimos",
            (m, conta, t["utilizador"], t["moeda"], m))
    else:
        cur = await c.execute(
            "UPDATE contas SET saldo_centimos = saldo_centimos + %s WHERE id = %s AND moeda = %s "
            "RETURNING saldo_centimos", (m, conta, t["moeda"]))
    linha = await cur.fetchone()
    if linha is None:
        info = await (await c.execute("SELECT titular, moeda, saldo_centimos FROM contas WHERE id = %s",
                                      (conta,))).fetchone()
        if info is None:
            raise ErroNegocio("CONTA_INEXISTENTE", f"a conta {conta} nao existe")
        if tipo == "DEBITO" and info[0] != t["utilizador"]:
            raise ErroNegocio("SEM_AUTORIZACAO", f"a conta {conta} nao pertence a {t['utilizador']}")
        if info[1] != t["moeda"]:
            raise ErroNegocio("MOEDA_DIFERENTE", f"a conta {conta} esta em {info[1]}")
        raise ErroNegocio("SALDO_INSUFICIENTE", f"saldo insuficiente em {conta}")
    await c.execute("INSERT INTO movimentos (transferencia_id, conta_id, tipo, montante_centimos, "
                    "saldo_apos_centimos, contraparte) VALUES (%s, %s, %s, %s, %s, %s)",
                    (t["id"], conta, tipo, m, linha[0], contraparte))


async def preparar(no: str, t: dict, operacoes: list) -> Falha | None:
    gid = gid_de(t["id"], no)
    await ponto(f"antes_preparar_{no}", t["id"])
    enviado = False                      # True a partir do momento em que o PREPARE foi enviado
    try:
        async with asyncio.timeout(TIMEOUT_PREPARAR_S):
            async with pools_preparar[no].connection() as c:
                await c.execute("BEGIN")
                try:
                    await c.execute(sql.SQL("SET LOCAL lock_timeout = {}").format(sql.Literal(LOCK_TIMEOUT)))
                    for tipo, conta, contraparte in sorted(operacoes, key=lambda o: o[1]):   # ordem fixa
                        await _operacao(c, t, tipo, conta, contraparte)
                    enviado = True
                    await c.execute(sql.SQL("PREPARE TRANSACTION {}").format(sql.Literal(gid)))
                except Exception:
                    # Antes do PREPARE a transaccao e local e normal: desfaz-se ja.
                    # (Se a ligacao caiu, o PostgreSQL desfaz sozinho uma transaccao nao preparada.)
                    if not enviado and not c.broken:
                        await c.execute("ROLLBACK")
                    raise
    except ErroNegocio as e:
        await estado_participante(t["id"], no, "NAO_PREPARADO")
        await evento(t["id"], "VOTO_NAO", f"{no}: {e.codigo} ({e.mensagem})")
        return Falha(no, e.codigo, e.mensagem)
    except (psycopg.errors.LockNotAvailable, psycopg.errors.DeadlockDetected):
        await estado_participante(t["id"], no, "NAO_PREPARADO")
        await evento(t["id"], "VOTO_NAO", f"{no}: conta bloqueada por outra transaccao")
        return Falha(no, "CONFLITO_BLOQUEIO", "a conta esta bloqueada por outra transaccao; tente de novo")
    except (PoolTimeout, psycopg.OperationalError, TimeoutError) as e:
        # Se o PREPARE ja tinha sido enviado, nao sabemos se o no o executou: estado INCERTO.
        # A decisao sera ABORT e o ROLLBACK PREPARED sera repetido ate o no responder.
        estado = "INCERTO" if enviado else "NAO_PREPARADO"
        await estado_participante(t["id"], no, estado)
        await evento(t["id"], "SEM_RESPOSTA_PREPARACAO", f"{no}: {type(e).__name__} (estado {estado})")
        return Falha(no, "NO_INDISPONIVEL", f"o no {no} nao respondeu durante a preparacao")
    await estado_participante(t["id"], no, "PREPARADO")
    await evento(t["id"], "PREPARADO", f"{no}: PREPARE TRANSACTION '{gid}'")
    return None


# ---------------------------------------------------------------- decisao e fase 2
async def decidir(tid, decisao: str, codigo: str | None = None, motivo: str | None = None) -> str:
    """Grava a decisao global. So a primeira decisao conta (WHERE decisao IS NULL)."""
    estado = "COMMIT_DECIDIDO" if decisao == "COMMIT" else "ABORT_DECIDIDO"
    async with log_bd.connection() as c:
        async with c.transaction():      # o COMMIT desta transaccao torna a decisao duravel
            linha = await (await c.execute(
                "UPDATE transferencias SET decisao = %s, estado = %s, codigo_erro = %s, motivo = %s, "
                "decidida_em = now(), actualizada_em = now() WHERE id = %s AND decisao IS NULL RETURNING id",
                (decisao, estado, codigo, motivo, tid))).fetchone()
            if linha:
                await c.execute("INSERT INTO eventos (transferencia_id, evento, detalhe) VALUES (%s, %s, %s)",
                                (tid, f"DECISAO_{decisao}", motivo or "todos os participantes prepararam"))
    if linha:
        registo.registar(str(tid), f"DECISAO_{decisao}", decisao, codigo=codigo, motivo=motivo)
        return decisao
    return (await carregar(tid))["decisao"]          # ja estava decidida: mantem-se


async def _aplicar_no(tid, decisao: str, p: dict) -> bool:
    """Aplica a decisao num participante. Devolve False se o no nao respondeu (fica pendente)."""
    no, gid = p["no"], p["gid"]
    if p["estado"] in ("CONFIRMADO", "DESFEITO") or (decisao == "ABORT" and p["estado"] in ("NAO_PREPARADO", "POR_PREPARAR")):
        return True                                  # nada a fazer neste no (nunca preparou)
    await ponto(f"antes_{'commit' if decisao == 'COMMIT' else 'rollback'}_{no}", tid)
    try:
        async with asyncio.timeout(TIMEOUT_DECIDIR_S):
            async with pools_decidir[no].connection() as c:
                preparada = await (await c.execute("SELECT 1 FROM pg_prepared_xacts WHERE gid = %s",
                                                   (gid,))).fetchone()
                if preparada:
                    comando = "COMMIT PREPARED {}" if decisao == "COMMIT" else "ROLLBACK PREPARED {}"
                    await c.execute(sql.SQL(comando).format(sql.Literal(gid)))
                elif decisao == "COMMIT":
                    # Ja nao esta preparada: se foi confirmada antes, os movimentos existem.
                    n = (await (await c.execute("SELECT count(*) FROM movimentos WHERE transferencia_id = %s",
                                                (tid,))).fetchone())[0]
                    if n == 0:
                        await evento(tid, "INCONSISTENCIA", f"{no}: {gid} nao esta preparada nem confirmada")
                        return False
    except (PoolTimeout, psycopg.OperationalError, TimeoutError) as e:
        await evento(tid, "DECISAO_PENDENTE", f"{no}: {type(e).__name__}; a decisao {decisao} mantem-se e sera repetida")
        return False
    novo = "CONFIRMADO" if decisao == "COMMIT" else "DESFEITO"
    await estado_participante(tid, no, novo)
    await evento(tid, novo, f"{no}: {'COMMIT' if decisao == 'COMMIT' else 'ROLLBACK'} PREPARED '{gid}'")
    return True


async def aplicar_decisao(tid) -> bool:
    t = await carregar(tid)
    decisao = t["decisao"]
    resultados = await asyncio.gather(*(_aplicar_no(tid, decisao, p) for p in await participantes(tid)))
    if not all(resultados):
        return False
    final = "CONCLUIDA" if decisao == "COMMIT" else "ABORTADA"
    async with log_bd.connection() as c:
        await c.execute("UPDATE transferencias SET estado = %s, concluida_em = now(), actualizada_em = now(), "
                        "parceiro_estado = %s WHERE id = %s AND estado <> %s",
                        (final, "POR_ENVIAR" if final == "CONCLUIDA" else "NAO_APLICAVEL", tid, final))
    await evento(tid, final, "decisao aplicada em todos os participantes")
    if final == "CONCLUIDA":
        tarefa = asyncio.create_task(confirmar_parceiro(tid))
        _tarefas.add(tarefa)
        tarefa.add_done_callback(_tarefas.discard)
    return True


async def executar(t: dict) -> None:
    """Executa o 2PC de uma transferencia acabada de registar."""
    tid = t["id"]
    em_curso.add(tid)
    try:
        ops = plano(t)
        falhas = []
        for no in config.NOS:                    # ordem global fixa: europa, america
            if no in ops:
                falha = await preparar(no, t, ops[no])
                if falha:                        # um voto NAO chega para abortar: nao vale a pena continuar
                    falhas.append(falha)
                    break
        if not falhas:
            async with log_bd.connection() as c:
                await c.execute("UPDATE transferencias SET estado = 'PREPARADA', actualizada_em = now() "
                                "WHERE id = %s", (tid,))
            await ponto("apos_preparar", tid)
            await decidir(tid, "COMMIT")
            await ponto("apos_decisao", tid)
        else:
            await decidir(tid, "ABORT", falhas[0].codigo, falhas[0].mensagem)
        await aplicar_decisao(tid)
    finally:
        em_curso.discard(tid)


# ---------------------------------------------------------------- recuperacao
async def recuperar(arranque: bool = False) -> None:
    async with log_bd.connection() as c:
        por_resolver = await (await c.execute(
            "SELECT id, decisao, actualizada_em FROM transferencias "
            "WHERE estado NOT IN ('CONCLUIDA', 'ABORTADA') ORDER BY criada_em")).fetchall()
    limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=30)
    for t in por_resolver:
        if t["id"] in em_curso:
            continue
        try:
            if t["decisao"] is None:
                if not arranque and t["actualizada_em"] > limite:
                    continue
                await evento(t["id"], "RECUPERACAO", "sem decisao gravada: abort presumido")
                await decidir(t["id"], "ABORT", "RECUPERACAO",
                              "o coordenador reiniciou antes de decidir; nada foi confirmado (abort presumido)")
            elif arranque:
                await evento(t["id"], "RECUPERACAO", f"decisao {t['decisao']} gravada: repetir nos participantes")
            await aplicar_decisao(t["id"])
        except Exception:
            log.exception("recuperacao de %s falhou; sera repetida", t["id"])
    await _orfas()
    await _parceiro_pendentes()


async def _orfas() -> None:
    """Transaccoes preparadas num no sem registo no coordenador: ROLLBACK (abort presumido)."""
    for no, pool in pools_decidir.items():
        try:
            async with pool.connection() as c:
                gids = [g for (g,) in await (await c.execute(
                    "SELECT gid FROM pg_prepared_xacts WHERE gid LIKE 'gs-%'")).fetchall()]
                for gid in gids:
                    tid = uuid.UUID(gid[3:39])
                    if tid not in em_curso and await carregar(tid) is None:
                        await c.execute(sql.SQL("ROLLBACK PREPARED {}").format(sql.Literal(gid)))
                        log.warning("%s: transaccao preparada orfa %s desfeita", no, gid)
        except (PoolTimeout, psycopg.OperationalError, TimeoutError):
            pass                                       # no em baixo: tenta-se no proximo ciclo


async def ciclo_recuperacao() -> None:
    arranque = True
    while True:
        try:
            await recuperar(arranque)
            arranque = False
        except Exception as e:                           # por exemplo, registo do coordenador em baixo
            log.warning("recuperacao adiada: %s", e)
        await asyncio.sleep(INTERVALO_RECUPERACAO_S)


# ---------------------------------------------------------------- banco parceiro (Java)
async def confirmar_parceiro(tid) -> None:
    """Envia a confirmacao da transferencia concluida ao banco parceiro (XML sobre HTTPS).

    O dinheiro ja esta movido; se o parceiro estiver em baixo, a confirmacao fica POR_ENVIAR e
    e repetida pelo ciclo de recuperacao. O Java e idempotente: o mesmo id da a mesma referencia.
    """
    if tid in a_confirmar:
        return
    t = await carregar(tid)
    if t is None or t["parceiro_estado"] != "POR_ENVIAR":
        return
    a_confirmar.add(tid)
    try:
        r = await cliente_parceiro.post("/legado/confirmacoes", content=contrato_parceiro.pedido_confirmacao(t),
                                        headers={"Content-Type": "application/xml"})
        dados = contrato_parceiro.ler_registo(r.content, str(tid))
    except httpx.TransportError as e:
        log.warning("banco parceiro indisponivel (%s); confirmacao de %s fica por enviar", type(e).__name__, tid)
        return
    except contrato_parceiro.ErroContrato as e:
        await evento(tid, "PARCEIRO_ERRO", str(e))
        return
    finally:
        a_confirmar.discard(tid)
    async with log_bd.connection() as c:
        await c.execute("UPDATE transferencias SET parceiro_estado = 'CONFIRMADA', parceiro_referencia = %s, "
                        "actualizada_em = now() WHERE id = %s", (dados["referenciaParceiro"], tid))
    await evento(tid, "PARCEIRO_CONFIRMOU", f"referencia {dados['referenciaParceiro']} (HTTP {r.status_code})")


async def _parceiro_pendentes() -> None:
    async with log_bd.connection() as c:
        ids = [l["id"] for l in await (await c.execute(
            "SELECT id FROM transferencias WHERE parceiro_estado = 'POR_ENVIAR' ORDER BY concluida_em LIMIT 20")).fetchall()]
    for tid in ids:
        await confirmar_parceiro(tid)
