"""Auditoria no sistema de ficheiros distribuido (NFS montado em /mnt/dfs).

Estrategia de acesso concorrente: UM FICHEIRO POR EVENTO. O nome junta data UTC, transferencia,
servico, evento e um sufixo aleatorio, por isso dois servicos (ou duas threads) nunca escrevem no
mesmo ficheiro e nao e preciso nenhum bloqueio distribuido. Cada ficheiro e escrito com um nome
temporario e depois renomeado: quem le ve o ficheiro completo ou nao o ve.

Tolerancia a falhas: o evento e primeiro gravado no disco local do servico (pasta de espera, num
volume persistente) e so depois uma thread o publica no DFS. Se o NFS estiver em baixo, os eventos
ficam na pasta de espera e sao publicados quando ele voltar; nenhum evento financeiro se perde e
as transferencias nao ficam a espera do NFS.
"""
import datetime as dt
import json
import logging
import os
import threading
import uuid
from pathlib import Path

from comum import config

log = logging.getLogger("auditoria")


def _escrever_atomico(destino: Path, conteudo: bytes) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(f".{destino.name}.tmp")
    with open(temporario, "wb") as f:
        f.write(conteudo)
        f.flush()
        os.fsync(f.fileno())            # garante que os dados chegaram ao disco (ou ao servidor NFS)
    os.replace(temporario, destino)     # renomear e atomico dentro da mesma pasta


class Auditoria:
    def __init__(self, servico: str, dfs: Path = config.DFS, espera: Path = config.SPOOL):
        self.servico = servico
        self.dfs = dfs
        self.espera = espera
        self.espera.mkdir(parents=True, exist_ok=True)
        self._acordar = threading.Event()
        threading.Thread(target=self._publicar_continuamente, name="publicador-dfs", daemon=True).start()

    def registar(self, transferencia_id: str, evento: str, resultado: str, **detalhe) -> str:
        agora = dt.datetime.now(dt.timezone.utc)
        doc = {"transferencia_id": str(transferencia_id), "data_utc": agora.isoformat(timespec="milliseconds"),
               "servico": self.servico, "evento": evento, "resultado": resultado, "detalhe": detalhe}
        nome = f"{agora:%Y%m%dT%H%M%S%f}Z_{transferencia_id}_{self.servico}_{evento}_{uuid.uuid4().hex[:6]}.json"
        _escrever_atomico(self.espera / nome, json.dumps(doc, ensure_ascii=False, indent=1).encode())
        self._acordar.set()
        return nome

    def pendentes(self) -> int:
        return sum(1 for _ in self.espera.glob("*.json"))

    def _publicar_continuamente(self) -> None:
        while True:
            self._acordar.wait(timeout=5)
            self._acordar.clear()
            try:
                self.publicar_pendentes()
            except Exception:                         # nunca deixar a thread morrer
                log.exception("erro inesperado a publicar a auditoria")

    def publicar_pendentes(self) -> int:
        publicados = 0
        for ficheiro in sorted(self.espera.glob("*.json")):
            dia = f"{ficheiro.name[0:4]}-{ficheiro.name[4:6]}-{ficheiro.name[6:8]}"
            try:
                _escrever_atomico(self.dfs / "auditoria" / dia / ficheiro.name, ficheiro.read_bytes())
            except OSError as e:
                log.warning("DFS indisponivel (%s); %d evento(s) ficam na pasta de espera", e, self.pendentes())
                return publicados
            ficheiro.unlink()
            publicados += 1
        return publicados


def ler_eventos(transferencia_id: str, dfs: Path = config.DFS) -> list[dict]:
    """Le do DFS todos os eventos de uma transferencia, escritos por qualquer servico."""
    eventos = []
    for f in (dfs / "auditoria").glob(f"*/*_{transferencia_id}_*.json"):
        eventos.append(json.loads(f.read_text(encoding="utf-8")) | {"ficheiro": f"{f.parent.name}/{f.name}"})
    return sorted(eventos, key=lambda e: e["data_utc"])
