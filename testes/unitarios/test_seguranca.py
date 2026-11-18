"""Testes sem Docker: dinheiro, assinatura das ordens, JWT, palavras-passe e contrato XML."""
import datetime as dt
import time

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from comum import assinatura, config, contrato_parceiro, dinheiro, palavras_passe, tokens

PRIV_API1 = config.ler_segredo("assinatura-api-1.pem")
PUB_API1 = config.ler_segredo("assinatura-api-1.pub.pem")
PUB_API2 = config.ler_segredo("assinatura-api-2.pub.pem")
JWT_PRIV = config.ler_segredo("jwt-privada.pem")
JWT_PUB = config.ler_segredo("jwt-publica.pem")


def ordem(**alteracoes):
    m = {"id": "0b9d6f7e-1c2a-4d8e-9f00-123456789abc", "chave_idempotencia": "teste-0001", "utilizador": "ana",
         "conta_origem": "EU-1001", "conta_destino": "US-2001", "montante_centimos": 12550, "moeda": "EUR",
         "emitido_em": assinatura.agora_utc(), "instancia": "api-1"}
    return m | alteracoes


# ------------------------------------------------------------ dinheiro
@pytest.mark.parametrize("texto,centimos", [("125.50", 12550), ("0.01", 1), ("10", 1000), (" 7.5 ", 750)])
def test_montantes_validos(texto, centimos):
    assert dinheiro.para_centimos(texto) == centimos


@pytest.mark.parametrize("texto", ["0", "-5", "1.001", "abc", "NaN", "Infinity", "", "1e999"])
def test_montantes_invalidos(texto):
    with pytest.raises(dinheiro.MontanteInvalido):
        dinheiro.para_centimos(texto)


def test_float_recusado():
    with pytest.raises(dinheiro.MontanteInvalido):
        dinheiro.para_centimos(0.1)


def test_formatar():
    assert dinheiro.formatar(12550) == "125.50" and dinheiro.formatar(5) == "0.05"


# ------------------------------------------------------------ assinatura das ordens
def test_assinatura_valida():
    m = ordem()
    assinatura.verificar(m, assinatura.assinar(m, PRIV_API1), PUB_API1)


def test_montante_adulterado_e_recusado():
    m = ordem()
    s = assinatura.assinar(m, PRIV_API1)
    m["montante_centimos"] = 999999
    with pytest.raises(assinatura.AssinaturaInvalida):
        assinatura.verificar(m, s, PUB_API1)


def test_chave_de_outra_instancia_e_recusada():
    m = ordem()
    with pytest.raises(assinatura.AssinaturaInvalida):
        assinatura.verificar(m, assinatura.assinar(m, PRIV_API1), PUB_API2)


def test_representacao_canonica_nao_depende_da_ordem_dos_campos():
    m = ordem()
    invertida = dict(reversed(list(m.items())))
    assert assinatura.canonico(m) == assinatura.canonico(invertida)
    assert assinatura.resumo_sha256(m) == assinatura.resumo_sha256(invertida)


def test_mensagem_antiga_fora_da_janela():
    antiga = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)).isoformat()
    with pytest.raises(assinatura.AssinaturaInvalida):
        assinatura.verificar_janela(ordem(emitido_em=antiga))


# ------------------------------------------------------------ JWT
def test_token_valido():
    u = tokens.validar(tokens.emitir(JWT_PRIV, "ana", "Ana Silva", "EU"), JWT_PUB)
    assert (u.id, u.regiao) == ("ana", "EU")


def test_token_expirado():
    with pytest.raises(HTTPException, match="expirado"):
        tokens.validar(tokens.emitir(JWT_PRIV, "ana", "Ana", "EU", validade_s=-60), JWT_PUB)


def test_token_assinado_por_outra_chave():
    outra = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    with pytest.raises(HTTPException, match="assinatura"):
        tokens.validar(tokens.emitir(outra, "ana", "Ana", "EU"), JWT_PUB)


def test_token_para_outro_destinatario():
    agora = int(time.time())
    t = pyjwt.encode({"iss": config.JWT_EMISSOR, "aud": "outro-sistema", "sub": "ana", "iat": agora,
                      "exp": agora + 60}, JWT_PRIV, algorithm="RS256")
    with pytest.raises(HTTPException, match="destinatario"):
        tokens.validar(t, JWT_PUB)


def test_algoritmo_none_recusado():
    agora = int(time.time())
    t = pyjwt.encode({"iss": config.JWT_EMISSOR, "aud": config.JWT_AUDIENCIA, "sub": "ana", "iat": agora,
                      "exp": agora + 60}, None, algorithm="none")
    with pytest.raises(HTTPException):
        tokens.validar(t, JWT_PUB)


# ------------------------------------------------------------ palavras-passe
def test_scrypt():
    h = palavras_passe.gerar_hash("Ana#2026")
    assert h.startswith("scrypt$") and palavras_passe.verificar("Ana#2026", h)
    assert not palavras_passe.verificar("errada", h)


# ------------------------------------------------------------ contrato XML
def test_pedido_xml_e_leitura_da_resposta():
    t = {"id": "0b9d6f7e-1c2a-4d8e-9f00-123456789abc", "conta_origem": "EU-1001", "conta_destino": "US-2001",
         "montante_centimos": 12550, "moeda": "EUR", "concluida_em": dt.datetime.now(dt.timezone.utc)}
    xml = contrato_parceiro.pedido_confirmacao(t)
    assert b"<montanteCentimos>12550</montanteCentimos>" in xml
    resposta = (b'<registoParceiro versao="1"><id>0b9d6f7e-1c2a-4d8e-9f00-123456789abc</id>'
                b'<referenciaParceiro>BP-000001</referenciaParceiro><estado>REGISTADA</estado>'
                b'<montanteCentimos>12550</montanteCentimos></registoParceiro>')
    assert contrato_parceiro.ler_registo(resposta, t["id"])["referenciaParceiro"] == "BP-000001"


@pytest.mark.parametrize("xml", [
    b"<?xml version='1.0'?><!DOCTYPE x [<!ENTITY a 'b'>]><registoParceiro/>",
    b"<registoParceiro><id>x</id></registoParceiro>",
    b"<erro><codigo>DADOS_INVALIDOS</codigo><mensagem>m</mensagem></erro>",
    b"isto nao e xml",
])
def test_respostas_xml_recusadas(xml):
    with pytest.raises(contrato_parceiro.ErroContrato):
        contrato_parceiro.ler_registo(xml)
