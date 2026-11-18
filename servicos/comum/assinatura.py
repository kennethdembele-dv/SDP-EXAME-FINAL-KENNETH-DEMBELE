"""Assinatura digital das ordens de transferencia (API -> coordenador).

1. Representacao deterministica: os campos relevantes em JSON canonico (chaves ordenadas,
   sem espacos, UTF-8). Os mesmos dados produzem sempre os mesmos bytes.
2. SHA-256 resume esses bytes num valor de 32 bytes; qualquer alteracao (por exemplo no
   montante) produz um resumo completamente diferente.
3. RSA-PSS assina o resumo com a chave PRIVADA da instancia da API. O coordenador verifica com
   a chave PUBLICA: so quem tem a privada consegue produzir uma assinatura valida (autenticidade)
   e a verificacao falha se um unico byte mudar (integridade).
"""
import base64
import datetime as dt
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# Campos protegidos. emitido_em e o id limitam a repeticao (replay) de mensagens antigas.
CAMPOS = ("id", "chave_idempotencia", "utilizador", "conta_origem", "conta_destino",
          "montante_centimos", "moeda", "emitido_em", "instancia")
JANELA_S = 120          # idade maxima aceite de uma mensagem assinada
_PSS = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH)


class AssinaturaInvalida(Exception):
    pass


def canonico(mensagem: dict) -> bytes:
    em_falta = [c for c in CAMPOS if c not in mensagem]
    if em_falta:
        raise AssinaturaInvalida(f"campos em falta: {', '.join(em_falta)}")
    return json.dumps({c: mensagem[c] for c in CAMPOS}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def resumo_sha256(mensagem: dict) -> str:
    """So para mostrar nas evidencias: o resumo que a assinatura protege."""
    d = hashes.Hash(hashes.SHA256())
    d.update(canonico(mensagem))
    return d.finalize().hex()


def assinar(mensagem: dict, chave_privada_pem: bytes) -> str:
    chave = serialization.load_pem_private_key(chave_privada_pem, password=None)
    return base64.b64encode(chave.sign(canonico(mensagem), _PSS, hashes.SHA256())).decode()


def verificar(mensagem: dict, assinatura_b64: str, chave_publica_pem: bytes) -> None:
    chave = serialization.load_pem_public_key(chave_publica_pem)
    try:
        chave.verify(base64.b64decode(assinatura_b64), canonico(mensagem), _PSS, hashes.SHA256())
    except (InvalidSignature, ValueError):
        raise AssinaturaInvalida("assinatura invalida: a mensagem foi alterada ou nao foi assinada por uma API conhecida") from None


def verificar_janela(mensagem: dict, agora: dt.datetime | None = None) -> None:
    agora = agora or dt.datetime.now(dt.timezone.utc)
    try:
        emitido = dt.datetime.fromisoformat(mensagem["emitido_em"])
    except (KeyError, ValueError):
        raise AssinaturaInvalida("emitido_em invalido") from None
    if abs((agora - emitido).total_seconds()) > JANELA_S:
        raise AssinaturaInvalida(f"mensagem fora da janela de {JANELA_S} s (possivel repeticao)")


def agora_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
