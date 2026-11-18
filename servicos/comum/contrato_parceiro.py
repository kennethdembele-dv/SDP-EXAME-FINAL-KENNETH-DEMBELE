"""Contrato XML com o banco parceiro (modulo legado em Java).

Pedido (Python -> Java), POST /legado/confirmacoes:
    <confirmacaoTransferencia versao="1">
      <id>UUID</id><contaOrigem>EU-1001</contaOrigem><contaDestino>US-2001</contaDestino>
      <montanteCentimos>12550</montanteCentimos><moeda>EUR</moeda>
      <concluidaEm>2026-11-19T10:00:00.000Z</concluidaEm>
    </confirmacaoTransferencia>

Resposta (Java -> Python), 201 (novo) ou 200 (repetido), e tambem em GET /legado/transferencias/{id}:
    <registoParceiro versao="1">
      <id>UUID</id><referenciaParceiro>BP-000001</referenciaParceiro><estado>REGISTADA</estado>
      ...os campos do pedido...<recebidaEm>...</recebidaEm>
    </registoParceiro>

Erro: <erro><codigo>DADOS_INVALIDOS</codigo><mensagem>...</mensagem></erro>   (HTTP 400/404)
O esquema formal esta em banco-parceiro/contrato.xsd.
"""
import re
import xml.etree.ElementTree as ET

CAMPOS_PEDIDO = ("id", "contaOrigem", "contaDestino", "montanteCentimos", "moeda", "concluidaEm")
REGRAS = {
    "id": re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
    "contaOrigem": re.compile(r"^(EU|US)-\d{4}$"),
    "contaDestino": re.compile(r"^(EU|US)-\d{4}$"),
    "montanteCentimos": re.compile(r"^[1-9]\d{0,14}$"),
    "moeda": re.compile(r"^[A-Z]{3}$"),
    "referenciaParceiro": re.compile(r"^BP-\d{6}$"),
}


class ErroContrato(Exception):
    """Resposta que nao cumpre o contrato (ou erro devolvido pelo parceiro)."""


def pedido_confirmacao(t: dict) -> bytes:
    raiz = ET.Element("confirmacaoTransferencia", versao="1")
    valores = {"id": str(t["id"]), "contaOrigem": t["conta_origem"], "contaDestino": t["conta_destino"],
               "montanteCentimos": str(t["montante_centimos"]), "moeda": t["moeda"],
               "concluidaEm": t["concluida_em"].isoformat(timespec="milliseconds").replace("+00:00", "Z")}
    for campo in CAMPOS_PEDIDO:
        ET.SubElement(raiz, campo).text = valores[campo]
    return ET.tostring(raiz, encoding="utf-8", xml_declaration=True)


def ler_registo(xml: bytes, id_esperado: str | None = None) -> dict:
    """Valida a resposta do Java e devolve-a como dicionario."""
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:      # recusa DTD/entidades (ataques XXE)
        raise ErroContrato("a resposta contem DTD; recusada")
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError as e:
        raise ErroContrato(f"XML mal formado: {e}") from None
    if raiz.tag == "erro":
        raise ErroContrato(f"{raiz.findtext('codigo')}: {raiz.findtext('mensagem')}")
    if raiz.tag != "registoParceiro":
        raise ErroContrato(f"elemento raiz inesperado: <{raiz.tag}>")
    dados = {filho.tag: (filho.text or "") for filho in raiz}
    for campo in ("id", "referenciaParceiro", "estado", "montanteCentimos"):
        if campo not in dados:
            raise ErroContrato(f"falta <{campo}> na resposta")
    for campo, regra in REGRAS.items():
        if campo in dados and not regra.match(dados[campo]):
            raise ErroContrato(f"<{campo}> com formato invalido: {dados[campo]!r}")
    if id_esperado and dados["id"] != str(id_esperado):
        raise ErroContrato("a resposta refere-se a outra transferencia")
    return dados
