#!/usr/bin/env python3
"""Gera o relatorio tecnico em Word (docs/Relatorio_Tecnico_Global-Scale.docx).

    python docs/relatorio/gerar_relatorio.py
    powershell -ExecutionPolicy Bypass -File docs/relatorio/exportar_pdf.ps1

As evidencias de evidencias/*.json (gravadas por testes/cenarios.py) e as capturas de ecra reais de
docs/relatorio/capturas/ (feitas por capturar_ecra.py) entram automaticamente.
"""
import datetime as dt
import html
import json
import os
import pathlib
import re
import subprocess
import sys
import time

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from word import (AZUL, caixa, campo, codigo, configurar_estilos, contorno_primeira_pagina,  # noqa: E402
                  figura, par, tabela, topicos)

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
EVID = pathlib.Path(os.environ.get("GS_EVIDENCIAS", RAIZ / "evidencias"))
CONSTRUIR = RAIZ / "docs" / "relatorio" / ".construir"
EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
DATA = "19 de Novembro de 2026"


# ------------------------------------------------------------------ imagens (SVG e capturas -> PNG)
def png_de_html(conteudo_html: str, nome: str, largura: int, altura: int) -> str:
    CONSTRUIR.mkdir(parents=True, exist_ok=True)
    pagina = CONSTRUIR / f"{nome}.html"
    pagina.write_text(conteudo_html, encoding="utf8")
    png = CONSTRUIR / f"{nome}.png"
    if png.exists():
        png.unlink()
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                    "--user-data-dir=" + str(CONSTRUIR / "edge"), f"--window-size={largura},{altura}",
                    "--screenshot=" + str(png), pagina.resolve().as_uri()], capture_output=True, timeout=120)
    for _ in range(120):           # o Edge pode devolver o controlo antes de acabar de escrever
        if png.exists() and png.stat().st_size > 0:
            time.sleep(0.4)
            break
        time.sleep(0.25)
    return str(png)


def png_de_svg(svg: str, nome: str, largura=1800) -> str:
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    altura = int(largura * vb[3] / vb[2])
    svg = svg.replace("<svg ", f'<svg width="{largura}" height="{altura}" ', 1)
    return png_de_html("<html><head><style>text{font-family:Calibri,'Segoe UI',sans-serif}</style></head>"
                       f"<body style='margin:0;background:#fff;overflow:hidden'>{svg}</body></html>",
                       nome, largura, altura)


# ------------------------------------------------------------------ diagramas
SVG_ARQ = """<svg viewBox="0 0 960 600" xmlns="http://www.w3.org/2000/svg">
<defs><marker id="s" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#333"/></marker>
<style>.c{font-size:13.5px;font-weight:700}.t{font-size:11px}.p{font-size:10.5px;fill:#7a1f1f;font-weight:700}.l{stroke:#333;stroke-width:1.4;fill:none;marker-end:url(#s)}.g{font-size:11.5px;font-weight:700;fill:#173b6c}</style></defs>
<rect x="5" y="70" width="950" height="160" rx="10" fill="#f4f8fd" stroke="#173b6c" stroke-dasharray="6 4"/>
<text x="16" y="88" class="g">rede frontal 172.30.1.0/24</text>
<rect x="5" y="240" width="950" height="355" rx="10" fill="#f7faf7" stroke="#17803d" stroke-dasharray="6 4"/>
<text x="16" y="258" class="g" fill="#17803d">rede interna 172.30.2.0/24 (DNS interno do Docker)</text>
<rect x="380" y="8" width="200" height="46" rx="6" fill="#fff" stroke="#555"/><text x="480" y="28" text-anchor="middle" class="c">Cliente</text><text x="480" y="44" text-anchor="middle" class="t">cliente.py, Swagger, curl</text>
<rect x="40" y="110" width="210" height="64" rx="6" fill="#fff6e3" stroke="#d9971e"/><text x="145" y="132" text-anchor="middle" class="c">auth (Python)</text><text x="145" y="148" text-anchor="middle" class="t">emite JWT RS256 (chave privada)</text><text x="145" y="164" text-anchor="middle" class="p">HTTPS :8000</text>
<rect x="330" y="110" width="200" height="64" rx="6" fill="#e8f0fb" stroke="#173b6c"/><text x="430" y="132" text-anchor="middle" class="c">api-1 (Python)</text><text x="430" y="148" text-anchor="middle" class="t">valida JWT, assina a ordem</text><text x="430" y="164" text-anchor="middle" class="p">HTTPS :8001</text>
<rect x="600" y="110" width="200" height="64" rx="6" fill="#e8f0fb" stroke="#173b6c"/><text x="700" y="132" text-anchor="middle" class="c">api-2 (Python)</text><text x="700" y="148" text-anchor="middle" class="t">mesma imagem, outra chave</text><text x="700" y="164" text-anchor="middle" class="p">HTTPS :8002</text>
<rect x="420" y="290" width="230" height="70" rx="6" fill="#f3faf6" stroke="#17803d"/><text x="535" y="312" text-anchor="middle" class="c">coordenador 2PC (Python)</text><text x="535" y="328" text-anchor="middle" class="t">asyncio, recuperação, idempotência</text><text x="535" y="346" text-anchor="middle" class="p">HTTPS :8100</text>
<rect x="760" y="290" width="180" height="70" rx="6" fill="#fdf0f0" stroke="#b3261e"/><text x="850" y="312" text-anchor="middle" class="c">banco-parceiro</text><text x="850" y="328" text-anchor="middle" class="t">Java 21, XML (legado)</text><text x="850" y="346" text-anchor="middle" class="p">HTTPS :8200</text>
<rect x="30" y="440" width="190" height="70" rx="6" fill="#e9eefb" stroke="#173b6c"/><text x="125" y="462" text-anchor="middle" class="c">db-europa</text><text x="125" y="478" text-anchor="middle" class="t">fragmento EU-xxxx</text><text x="125" y="496" text-anchor="middle" class="p">PostgreSQL 17 TLS :5433</text>
<rect x="260" y="440" width="190" height="70" rx="6" fill="#e9eefb" stroke="#173b6c"/><text x="355" y="462" text-anchor="middle" class="c">db-america</text><text x="355" y="478" text-anchor="middle" class="t">fragmento US-xxxx</text><text x="355" y="496" text-anchor="middle" class="p">PostgreSQL 17 TLS :5434</text>
<rect x="490" y="440" width="190" height="70" rx="6" fill="#e9eefb" stroke="#173b6c"/><text x="585" y="462" text-anchor="middle" class="c">db-coordenador</text><text x="585" y="478" text-anchor="middle" class="t">decisões 2PC (duráveis)</text><text x="585" y="496" text-anchor="middle" class="p">PostgreSQL 17 TLS :5435</text>
<rect x="740" y="440" width="190" height="70" rx="6" fill="#fff6e3" stroke="#d9971e"/><text x="835" y="462" text-anchor="middle" class="c">nfs (NFS-Ganesha)</text><text x="835" y="478" text-anchor="middle" class="t">auditoria/, relatorios/</text><text x="835" y="496" text-anchor="middle" class="p">NFSv4 :2049</text>
<path class="l" d="M440,54 L170,106"/><text x="250" y="64" class="t">1. login (HTTPS)</text>
<path class="l" d="M470,54 L440,106"/><text x="462" y="86" class="t">2. JWT</text>
<path class="l" d="M500,54 L680,106" stroke-dasharray="5 3"/><text x="610" y="64" class="t">failover</text>
<path class="l" d="M430,174 L500,286"/><path class="l" d="M700,174 L580,286"/><rect x="596" y="264" width="236" height="16" fill="#f7faf7"/><text x="600" y="276" class="t">ordem assinada (RSA-PSS/SHA-256) + JWT</text>
<path class="l" d="M470,360 L160,436"/><path class="l" d="M500,360 L370,436"/><rect x="226" y="396" width="200" height="16" fill="#f7faf7"/><text x="230" y="408" class="t">PREPARE / COMMIT PREPARED (TLS)</text>
<path class="l" d="M560,360 L580,436"/><text x="582" y="404" class="t">decisão</text>
<path class="l" d="M650,325 L756,325"/><text x="664" y="318" class="t">XML</text>
<path class="l" d="M620,360 C700,400 760,420 800,436"/><path class="l" d="M800,174 C900,250 900,380 880,436"/><text x="905" y="285" class="t">NFS</text>
<path class="l" d="M140,174 L130,436" stroke-dasharray="3 3"/><text x="40" y="320" class="t">leitura (TLS)</text>
<path class="l" d="M380,174 L180,436" stroke-dasharray="3 3"/><path class="l" d="M450,174 L360,436" stroke-dasharray="3 3"/>
<text x="20" y="540" class="t">Linhas tracejadas finas: leituras (utilizadores, saldos, histórico) com o papel gs_leitura. Todas as ligações usam TLS;</text>
<text x="20" y="556" class="t">o PostgreSQL recusa ligações sem TLS (hostnossl ... reject) e os clientes verificam a CA e o nome do servidor (verify-full).</text>
<text x="20" y="580" class="t">Dois computadores: PC A = auth, api-1, coordenador, db-europa, db-coordenador, nfs; PC B = db-america, api-2, banco-parceiro.</text>
</svg>"""

SVG_2PC = """<svg viewBox="0 0 900 420" xmlns="http://www.w3.org/2000/svg">
<defs><marker id="m" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#333"/></marker>
<style>.h{font-size:12.5px;font-weight:700}.t{font-size:11px}.l{stroke:#333;stroke-width:1.3;fill:none;marker-end:url(#m)}.v{stroke:#17803d;stroke-width:1.3;fill:none;marker-end:url(#m)}</style></defs>
<g text-anchor="middle" class="h"><text x="90" y="18">api-1</text><text x="300" y="18">coordenador</text><text x="470" y="18">db-coordenador</text><text x="640" y="18">db-europa</text><text x="810" y="18">db-america</text></g>
<g stroke="#aaa"><path d="M90,26 V415"/><path d="M300,26 V415"/><path d="M470,26 V415"/><path d="M640,26 V415"/><path d="M810,26 V415"/></g>
<path class="l" d="M90,44 H296"/><text x="195" y="39" text-anchor="middle" class="t">ordem assinada + JWT</text>
<rect x="215" y="52" width="170" height="20" fill="#eef3fa" stroke="#173b6c"/><text x="300" y="66" text-anchor="middle" class="t">verifica assinatura e token</text>
<path class="l" d="M300,86 H466"/><text x="385" y="81" text-anchor="middle" class="t">INSERT INICIADA (chave UNIQUE)</text>
<text x="20" y="108" class="h" fill="#173b6c">Fase 1</text>
<path class="l" d="M300,118 H636"/><text x="470" y="113" text-anchor="middle" class="t">BEGIN; UPDATE débito (saldo ≥ m); INSERT movimento; PREPARE TRANSACTION</text>
<path class="v" d="M636,138 H304"/><text x="470" y="133" text-anchor="middle" class="t" fill="#17803d">voto SIM (ou NÃO → ABORT)</text>
<path class="l" d="M300,160 H806"/><text x="555" y="155" text-anchor="middle" class="t">BEGIN; UPDATE crédito; INSERT movimento; PREPARE TRANSACTION</text>
<path class="v" d="M806,180 H304"/><text x="555" y="175" text-anchor="middle" class="t" fill="#17803d">voto SIM</text>
<text x="20" y="214" class="h" fill="#b3261e">Decisão</text>
<path class="l" d="M300,210 H466"/><text x="385" y="205" text-anchor="middle" class="t">UPDATE decisao = COMMIT</text>
<rect x="390" y="218" width="160" height="34" fill="#fdf0f0" stroke="#b3261e"/><text x="470" y="232" text-anchor="middle" class="t">COMMIT local (fsync do WAL)</text><text x="470" y="246" text-anchor="middle" class="t">a partir daqui não muda</text>
<text x="20" y="280" class="h" fill="#173b6c">Fase 2</text>
<path class="l" d="M300,276 H636"/><text x="470" y="271" text-anchor="middle" class="t">COMMIT PREPARED 'gs-id-europa'</text>
<path class="l" d="M300,296 H806"/><text x="555" y="291" text-anchor="middle" class="t">COMMIT PREPARED 'gs-id-america' (em paralelo)</text>
<path class="l" d="M300,326 H466"/><text x="385" y="321" text-anchor="middle" class="t">estado CONCLUIDA</text>
<path class="l" d="M296,346 H94"/><text x="195" y="341" text-anchor="middle" class="t">201 CONCLUIDA</text>
<text x="310" y="378" class="t">Se um nó não responder na fase 2: estado COMMIT_DECIDIDO (HTTP 202) e a recuperação repete o COMMIT PREPARED</text>
<text x="310" y="394" class="t">a cada 5 s. Se o coordenador cair antes da decisão: abort presumido no arranque (ROLLBACK PREPARED).</text>
</svg>"""


# ------------------------------------------------------------------ evidencias
def carregar_evidencias() -> dict[int, dict]:
    res = {}
    for f in sorted(EVID.glob("[0-9]*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf8"))
            res[d["cenario"]] = d | {"ficheiro": f.stem}
        except (ValueError, KeyError):
            pass
    return res


# ------------------------------------------------------------------ capa
def capa(doc, logo):
    def linha(texto="", tamanho=11, negrito=False, alinhar=WD_ALIGN_PARAGRAPH.LEFT, antes=0, depois=6):
        p = doc.add_paragraph()
        p.alignment = alinhar
        p.paragraph_format.space_before = Pt(antes)
        p.paragraph_format.space_after = Pt(depois)
        if texto:
            r = p.add_run(texto)
            r.font.size = Pt(tamanho)
            r.bold = negrito
        return p

    p = linha(alinhar=WD_ALIGN_PARAGRAPH.CENTER, antes=30, depois=14)
    p.add_run().add_picture(logo, width=Cm(5.2))
    linha("INSTITUTO SUPERIOR DE TRANSPORTES E COMUNICAÇÕES", 14, True, WD_ALIGN_PARAGRAPH.CENTER, depois=14)
    tema = linha("Tema: Exame Normal Prático Laboratorial — Global-Scale System: Plataforma de Transacções "
                 "Financeiras Distribuída e Resiliente", 13, True, WD_ALIGN_PARAGRAPH.CENTER, depois=0)
    caixa(tema)
    sub = tema.add_run("\nRelatório Técnico")
    sub.font.size = Pt(12)
    sub.bold = False
    linha(depois=30)
    for t in ("Cadeira: Sistemas Distribuídos e Paralelos", "Curso: Licenciatura em Engenharia e Ciência dos Computadores",
              "Turma: LECC31", "Ano lectivo: 2026", "Discente: Kenneth Dembele"):
        linha(t, 11, depois=8)
    linha(depois=110)
    linha("Docente: Msc. Sérgio J. Sambo", 11, alinhar=WD_ALIGN_PARAGRAPH.RIGHT, depois=150)
    p = linha(f"Maputo, aos {DATA}", 11, True, WD_ALIGN_PARAGRAPH.CENTER, depois=0)
    p.add_run().add_break(WD_BREAK.PAGE)


# ------------------------------------------------------------------ conteudo
# Titulos e objectivos dos cenarios, com a acentuacao do relatorio (os ficheiros de evidencia sao ASCII).
CENARIOS = {
    0: ("Ambiente, rede, DNS e TLS",
        "Mostrar os nós, as redes, os endereços IP e as portas, e provar que as ligações ao PostgreSQL e às APIs usam "
        "TLS verificado: sem TLS ou com outro nome no certificado, a ligação é recusada.", ""),
    1: ("Transferência bem-sucedida entre Europa e América",
        "Transferir 125,50 EUR de EU-1001 (nó Europa) para US-2001 (nó América) com 2PC e confirmar um débito, um "
        "crédito, os comandos PREPARE TRANSACTION e COMMIT PREPARED nos dois nós e a confirmação do banco parceiro.",
        "Num só PC os dois nós são contentores diferentes; com distribuido/ o nó Europa corre no PC A e o nó América no PC B."),
    2: ("Saldo insuficiente e outras validações",
        "O bruno (EU-1003, 300,00) tenta transferir 1000,00: o nó Europa vota NÃO e a decisão é ABORT. Testam-se também "
        "conta inexistente, montante negativo, três casas decimais, origem igual ao destino e moeda diferente.", ""),
    3: ("Transferências concorrentes sobre a mesma conta",
        "Dez transferências simultâneas de 50,00 a partir de EU-1003, metade pela api-1 e metade pela api-2: só passam "
        "as que o saldo permite e o saldo nunca fica negativo.", ""),
    4: ("Repetição de um pedido com a mesma chave de idempotência",
        "O mesmo pedido enviado à api-1 e repetido na api-2 com a mesma Idempotency-Key produz uma só transferência; a "
        "mesma chave com outro montante é recusada (409); cinco pedidos simultâneos com a mesma chave criam uma só.", ""),
    5: ("Falha de um participante antes e durante a preparação",
        "(a) O nó Europa está em baixo quando chega uma transferência US-2001 → EU-1001: nenhum participante prepara e a "
        "decisão é ABORT. (b) O nó América cai depois de o Europa ter preparado: o Europa faz ROLLBACK PREPARED. "
        "Nenhum saldo muda.", "Com dois PCs pode desligar-se a rede do PC B em vez de parar o contentor."),
    6: ("Falha durante a confirmação e recuperação",
        "(a) A decisão COMMIT já está gravada e o Europa já confirmou quando o nó América cai: a transferência fica "
        "COMMIT_DECIDIDO, a transacção preparada sobrevive ao reinício do PostgreSQL e a recuperação conclui o COMMIT. "
        "(b) Falha de rede: o nó América fica sem responder (docker compose pause); o COMMIT esgota o tempo, a decisão "
        "não muda e a transferência conclui quando a rede volta.", "Com dois PCs pode desligar-se a rede do PC B durante a pausa."),
    7: ("Reinício do coordenador com transacções pendentes",
        "(a) O coordenador cai depois de gravar COMMIT: as linhas ficam bloqueadas e, ao reiniciar, conclui o COMMIT nos "
        "dois nós. (b) O coordenador cai depois de preparar mas antes de decidir: ao reiniciar faz abort presumido.", ""),
    8: ("Queda de uma instância da API e utilização da outra",
        "Com a api-1 parada, o cliente passa para a api-2. O token emitido antes continua válido porque a api-2 o valida "
        "localmente com a chave pública.", ""),
    9: ("Token inválido ou expirado e acesso sem autorização",
        "As APIs validam assinatura, expiração, emissor e destinatário do JWT e só deixam o titular consultar ou "
        "movimentar a conta; com o serviço de autenticação parado, um token válido continua aceite.", ""),
    10: ("Mensagem de transferência adulterada",
         "Um intermediário altera o montante de uma ordem assinada pela api-1. O coordenador verifica a assinatura "
         "RSA-PSS/SHA-256 antes de tocar nos saldos e recusa a ordem; recusa também uma chave desconhecida e uma ordem "
         "antiga, e aceita a ordem original intacta.", ""),
    11: ("Comunicação entre Python e Java (XML sobre HTTPS)",
         "O coordenador (Python) confirma cada transferência concluída no banco parceiro (Java) com XML e a API consulta "
         "esse registo. Testam-se a validação do XML no Java e a indisponibilidade do Java.", ""),
    12: ("Escrita e leitura dos ficheiros partilhados (NFS)",
         "A api-1 escreve um relatório no NFS e a api-2 lê-o; os eventos de auditoria de vários serviços ficam no mesmo "
         "DFS; com o NFS em baixo os eventos ficam em espera e são publicados depois.",
         "Com dois PCs, o servidor NFS está no PC A e a api-2 do PC B monta-o pela rede."),
}


CAPTURAS = AQUI / "capturas"
_figuras = [0]


def fig_numerada(doc, png, legenda, largura=16.0):
    _figuras[0] += 1
    figura(doc, str(png), f"Figura {_figuras[0]}. {legenda}", largura=largura)
    return _figuras[0]


def captura_real(doc, nome, legenda, largura=16.0):
    """Captura de ecra real (docs/relatorio/capturas), feita por capturar_ecra.py neste computador."""
    png = CAPTURAS / nome
    partes = [png.with_name(f"{png.stem}_{i}{png.suffix}") for i in (1, 2)]
    if not png.exists() and all(p.exists() for p in partes):
        # A saida nao coube numa janela: a mesma janela foi fotografada no inicio e no fim.
        fig_numerada(doc, partes[0], legenda + " Início da janela. Captura de ecrã real do computador de "
                                               "desenvolvimento.", largura)
        return fig_numerada(doc, partes[1], legenda + " Fim da mesma janela (continuação).", largura)
    if not png.exists():
        par(doc, f"**Captura em falta:** `{nome}` (gerar com `python docs/relatorio/capturar_ecra.py`).")
        return None
    return fig_numerada(doc, png, legenda + " Captura de ecrã real do computador de desenvolvimento.", largura)


def conteudo(doc, fig, ev):
    def H1(t):
        h = doc.add_heading(t, level=1)
        h.paragraph_format.page_break_before = True          # cada seccao principal na sua pagina
        return h
    H2 = lambda t: doc.add_heading(t, level=2)

    p = doc.add_paragraph()
    r = p.add_run("Resumo")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(13), AZUL
    par(doc, "Este relatório descreve o Global-Scale System, o protótipo de uma plataforma de transacções financeiras "
             "internacionais pedido no Exame Normal Prático de Sistemas Distribuídos e Paralelos [E]. As contas estão "
             "fragmentadas por região em dois nós PostgreSQL (Europa e América). Uma transferência entre regiões é "
             "uma transacção distribuída coordenada pelo protocolo Two-Phase Commit (2PC), implementado sobre as "
             "transacções preparadas do PostgreSQL, com registo durável da decisão e recuperação automática. Duas "
             "instâncias de uma API REST validam localmente tokens JWT RS256 emitidos por um nó de autenticação e "
             "assinam cada ordem de transferência com RSA-PSS sobre SHA-256. Um banco parceiro escrito em Java troca "
             "mensagens XML com o sistema; a auditoria e os relatórios ficam num sistema de ficheiros distribuído NFSv4. "
             "Todas as ligações usam TLS. O ambiente corre em Docker Compose num computador ou repartido por dois. "
             "Os treze cenários de teste, incluindo quedas de nós e uma falha de rede durante cada fase do 2PC, foram "
             "executados em Docker a partir de uma instalação limpa e as evidências reais estão no repositório.")
    p = doc.add_paragraph()
    p.paragraph_format.page_break_before = True               # o indice na sua pagina
    r = p.add_run("Índice")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(13), AZUL
    campo(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u', "(o índice é actualizado pelo Word)")

    # ---------------------------------------------------------------- 1
    H1("1. Introdução")
    par(doc, "A Global Scale Corporation precisa de processar transferências internacionais com alta disponibilidade, "
             "consistência dos dados, interoperabilidade entre tecnologias e segurança [E]. O objectivo deste trabalho "
             "é desenhar, implementar e documentar um protótipo funcional dessa infraestrutura e demonstrar, com falhas "
             "reais provocadas durante a execução, que o dinheiro nunca sai de uma conta sem entrar na outra.")
    par(doc, "O relatório segue as quatro partes do enunciado: arquitectura, redes e sistemas operativos (secção 2); "
             "processamento, transacções e base de dados (secção 3); interoperabilidade e serviços Web, incluindo a "
             "análise OMA/OMG (secção 4); e técnicas de segurança (secção 5). A secção 6 apresenta as evidências, a "
             "secção 7 associa cada requisito à implementação e à prova, e a secção 8 enumera as limitações.")
    tabela(doc, ["Conteúdo da disciplina [E]", "Onde é aplicado"], [
        ["1. Redes, SO e linguagens", "Redes Docker com IP fixos e DNS; contentores Linux; Python e Java"],
        ["2. Distribuído vs centralizado", "Secção 2.1; nós regionais, duas APIs, coordenador"],
        ["3. Transacções distribuídas", "2PC com PREPARE TRANSACTION, recuperação, idempotência"],
        ["4. Segurança", "TLS, JWT RS256, scrypt, assinaturas RSA-PSS/SHA-256"],
        ["5. Interoperabilidade", "Python ↔ Java com contrato XML sobre HTTPS"],
        ["6. Bases de dados distribuídas", "Fragmentação horizontal Europa/América"],
        ["7. SO distribuídos", "Transparência de localização (nomes, NFS), Docker como camada de distribuição"],
        ["8. DFS", "NFSv4 partilhado por três serviços"],
        ["9. OMG/OMA", "Secção 4.3"],
        ["10. Serviços Web", "API REST/JSON com OpenAPI"],
    ], [6, 10.6])

    # ---------------------------------------------------------------- 2
    H1("2. Parte 1: arquitectura, redes e sistemas operativos")
    H2("2.1 Sistema centralizado versus distribuído")
    par(doc, "Num sistema centralizado, um único servidor guarda todas as contas e processa todas as transferências. "
             "É mais simples (uma transacção local é ACID sem protocolo adicional), mas para uma empresa com clientes "
             "em vários continentes traz três limitações [1]:")
    topicos(doc, [
        "**Latência:** um cliente na América que fala com um servidor na Europa paga a viagem transatlântica (da "
        "ordem de 80 a 150 ms por ida e volta) em cada pedido. Com nós regionais, as leituras de saldo e histórico "
        "são servidas pelo nó da própria região.",
        "**Ponto único de falha:** se o servidor cair, nenhum cliente opera. Na arquitectura adoptada há duas "
        "instâncias da API (uma pode cair, cenário 8), e a queda de um nó regional só afecta as contas dessa região "
        "(cenário 5): as transferências entre contas europeias continuam.",
        "**Escalabilidade:** um servidor só cresce verticalmente (mais CPU e memória), até um limite físico e com "
        "custo crescente. Fragmentar os dados por região e acrescentar instâncias da API escala horizontalmente.",
    ])
    par(doc, "A distribuição tem custos que este trabalho trata explicitamente: uma transferência entre regiões "
             "passa a envolver dois nós e precisa de um protocolo de transacção distribuída (secção 3); as falhas "
             "parciais (um nó em baixo, uma mensagem perdida) passam a ser normais e têm de ser recuperadas; e há "
             "mais superfície de ataque na rede, por isso todas as ligações usam TLS (secção 5).")
    tabela(doc, ["Aspecto", "Centralizado", "Global-Scale (distribuído)"], [
        ["Latência de leitura", "Igual para todos, alta para quem está longe", "Nó da região do cliente"],
        ["Falha de um servidor", "Sistema todo parado", "Só a região ou a instância afectada"],
        ["Escala", "Vertical", "Horizontal (mais nós e instâncias)"],
        ["Transferência", "Transacção local", "2PC entre dois nós (mais mensagens, bloqueio se o coordenador cair)"],
        ["Operação", "Simples", "Recuperação, idempotência, monitorização"],
    ], [3.6, 5.6, 7.4])

    H2("2.2 Arquitectura implementada")
    fig_numerada(doc, fig["arq"], "Arquitectura do Global-Scale System: nós, redes, protocolos e portas.", largura=16.6)
    tabela(doc, ["Nó", "Tecnologia", "Função"], [
        ["auth", "Python 3.12, FastAPI", "Nó emissor de tokens: verifica a palavra-passe e assina JWT RS256"],
        ["api-1, api-2", "Python 3.12, FastAPI", "API REST; validam o JWT localmente e assinam as ordens"],
        ["coordenador", "Python 3.12, FastAPI, asyncio", "Coordenador 2PC com estado persistente e recuperação"],
        ["db-europa, db-america", "PostgreSQL 17.12", "Participantes 2PC; fragmentos Europa e América"],
        ["db-coordenador", "PostgreSQL 17.12", "Registo durável das transferências e decisões"],
        ["banco-parceiro", "Java 21 (só JDK)", "Banco parceiro legado; contrato XML"],
        ["nfs", "NFS-Ganesha (NFSv4)", "Sistema de ficheiros distribuído"],
    ], [3.4, 4.4, 8.8])

    H2("2.3 Rede: endereços, portas e DNS local")
    par(doc, "O ambiente local é definido em `docker-compose.yml`. Há duas redes bridge com sub-redes fixas: a rede "
             "`frontal` (172.30.1.0/24) só tem os serviços que os clientes usam, e a rede `interna` (172.30.2.0/24) tem "
             "as bases de dados, o coordenador, o banco parceiro e o NFS. Cada contentor tem um IP fixo e é "
             "encontrado pelo nome através do DNS interno do Docker [11]. Os certificados TLS têm esses nomes no SAN, "
             "o que permite ao cliente verificar que fala com o servidor certo (secção 5.1).")
    tabela(doc, ["Contentor", "IP frontal", "IP interno", "Porta", "No anfitrião"], [
        ["auth", "172.30.1.10", "172.30.2.50", "8000 HTTPS", "8000"],
        ["api-1 / api-2", "172.30.1.11 / .12", "172.30.2.51 / .52", "8001 / 8002 HTTPS", "8001 / 8002"],
        ["db-europa", "", "172.30.2.10", "5433 TLS", "não"],
        ["db-america", "", "172.30.2.11", "5434 TLS", "não"],
        ["db-coordenador", "", "172.30.2.12", "5435 TLS", "não"],
        ["coordenador", "", "172.30.2.20", "8100 HTTPS", "127.0.0.1 (testes)"],
        ["banco-parceiro", "", "172.30.2.30", "8200 HTTPS", "127.0.0.1 (testes)"],
        ["nfs", "", "172.30.2.40", "2049 NFSv4", "não"],
    ], [3.2, 3.2, 3.4, 3.4, 3.4])
    par(doc, "Cada nó PostgreSQL usa uma porta diferente para que a mesma configuração funcione em dois computadores. "
             "Nesse modo (`distribuido/pc-a.yml` e `pc-b.yml`), o PC A corre o nó Europa, o coordenador, a "
             "autenticação, a api-1 e o servidor NFS, e o PC B corre o nó América, a api-2 e o banco parceiro. Os "
             "nomes do outro computador são mapeados para o seu IP com `extra_hosts`, que acrescenta a entrada ao "
             "`/etc/hosts` do contentor [11]: os serviços continuam a usar os mesmos nomes e a verificação TLS "
             "continua válida. A transferência entre EU-1001 e US-2001 passa assim a envolver dois computadores "
             "fisicamente diferentes. As instruções e os comandos para o comprovar na demonstração estão em "
             "`docs/DOIS_COMPUTADORES.md`.")
    ensaio = EVID / "13_ensaio_dois_pcs.md"
    if ensaio.exists():
        texto = ensaio.read_text(encoding="utf8")
        par(doc, "Os dois ficheiros foram ensaiados num só computador, como dois projectos Docker que só comunicam "
                 "pelas portas publicadas (`IP_PC_A=IP_PC_B=host-gateway`), com o script `testes/ensaio_distribuido.py`. "
                 "O resultado está em `evidencias/13_ensaio_dois_pcs.md`: " +
                 ("todas as verificações passaram" if "**Resultado: PASSOU**" in texto else "há verificações por resolver") +
                 ". O coordenador do \"PC A\" preparou e confirmou no db-america do \"PC B\" por TLS 1.3, e a api-2 do "
                 "\"PC B\" montou o NFS do \"PC A\". O ensaio não substitui a prova física com duas máquinas, que se faz "
                 "com o mesmo procedimento trocando `host-gateway` pelos IP reais.")
    captura_real(doc, "ambiente.png", "Contentores, imagens, portas e endereços IP nas duas redes (docker compose ps e "
                 "docker network inspect).")
    captura_real(doc, "ensaio_dois_pcs.png", "Ensaio da configuração de dois computadores num só PC "
                 "(python testes/ensaio_distribuido.py).")

    H2("2.4 Sistemas operativos e contentores")
    par(doc, "Cada serviço corre num contentor Linux: Alpine para o PostgreSQL e o Java, Debian slim para o Python e "
             "o NFS. O Docker isola os processos (namespaces), limita os recursos (cgroups: 128 a 256 MB por "
             "contentor, cerca de 1,5 GB no total, adequado a um computador académico) e liga os contentores em "
             "redes virtuais. Os dados persistentes ficam em volumes com nome (`dados-europa`, `dados-coordenador`, "
             "...), que sobrevivem à recriação dos contentores. Cada contentor tem uma verificação de saúde "
             "(`healthcheck`) e o arranque respeita as dependências (`depends_on` com `service_healthy`) [11]. "
             "Do ponto de vista dos sistemas operativos distribuídos, a camada Docker oferece transparência de "
             "localização (o serviço é um nome, não uma máquina) e de migração (o mesmo contentor corre no PC A ou "
             "no PC B sem alterar o código).")
    captura_real(doc, "docker_desktop.png", "Docker Desktop com os contentores do Global-Scale em execução.")

    H2("2.5 Sistema de ficheiros distribuído (NFS)")
    par(doc, "O DFS é um servidor NFSv4 em espaço de utilizador, o NFS-Ganesha [20], que exporta `/dfs`. O volume "
             "`dfs` do Docker é do tipo NFS: é montado pelo cliente NFS do kernel Linux do anfitrião Docker e "
             "aparece como `/mnt/dfs` na api-1, na api-2 e no coordenador. Guarda a auditoria (um ficheiro JSON por "
             "evento, com o identificador da transferência, a data UTC, o serviço de origem e o resultado) e os "
             "extractos de conta em CSV.")
    par(doc, "**Transparência de localização.** O código só conhece o caminho `/mnt/dfs`. Quem resolve onde estão os "
             "ficheiros é a camada de sistema operativo: o cliente NFS do kernel traduz cada `open`, `write` e "
             "`rename` em pedidos NFSv4 ao servidor, que pode estar no mesmo computador ou noutro (no modo de dois "
             "PCs, a api-2 do PC B monta o NFS do PC A pelo IP). No cenário 12, a api-1 escreve um relatório e a "
             "api-2 lê-o, sem que nenhuma saiba onde está o disco.")
    par(doc, "**Acesso concorrente.** Em vez de vários serviços acrescentarem linhas ao mesmo ficheiro (o que no NFS "
             "exigiria bloqueios distribuídos), cada evento é um ficheiro com nome único: "
             "`<data UTC>_<transferência>_<serviço>_<evento>_<sufixo aleatório>.json`. O ficheiro é escrito com um "
             "nome temporário, sincronizado com `fsync` e depois renomeado; o `rename` dentro da mesma pasta é "
             "atómico, por isso um leitor vê o ficheiro completo ou não o vê. A estratégia é verificável: o cenário "
             "12 conta os ficheiros por serviço e confirma que não ficou nenhum temporário.")
    par(doc, "**Falhas de escrita.** Os eventos financeiros não podem perder-se nem atrasar as transferências. Por isso "
             "cada serviço grava primeiro o evento numa pasta de espera local, num volume persistente, e uma thread "
             "publica-o no DFS. Se o NFS estiver em baixo, os eventos acumulam-se na pasta de espera e são publicados "
             "quando ele voltar (cenário 12); o registo do coordenador na base de dados mantém, além disso, o diário "
             "completo de cada transferência. **Limites:** o servidor NFS é único, por isso durante uma falha a "
             "auditoria não pode ser lida; a montagem `soft` devolve erro em vez de bloquear para sempre; e o NFS com "
             "`sec=sys` não autentica os clientes, devendo ficar numa rede fechada. Alternativas replicadas seriam "
             "GlusterFS ou CephFS.")

    # ---------------------------------------------------------------- 3
    H1("3. Parte 2: processamento, transacções e base de dados")
    H2("3.1 Base de dados distribuída e fragmentação")
    par(doc, "Os dados financeiros estão fragmentados horizontalmente por região: o nó `db-europa` guarda os "
             "utilizadores e as contas europeias (`EU-xxxx`) e o nó `db-america` as americanas (`US-xxxx`). Os dois têm "
             "o mesmo esquema (`bd/regional/01-esquema.sql`); cada um tem uma restrição que impede linhas da outra "
             "região (`CHECK (id LIKE 'EU-%')`). O encaminhamento é feito pelo prefixo da conta (`config.no_da_conta`). "
             "As migrações são ficheiros SQL numerados que o PostgreSQL aplica no primeiro arranque e incluem dados "
             "fictícios de demonstração (quatro utilizadores e cinco contas, 10 600,00 EUR no total).")
    tabela(doc, ["Tabela (nó)", "Colunas principais", "Restrições"], [
        ["utilizadores (regional)", "id, nome, regiao, hash_palavra_passe", "regiao do fragmento"],
        ["contas (regional)", "id, titular, moeda, saldo_centimos", "saldo_centimos >= 0; id do fragmento"],
        ["movimentos (regional)", "transferencia_id, conta_id, tipo, montante_centimos, saldo_apos", "UNIQUE (transferencia_id, tipo); montante > 0"],
        ["transferencias (coordenador)", "id, utilizador, chave_idempotencia, hash_pedido, estado, decisao", "UNIQUE (utilizador, chave_idempotencia)"],
        ["participantes (coordenador)", "transferencia_id, no, gid, estado", "gid UNIQUE"],
        ["eventos (coordenador)", "transferencia_id, evento, detalhe, em", "diário do protocolo"],
    ], [4.2, 7.0, 5.4])
    par(doc, "Os montantes são guardados em cêntimos inteiros (`BIGINT`): `float` não representa 0,10 exactamente e as "
             "somas acumulariam erros. A API recebe texto decimal (`\"125.50\"`), valida no máximo duas casas e um "
             "valor positivo, e converte com `Decimal`. A demonstração usa uma moeda comum (EUR); o campo `moeda` "
             "existe em contas, ordens e mensagens, e uma conta noutra moeda é recusada (`MOEDA_DIFERENTE`).")

    H2("3.2 Two-Phase Commit com transacções preparadas")
    par(doc, "Uma transferência de EU-1001 para US-2001 tem de debitar um nó e creditar o outro de forma atómica. O "
             "coordenador (`servicos/coordenador/dois_fases.py`) implementa o 2PC [1] sobre o mecanismo nativo do "
             "PostgreSQL: `PREPARE TRANSACTION` grava no disco todo o estado da transacção, que continua a manter os "
             "seus bloqueios e pode ser confirmada mesmo depois de uma queda do servidor [2]; `COMMIT PREPARED` e "
             "`ROLLBACK PREPARED` terminam-na a partir de qualquer sessão do mesmo utilizador [5]; e a vista "
             "`pg_prepared_xacts` lista as transacções preparadas e o seu identificador global (gid) [4]. O parâmetro "
             "`max_prepared_transactions` é 0 por omissão, o que desactiva a funcionalidade, e só pode ser alterado "
             "no arranque; está configurado com 40, igual a `max_connections`, como recomenda a documentação [3].")
    fig_numerada(doc, fig["2pc"], "Sequência de uma transferência com 2PC.", largura=16.6)
    topicos(doc, [
        "**Fase 1 (preparação).** Para cada participante, por uma ordem fixa (primeiro Europa, depois América): "
        "`BEGIN`, `UPDATE` do saldo (o débito só se `saldo >= montante`), `INSERT` do movimento e `PREPARE "
        "TRANSACTION 'gs-<id>-<nó>'`. Um nó vota NÃO se a conta não existir, o saldo for insuficiente, a linha "
        "estiver bloqueada mais de 5 s ou não responder; nesse caso o nó seguinte nem é contactado.",
        "**Decisão.** Se todos prepararam, o coordenador grava `decisao = 'COMMIT'` no seu registo e confirma essa "
        "transacção local antes de enviar qualquer confirmação. O `UPDATE ... WHERE decisao IS NULL` garante que a "
        "primeira decisão é a única. Caso contrário grava ABORT.",
        "**Fase 2 (confirmação).** `COMMIT PREPARED` (ou `ROLLBACK PREPARED`) nos dois nós, em paralelo. Antes, "
        "consulta-se `pg_prepared_xacts`: se o gid já não existir, a decisão já tinha sido aplicada, o que torna "
        "a repetição segura.",
    ])
    codigo(doc, '''async def preparar(no, t, operacoes):
    async with pools_preparar[no].connection() as c:          # autocommit: BEGIN e PREPARE explicitos
        await c.execute("BEGIN")
        await c.execute("SET LOCAL lock_timeout = '5s'")
        for tipo, conta, contraparte in sorted(operacoes):       # ordem fixa das contas
            await _operacao(c, t, tipo, conta, contraparte)      # UPDATE condicional + INSERT
        await c.execute(sql.SQL("PREPARE TRANSACTION {}").format(sql.Literal(gid)))

async def decidir(tid, decisao):                                  # gravada ANTES de ser comunicada
    UPDATE transferencias SET decisao = %s, estado = 'COMMIT_DECIDIDO' WHERE id = %s AND decisao IS NULL''')
    par(doc, "O psycopg 3 tem métodos de dois fases da DB-API (`tpc_begin`, `tpc_prepare`, `tpc_commit`) [9]; optou-se "
             "pelos comandos SQL explícitos para que cada passo do protocolo seja visível no código e nos logs dos "
             "nós PostgreSQL, onde a evidência do cenário 1 mostra os dois `PREPARE TRANSACTION` e os dois "
             "`COMMIT PREPARED`.")

    H2("3.3 Como o 2PC garante as propriedades ACID")
    tabela(doc, ["Propriedade", "Como é garantida"], [
        ["Atomicidade", "O débito e o crédito só ficam visíveis com COMMIT PREPARED, que só é enviado depois de os dois nós "
                        "terem preparado e de a decisão estar gravada. Qualquer voto NÃO leva a ROLLBACK PREPARED em todos."],
        ["Consistência", "CHECK (saldo_centimos >= 0), UNIQUE (transferencia_id, tipo) e a soma constante de todos os "
                         "saldos; a verificação global dos testes confirma 10 600,00 EUR antes e depois."],
        ["Isolamento", "Cada participante usa uma transacção local; as linhas alteradas ficam bloqueadas até à decisão, por "
                       "isso nenhuma leitura vê um débito sem o crédito correspondente (leituras veem o último estado confirmado)."],
        ["Durabilidade", "A preparação fica no disco de cada nó (pg_twophase) e sobrevive a reinícios (cenário 6); a "
                         "decisão fica no WAL do db-coordenador, num volume persistente (cenário 7)."],
    ], [3.2, 13.4])
    par(doc, "É isto que impede que o dinheiro saia de uma conta sem entrar na outra em caso de falha de rede: depois "
             "de preparar, um nó já não pode decidir sozinho; e depois de a decisão COMMIT estar gravada, ela é "
             "repetida até todos os nós a aplicarem, por mais tempo que a rede demore a voltar.")

    H2("3.4 Falhas, recuperação e bloqueio")
    tabela(doc, ["Momento da falha", "Comportamento", "Prova"], [
        ["Nó em baixo antes da preparação", "O primeiro nó falha (NO_INDISPONIVEL); nenhum prepara; ABORT; HTTP 503", "Cenário 5a"],
        ["Nó cai durante a preparação", "Voto NÃO; os nós já preparados fazem ROLLBACK PREPARED; HTTP 503", "Cenário 5b"],
        ["Resposta ao PREPARE perdida", "Participante INCERTO; decisão ABORT; ROLLBACK PREPARED repetido até o nó responder", "Código"],
        ["Nó cai depois da decisão", "Estado COMMIT_DECIDIDO (HTTP 202, pendente_em); a recuperação repete COMMIT PREPARED a cada 5 s", "Cenário 6a"],
        ["Falha de rede na confirmação (nó vivo sem responder)", "COMMIT PREPARED esgota o tempo (5 s); decisão mantém-se; conclui quando a rede volta", "Cenário 6b"],
        ["Coordenador cai depois da decisão", "No arranque, repete a decisão gravada nos dois nós", "Cenário 7a"],
        ["Coordenador cai antes da decisão", "Abort presumido: sem decisão gravada ninguém confirmou, logo é seguro desfazer", "Cenário 7b"],
        ["Transacção preparada sem registo", "ROLLBACK PREPARED (órfã)", "Código"],
        ["Banco parceiro em baixo", "A transferência conclui; confirmação POR_ENVIAR e reenviada", "Cenário 11"],
    ], [4.4, 9.8, 2.4])
    par(doc, "**Timeout de comunicação versus decisão.** Um timeout significa \"não sei o que aconteceu\", nunca "
             "\"falhou\". Se o coordenador não responder à API, esta devolve HTTP 504 com \"resultado DESCONHECIDO\" "
             "e o cliente repete com a mesma chave de idempotência ou consulta `GET /transferencias?chave=` "
             "(cenário 7a). Dentro do coordenador, um timeout na fase 1 permite ainda decidir ABORT (não há decisão), "
             "mas um timeout na fase 2 nunca altera a decisão gravada: o nó fica pendente e o comando é repetido.")
    par(doc, "**Comportamento bloqueante.** Um participante preparado não sabe se os outros prepararam, por isso não "
             "pode confirmar nem desfazer sozinho. Se o coordenador cair entre a preparação e a fase 2, as linhas "
             "envolvidas ficam bloqueadas até ele voltar: o cenário 7a mostra um `UPDATE` directo na conta EU-1002 a "
             "falhar com `lock timeout` enquanto o coordenador está em baixo. A documentação do PostgreSQL alerta "
             "precisamente para não deixar transacções preparadas por muito tempo [2]. As condições para recuperar o "
             "progresso são: o registo do coordenador sobreviver (volume persistente), o coordenador voltar a "
             "arrancar e conseguir falar com os nós. O 3PC e os protocolos de consenso (Paxos, Raft) replicam o "
             "coordenador para reduzir este bloqueio, a custo de mais mensagens [1].")

    H2("3.5 Concorrência e idempotência")
    par(doc, "**Saldo nunca negativo.** O débito é `UPDATE contas SET saldo = saldo - m WHERE id = x AND titular = u AND "
             "saldo >= m`. O `UPDATE` bloqueia a linha; uma segunda transferência sobre a mesma conta espera e, quando "
             "a primeira termina, o PostgreSQL reavalia a condição com o saldo novo. A restrição `CHECK (saldo_centimos "
             ">= 0)` é a última defesa. No cenário 3, dez pedidos simultâneos de 50,00 sobre uma conta com saldo para "
             "um número limitado deles, metade pela api-1 e metade pela api-2, produzem exactamente esse número de "
             "transferências concluídas e um débito por cada uma.")
    par(doc, "**Bloqueio mútuo distribuído.** A primeira versão preparava os dois nós em paralelo. No teste de "
             "concorrência, 8 de 10 transferências abortaram por `lock_timeout`: uma transacção ficava com a linha no "
             "Europa e outra com a linha no América, cada uma à espera da outra, e nenhum PostgreSQL via o ciclo, "
             "porque cada um só conhece os seus bloqueios. A correcção foi adquirir os recursos por uma ordem global "
             "fixa (todos os nós pela ordem Europa, América, e as contas ordenadas dentro de cada nó), o que elimina "
             "os ciclos de espera. O `lock_timeout` de 5 s mantém-se como protecção.")
    par(doc, "**Idempotência.** O cliente envia `Idempotency-Key` com cada transferência. O coordenador insere a "
             "transferência com `INSERT ... ON CONFLICT (utilizador, chave_idempotencia) DO NOTHING`; a unicidade é "
             "garantida pelo PostgreSQL, por isso dois pedidos simultâneos com a mesma chave nunca criam duas "
             "transferências. Uma repetição devolve a transferência existente (`repetido: true`); a mesma chave com "
             "outros dados é detectada pela comparação do resumo SHA-256 dos campos do pedido e recusada com HTTP 409 "
             "(cenário 4).")

    H2("3.6 Linguagem de programação e concorrência")
    par(doc, "Os serviços principais estão em Python 3.12. No CPython, o GIL garante que só uma thread executa bytecode "
             "Python de cada vez, mas é libertado durante as operações de entrada e saída [13]. Estes serviços passam "
             "quase todo o tempo à espera da rede e das bases de dados, por isso a concorrência é real. A "
             "implementação usa quatro mecanismos:")
    topicos(doc, [
        "**Threads (API e autenticação).** Os endpoints são funções normais; o FastAPI corre cada pedido numa thread de "
        "um pool. Enquanto uma thread espera pelo PostgreSQL, as outras avançam. A auditoria usa ainda uma thread "
        "dedicada que publica os eventos no DFS, acordada por um `threading.Event`.",
        "**Tarefas assíncronas (coordenador).** Um único ciclo de eventos asyncio atende muitas transferências ao mesmo "
        "tempo: em cada `await` (rede, base de dados) passa a outra tarefa. A fase 2 aplica a decisão nos dois nós em "
        "paralelo com `asyncio.gather`; a recuperação é uma tarefa permanente que corre a cada 5 s; os timeouts usam "
        "`asyncio.timeout`. O estado em memória (`em_curso`, pausas) só é tocado pelo ciclo de eventos, por isso não "
        "precisa de lock.",
        "**Conexões.** Cada serviço usa pools psycopg que limitam as ligações simultâneas por nó (os pedidos a mais "
        "esperam na fila). Escolheu-se o pool sem ligações em repouso (`NullConnectionPool`), que abre uma ligação nova "
        "por operação [8]: um pool normal, depois de falhas seguidas, espaça as novas tentativas em backoff "
        "exponencial [8], e o ensaio mostrou que isso deixava o coordenador sem ligação ao nó América vários segundos "
        "depois de ele voltar. O coordenador tem ainda pools separados para preparar e para decidir, para que um "
        "`COMMIT PREPARED` nunca fique à espera de uma ligação ocupada por uma preparação bloqueada.",
        "**Bloqueios.** Na base de dados: bloqueios de linha do `UPDATE`, mantidos pelas transacções preparadas até à "
        "decisão, com `lock_timeout` de 5 s; e a restrição `UNIQUE` como bloqueio da idempotência. No Java, um pool de "
        "4 threads atende os pedidos e os registos ficam num `ConcurrentHashMap` com `computeIfAbsent` atómico.",
    ])
    par(doc, "Para trabalho intensivo de CPU, o GIL seria uma limitação e usar-se-iam processos (`multiprocessing`) ou "
             "mais instâncias, como as duas APIs. O Java e o Go têm threads ou corrotinas executadas em paralelo real, "
             "mas o Python foi preferido pela maturidade das bibliotecas usadas (FastAPI, psycopg, cryptography) e "
             "pela clareza do código, que é mais importante num protótipo que tem de ser explicado.")

    # ---------------------------------------------------------------- 4
    H1("4. Parte 3: interoperabilidade e serviços Web")
    H2("4.1 API REST")
    par(doc, "O núcleo expõe uma API REST com JSON sobre HTTPS, implementada em FastAPI, que gera automaticamente a "
             "especificação OpenAPI e a interface Swagger em `/docs`. As duas instâncias são a mesma imagem com "
             "identidades diferentes (`INSTANCIA=api-1` ou `api-2`, cada uma com a sua chave de assinatura) e "
             "devolvem o cabeçalho `X-Instancia`, que mostra qual respondeu.")
    tabela(doc, ["Método e caminho", "Descrição"], [
        ["POST /api/v1/autenticacao/token (auth)", "Autenticação; devolve o JWT"],
        ["GET /api/v1/contas, /contas/{id}, /contas/{id}/saldo", "Contas e saldo (só o titular)"],
        ["GET /api/v1/contas/{id}/movimentos", "Histórico"],
        ["POST /api/v1/transferencias (Idempotency-Key)", "Transferência; 201, 202 (pendente), 409, 422, 503, 504"],
        ["GET /api/v1/transferencias[?chave=], /{id}", "Estado, participantes, confirmação do parceiro"],
        ["GET /api/v1/transferencias/{id}/auditoria", "Eventos da transferência no DFS"],
        ["GET /api/v1/parceiro/transferencias/{id}", "Consulta no banco parceiro (Java)"],
        ["POST /api/v1/relatorios/extracto, GET /api/v1/relatorios[/{nome}]", "Extractos CSV no DFS"],
    ], [8.2, 8.4])
    captura_real(doc, "swagger_edge.png", "Documentação OpenAPI da api-1 no Microsoft Edge (https://localhost:8001/docs). "
                 "A especificação está também em docs/openapi/.", largura=15.0)

    H2("4.2 Módulo legado em Java e contrato XML")
    par(doc, "O banco parceiro (`banco-parceiro/src/BancoParceiro.java`) simula o sistema de um banco externo. Está "
             "escrito em Java 21 só com a biblioteca padrão: `HttpsServer` para o HTTPS, `DocumentBuilderFactory` para "
             "o XML e um ficheiro de texto para persistir os registos. Integra-se numa operação concreta: quando uma "
             "transferência fica CONCLUIDA, o coordenador envia-lhe uma `<confirmacaoTransferencia>` e guarda a "
             "referência devolvida (`BP-000001`); a API pode consultar esse registo. O contrato está formalizado em "
             "`banco-parceiro/contrato.xsd`.")
    codigo(doc, '''<confirmacaoTransferencia versao="1">                     Python -> Java  (POST /legado/confirmacoes)
  <id>0b9d6f7e-...</id><contaOrigem>EU-1001</contaOrigem><contaDestino>US-2001</contaDestino>
  <montanteCentimos>12550</montanteCentimos><moeda>EUR</moeda><concluidaEm>2026-11-19T10:00:00.000Z</concluidaEm>
</confirmacaoTransferencia>
<registoParceiro versao="1"><id>0b9d6f7e-...</id><referenciaParceiro>BP-000001</referenciaParceiro>
  <estado>REGISTADA</estado>...<recebidaEm>...</recebidaEm></registoParceiro>          Java -> Python (201 / 200)''')
    par(doc, "**Validação.** O Java recusa DTD e entidades externas (protecção contra XXE), exige todos os campos e "
             "valida-os com expressões regulares e `Instant.parse`; um erro devolve HTTP 400 com `<erro>`. O Python "
             "valida a resposta (elemento raiz, campos obrigatórios, formato da referência e identificador igual ao "
             "enviado). **Idempotência:** o mesmo identificador devolve sempre a mesma referência. **Indisponibilidade:** "
             "o Java não participa no 2PC, por isso a sua queda não impede transferências; a confirmação fica "
             "`POR_ENVIAR` e o ciclo de recuperação reenvia-a; a consulta pela API devolve HTTP 503 (cenário 11).")

    H2("4.3 OMA/OMG, CORBA e os serviços Web actuais")
    par(doc, "A Object Management Architecture (OMA) do Object Management Group (OMG) organiza um sistema distribuído "
             "em objectos que comunicam através de um Object Request Broker (ORB). O CORBA é a sua concretização: uma "
             "arquitectura aberta e independente de fabricantes para interoperabilidade entre sistemas diferentes, em "
             "que o ORB é o mecanismo básico pelo qual os objectos fazem pedidos de forma transparente a outros "
             "objectos, locais ou remotos [18]. A versão mais recente da especificação é a 3.4 (2021) [18]. As "
             "interfaces são descritas numa linguagem neutra (IDL), compilada para stubs e skeletons em cada "
             "linguagem, e a OMA acrescenta serviços de objectos comuns (nomes, eventos, transacções, segurança).")
    tabela(doc, ["Conceito OMA/CORBA", "Equivalente no Global-Scale", "Diferença"], [
        ["ORB (encaminha invocações, esconde a localização)", "HTTP/HTTPS + DNS do Docker; extra_hosts em dois PCs",
         "Não há broker central: cada serviço chama o outro pelo nome"],
        ["IDL (contrato neutro)", "OpenAPI gerado pelo FastAPI; XSD do contrato XML",
         "Descreve recursos e documentos, não métodos de objectos"],
        ["Stubs/skeletons gerados", "Modelos Pydantic; DOM no Java", "Contrato textual (JSON/XML) em vez de binário (GIOP/IIOP)"],
        ["Naming Service", "DNS interno do Docker", "Nomes de serviços, não de objectos"],
        ["Object Transaction Service", "Coordenador 2PC com registo durável", "Implementado na aplicação, sobre o PostgreSQL"],
        ["Security Service", "TLS, JWT RS256, assinaturas RSA-PSS", "Normas Web (RFC) em vez de especificação OMG"],
        ["Referência de objecto remoto com estado", "Pedidos sem estado com token", "REST é stateless [19]"],
    ], [4.8, 5.8, 6.0])
    par(doc, "A influência é directa: a ideia de um contrato independente da linguagem (IDL) reaparece no OpenAPI e no "
             "Protocol Buffers do gRPC; a transparência de localização do ORB reaparece nos nomes de serviço, nos "
             "service meshes e nos gateways; e os serviços de objectos tornaram-se serviços de plataforma (descoberta, "
             "mensagens, identidade). As diferenças explicam a mudança: o CORBA acoplava cliente e servidor ao mesmo "
             "modelo de objectos e a um protocolo binário que atravessava mal firewalls; o REST impõe uma interface "
             "uniforme e comunicação sem estado, em que cada pedido contém toda a informação necessária [19], o que "
             "facilita intermediários, cache e escala horizontal (as duas APIs aceitam qualquer pedido porque o token "
             "viaja em cada um). No projecto, o banco parceiro em Java integra-se sem partilhar nenhuma biblioteca com o "
             "Python: basta o contrato XML, o que num ambiente CORBA exigiria um ORB compatível dos dois lados.")

    # ---------------------------------------------------------------- 5
    H1("5. Parte 4: técnicas de segurança")
    H2("5.1 Cifragem do canal (TLS)")
    par(doc, "O script `seguranca/gerar_materiais.py` cria uma autoridade certificadora (CA) de laboratório e um "
             "certificado por serviço, com o nome DNS do serviço no SAN (mais `localhost` para os testes no próprio "
             "PC). Todos os serviços Web só aceitam HTTPS: o uvicorn (auth, APIs, coordenador) e o `HttpsServer` do "
             "Java, que lê o certificado em PKCS#12. Os clientes Python confiam apenas na CA do laboratório e "
             "verificam o nome do servidor. A confiança nos dois computadores instala-se com `certutil` (Windows) "
             "ou `update-ca-certificates` (Linux), como descrito em `docs/DOIS_COMPUTADORES.md`.")
    par(doc, "Nos nós PostgreSQL: `ssl=on`, versão mínima TLS 1.2 e um `pg_hba.conf` com `hostssl ... scram-sha-256`, que "
             "só aceita ligações TCP com TLS, seguido de `hostnossl ... reject`, que recusa as restantes [7]. Os "
             "clientes usam `sslmode=verify-full`, que verifica a cadeia até à CA e que o nome do servidor coincide "
             "com o certificado, protegendo contra intermediários [6]. O cenário 0 prova as três situações: a ligação "
             "sem TLS é recusada, a ligação ao IP (nome que não está no certificado) é recusada, e as ligações dos "
             "serviços aparecem em `pg_stat_ssl` com TLS 1.3.")
    par(doc, "A captura da execução do cenário 0, com estas ligações, está na secção 6.1.")

    H2("5.2 Autenticação distribuída com JWT")
    par(doc, "O serviço `auth` é o nó emissor de tokens: verifica a palavra-passe no nó regional do utilizador e emite "
             "um JWT assinado com RS256, isto é, RSASSA-PKCS1-v1_5 com SHA-256 e chave RSA de 2048 bits [16]. O token "
             "tem `iss` (quem o emitiu), `aud` (a quem se destina), `sub`, `regiao`, `iat`, `nbf`, `exp` (15 minutos) e "
             "`jti` [15]. A chave privada só é montada no `auth`. As duas APIs e o coordenador recebem apenas a chave "
             "pública e validam o token de forma independente: assinatura, expiração, emissor e destinatário, com a "
             "lista de algoritmos fixa (o que recusa `none` e HS256). O cenário 9 mostra que, com o `auth` parado, a "
             "api-2 continua a aceitar um token válido; e que tokens assinados com outra chave, expirados, para outro "
             "destinatário, de outro emissor ou adulterados recebem HTTP 401.")
    H2("5.3 Autorização e palavras-passe")
    par(doc, "Só o titular pode consultar ou movimentar uma conta: a API compara o titular com o `sub` do token (HTTP "
             "403) e o próprio `UPDATE` do débito no participante inclui `AND titular = utilizador`. O coordenador "
             "recusa ordens cujo utilizador não seja o do token. As palavras-passe são guardadas com scrypt (N=2^14, "
             "r=8, p=5, sal aleatório de 16 bytes), uma das configurações recomendadas pela OWASP [14], e comparadas "
             "em tempo constante; um utilizador inexistente também calcula um hash, para o tempo de resposta não "
             "revelar quais os nomes válidos. Nas bases de dados, cada serviço usa um papel com o mínimo de "
             "privilégios: `gs_leitura` (só SELECT) para as APIs e a autenticação, `gs_transaccoes` para o coordenador.")
    H2("5.4 Integridade das mensagens: assinatura digital e SHA-256")
    par(doc, "Cada ordem de transferência que uma API envia ao coordenador é assinada (`servicos/comum/assinatura.py`):")
    topicos(doc, [
        "**Representação determinística:** os campos relevantes (id, chave de idempotência, utilizador, contas, montante "
        "em cêntimos, moeda, `emitido_em` e instância) em JSON canónico, com chaves ordenadas, sem espaços e em UTF-8. "
        "Os mesmos dados produzem sempre os mesmos bytes, seja qual for a ordem dos campos.",
        "**SHA-256:** resume esses bytes em 32 bytes. Qualquer alteração, mesmo de um dígito no montante, produz um "
        "resumo completamente diferente (cenário 10).",
        "**RSA-PSS:** a API assina o resumo com a sua chave privada (RSASSA-PSS, esquema probabilístico com sal "
        "aleatório [17]). O coordenador verifica com a chave pública dessa instância antes de qualquer alteração "
        "financeira; se a verificação falhar, responde 401 e regista a recusa na auditoria.",
    ])
    par(doc, "O SHA-256 garante a integridade (detecta a alteração) e a assinatura garante a autenticidade (só quem "
             "tem a chave privada da api-1 ou da api-2 a consegue produzir). Um hash sozinho não bastaria, porque um "
             "atacante que alterasse o montante podia recalcular o hash. Para detectar repetições, a mensagem inclui "
             "`emitido_em` (o coordenador recusa mensagens com mais de 120 s) e a chave de idempotência (uma repetição "
             "dentro da janela devolve a transferência existente, sem a duplicar).")
    H2("5.5 Segredos e dados em repouso")
    par(doc, "Os segredos nunca entram no repositório: `segredos/` e `.env` estão no `.gitignore`; o repositório tem o "
             "`.env.example` e o script que gera as palavras-passe aleatórias, a CA e as chaves. No Docker, cada ficheiro "
             "é montado como secret em `/run/secrets/<nome>` [12] e só nos serviços que precisam dele (por exemplo, só "
             "o `auth` recebe `jwt-privada.pem`; a chave da CA não é montada em nenhum). **Medidas efectivamente "
             "configuradas para os dados persistidos:** hash scrypt das palavras-passe; papéis com privilégios mínimos; "
             "chaves privadas fora das imagens; volumes Docker acessíveis só ao Docker. **Não configurado:** cifragem do "
             "disco das bases de dados e do NFS; em produção usar-se-ia BitLocker ou LUKS nos volumes, ou `pgcrypto` "
             "para colunas sensíveis, e Kerberos (`sec=krb5p`) no NFS.")

    # ---------------------------------------------------------------- 6
    H1("6. Evidências de funcionamento")
    par(doc, "Os cenários são executados por `python testes/cenarios.py` com o sistema a correr em Docker. Cada cenário "
             "provoca falhas reais (`docker compose stop`, `kill`, `start`, e `pause`/`unpause` para simular uma falha de "
             "rede em que o nó fica vivo mas deixa de responder), lê os saldos directamente nos nós PostgreSQL, de forma "
             "independente da API, e grava um ficheiro `.md` e um `.json` em `evidencias/`. Para escolher o momento exacto "
             "da falha, o coordenador tem pontos de pausa de laboratório (`POST /laboratorio/pausa`, activos só com "
             "`LABORATORIO=1` e protegidos por uma chave); a falha em si é sempre real.")
    par(doc, "**Como foram obtidas as imagens.** Cada cenário foi executado numa janela própria do PowerShell no computador "
             "de desenvolvimento (Windows 10 Pro, Docker Desktop 4.99) e a imagem é a captura de ecrã dessa janela no fim "
             "da execução (`docs/relatorio/capturar_ecra.py`). A janela mostra os passos com a hora, um resumo dos estados "
             "internos (registo do coordenador, `pg_prepared_xacts`, respostas), as verificações e, no fim, a verificação "
             "global de consistência de todo o sistema. O conteúdo completo de cada bloco está no ficheiro de evidência "
             "indicado. Antes desta execução, os mesmos 13 cenários passaram numa execução feita a partir de um clone limpo "
             "do repositório, com certificados e palavras-passe novos (`evidencias/REPRODUCAO_LIMPA.md`).")
    resumo = []
    for n in range(0, 13):
        d = ev.get(n)
        resumo.append([str(n), CENARIOS[n][0],
                       ("PASSOU" if d["passou"] else "FALHOU") if d else "-",
                       f"{sum(1 for _, o in d['verificacoes'] if o)}/{len(d['verificacoes'])}" if d else "-"])
    d99 = ev.get(99)
    if d99:
        resumo.append(["99", "Verificação global de consistência", "PASSOU" if d99["passou"] else "FALHOU",
                       f"{sum(1 for _, o in d99['verificacoes'] if o)}/{len(d99['verificacoes'])}"])
    tabela(doc, ["#", "Cenário", "Resultado", "Verificações"], resumo, [1.0, 10.6, 2.4, 2.6])
    captura_real(doc, "testes_unitarios.png", "Testes unitários (pytest): dinheiro, assinaturas, JWT, scrypt e contrato XML.")
    captura_real(doc, "cliente_transferencia.png", "Cliente de linha de comandos: saldo e transferência Europa → América.")

    for n in range(0, 13):
        d = ev.get(n)
        titulo, objectivo, dois = CENARIOS[n]
        h = H2(f"6.{n + 1} Cenário {n}: {titulo}")
        h.paragraph_format.page_break_before = True           # cada cenario na sua pagina
        if d is None:
            par(doc, f"**Por executar:** `python testes/cenarios.py {n}`.")
            continue
        ok = sum(1 for _, o in d["verificacoes"] if o)
        par(doc, f"**Objectivo.** {objectivo}")
        par(doc, f"**Resultado:** {'PASSOU' if d['passou'] else 'FALHOU'} ({ok}/{len(d['verificacoes'])} verificações). "
                 f"Evidência completa em `evidencias/{d['ficheiro']}.md`." + (f" **Dois computadores:** {dois}" if dois else ""))
        sal = d["dados"].get("saldos")
        if sal:
            rot = list(sal)
            tabela(doc, ["Conta"] + [f"Saldo {r} (EUR)" for r in rot],
                   [[c] + [f"{sal[r][c] / 100:,.2f}".replace(",", " ") for r in rot] for c in sal[rot[0]]],
                   [3.0] + [13.6 / len(rot)] * len(rot))
        captura_real(doc, f"cenario_{n:02d}.png", f"Execução do cenário {n}: {titulo[0].lower() + titulo[1:]}.",
                     largura=15.6)

    if d99:
        h = H2("6.14 Verificação global de consistência")
        h.paragraph_format.page_break_before = True
        par(doc, "Depois de cada cenário, o executor confere todo o sistema directamente nas bases de dados: a soma de todos "
                 "os saldos, a ausência de saldos negativos, que cada transferência CONCLUIDA tem exactamente um DEBITO e um "
                 "CREDITO, que as ABORTADA não têm movimentos, que não há movimentos sem transferência e que não ficou "
                 "nenhuma transacção preparada por resolver. As últimas linhas de cada captura mostram esse resultado; "
                 "o estado final, depois do último cenário, é este:")
        saldos_finais = json.loads(d99["blocos"].get("Saldos finais", "{}") or "{}")
        tabela(doc, ["Conta", "Saldo final (EUR)"], [[c, v] for c, v in saldos_finais.items()], [5.0, 5.0])
        topicos(doc, [("PASSOU: " if o else "FALHOU: ") + v for v, o in d99["verificacoes"]])

    # ---------------------------------------------------------------- 7
    H1("7. Requisitos, implementação e validação")
    tabela(doc, ["Requisito do enunciado [E]", "Ficheiro ou configuração", "Evidência"], [
        ["Limitações do centralizado", "Secção 2.1", "-"],
        ["SO modernos em contentores, IP, portas, DNS", "docker-compose.yml (networks, ipv4_address)", "Cenário 0"],
        ["Dois computadores", "distribuido/pc-a.yml, pc-b.yml, docs/DOIS_COMPUTADORES.md", "Ensaio num PC (evidência 13); prova física manual"],
        ["DFS (NFS) para auditoria e relatórios", "nfs/, volume dfs, comum/auditoria.py", "Cenário 12"],
        ["Instruções do servidor e clientes NFS", "docs/DOIS_COMPUTADORES.md (Servidor e clientes NFS)", "-"],
        ["Transparência e acesso concorrente no DFS", "Um ficheiro por evento, rename atómico", "Cenário 12"],
        ["BD fragmentada Europa/América", "bd/europa, bd/america, config.no_da_conta", "Cenário 1"],
        ["Transferência entre nós diferentes com 2PC", "coordenador/dois_fases.py", "Cenários 1, 5, 6, 7"],
        ["Falhas antes, durante a preparação e na confirmação", "preparar(), _aplicar_no(), recuperar()", "Cenários 5a, 5b, 6a, 6b"],
        ["Timeout de comunicação distinto da decisão", "api/main.py (504 DESCONHECIDO), asyncio.timeout na fase 2", "Cenários 6b, 7a"],
        ["max_prepared_transactions", "docker-compose.yml (command do PostgreSQL)", "Cenário 0"],
        ["Decisão durável e recuperação", "decidir(), recuperar(), db-coordenador", "Cenários 6, 7"],
        ["Concorrência sem saldo negativo", "_operacao() (UPDATE condicional), CHECK", "Cenário 3"],
        ["Idempotência e reutilização da chave", "registar_ou_obter(), hash_pedido()", "Cenário 4"],
        ["Justificação da linguagem", "Secção 3.6", "-"],
        ["API REST/JSON com OpenAPI", "servicos/api/main.py, /docs, docs/openapi/*.json", "Todos os cenários"],
        ["Módulo noutra tecnologia (Java) com XML", "banco-parceiro/, comum/contrato_parceiro.py", "Cenário 11"],
        ["Análise OMA/OMG", "Secção 4.3", "-"],
        ["TLS nos serviços Web e na BD", "comum/servidor.py, bd/pg_hba.conf, comum/bd.py", "Cenário 0"],
        ["Nó emissor de tokens e validação independente", "autenticacao/main.py, comum/tokens.py", "Cenário 9"],
        ["Assinaturas/hashes nas mensagens", "comum/assinatura.py", "Cenário 10"],
        ["Segredos fora do repositório", ".gitignore, .env.example, seguranca/gerar_materiais.py", "git status"],
        ["Demonstração: derrubar nós", "docs/ROTEIRO_DEFESA.md, testes/lab.py", "Cenários 5 a 8, 11, 12"],
    ], [5.8, 7.2, 3.6])

    # ---------------------------------------------------------------- 8
    H1("8. Limitações e trabalho futuro")
    topicos(doc, [
        "**Coordenador único.** Se cair depois de os nós prepararem, as linhas ficam bloqueadas até voltar (bloqueio do "
        "2PC). Replicar o registo do coordenador com consenso (Raft) ou usar 3PC reduziria esse tempo.",
        "**NFS único.** Durante uma falha do servidor NFS a auditoria não pode ser lida (os eventos ficam em espera). "
        "GlusterFS ou CephFS dariam replicação.",
        "**Sem replicação dos nós regionais.** A queda de um nó impede as transferências dessa região até ele voltar. "
        "Uma réplica em streaming por região aumentaria a disponibilidade das leituras.",
        "**Uma só moeda (EUR)** e sem conversão cambial.",
        "**Dados em repouso sem cifragem de disco** e NFS sem autenticação forte (secção 5.5).",
        "**Sem balanceador de carga:** o failover é feito pelo cliente; em produção usar-se-ia um balanceador replicado.",
        "**Dois computadores:** a configuração foi ensaiada num só computador (evidência 13); a prova com duas "
        "máquinas físicas não foi feita e segue o procedimento de `docs/DOIS_COMPUTADORES.md`.",
    ])

    H1("9. Conclusão")
    par(doc, "O protótipo cumpre as quatro partes do enunciado. A transferência entre contas em nós diferentes é atómica "
             "porque usa o 2PC sobre transacções preparadas reais, com a decisão gravada antes de ser comunicada e "
             "repetida até todos os nós a aplicarem; os testes derrubaram cada participante e o coordenador em cada fase "
             "e, no fim, a soma de todos os saldos manteve-se e cada transferência tinha exactamente um débito e um "
             "crédito. O trabalho também mostrou na prática dois problemas clássicos dos sistemas distribuídos: o "
             "bloqueio mútuo distribuído, resolvido com uma ordem global de aquisição, e o bloqueio do 2PC quando o "
             "coordenador falha, que é o preço da consistência forte escolhida.")

    # ---------------------------------------------------------------- referencias
    H1("Referências")
    refs = [
        "[E] ISUTC. Exame Normal Prático Laboratorial — Global-Scale System. Sistemas Distribuídos e Paralelos, LECC, 2026.",
        "[1] M. van Steen e A. S. Tanenbaum. Distributed Systems, 4.ª ed. distributed-systems.net, 2023. https://www.distributed-systems.net/index.php/books/ds4/",
        "[2] PostgreSQL Global Development Group. PREPARE TRANSACTION. PostgreSQL 17 Documentation. https://www.postgresql.org/docs/17/sql-prepare-transaction.html",
        "[3] PostgreSQL 17 Documentation. Resource Consumption: max_prepared_transactions. https://www.postgresql.org/docs/17/runtime-config-resource.html",
        "[4] PostgreSQL 17 Documentation. pg_prepared_xacts. https://www.postgresql.org/docs/17/view-pg-prepared-xacts.html",
        "[5] PostgreSQL 17 Documentation. COMMIT PREPARED. https://www.postgresql.org/docs/17/sql-commit-prepared.html",
        "[6] PostgreSQL 17 Documentation. libpq: SSL Support. https://www.postgresql.org/docs/17/libpq-ssl.html",
        "[7] PostgreSQL 17 Documentation. The pg_hba.conf File. https://www.postgresql.org/docs/17/auth-pg-hba-conf.html",
        "[8] Psycopg 3 Documentation. Connection pools. https://www.psycopg.org/psycopg3/docs/advanced/pool.html",
        "[9] Psycopg 3 Documentation. Transactions management (two-phase commit). https://www.psycopg.org/psycopg3/docs/basic/transactions.html",
        "[10] Docker. Install Docker Desktop on Windows. https://docs.docker.com/desktop/setup/install/windows-install/",
        "[11] Docker. Compose file reference: services. https://docs.docker.com/reference/compose-file/services/",
        "[12] Docker. Manage secrets securely in Docker Compose. https://docs.docker.com/compose/how-tos/use-secrets/",
        "[13] Python Software Foundation. Glossary: global interpreter lock. https://docs.python.org/3/glossary.html",
        "[14] OWASP. Password Storage Cheat Sheet. https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html",
        "[15] M. Jones, J. Bradley e N. Sakimura. RFC 7519: JSON Web Token (JWT). IETF, 2015.",
        "[16] M. Jones. RFC 7518: JSON Web Algorithms (JWA). IETF, 2015.",
        "[17] K. Moriarty et al. RFC 8017: PKCS #1: RSA Cryptography Specifications Version 2.2. IETF, 2016.",
        "[18] Object Management Group. Common Object Request Broker Architecture (CORBA), versão 3.4. https://www.omg.org/spec/CORBA/",
        "[19] R. T. Fielding. Architectural Styles and the Design of Network-based Software Architectures, cap. 5. "
        "Universidade da Califórnia, Irvine, 2000. https://ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm",
        "[20] NFS-Ganesha. https://github.com/nfs-ganesha/nfs-ganesha",
    ]
    for r in refs:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.6)
        p.paragraph_format.first_line_indent = Cm(-0.6)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(r)
        run.font.size = Pt(9.5)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    run = p.add_run(f"Todas as páginas Web foram consultadas em Novembro de 2026.")
    run.italic = True
    run.font.size = Pt(9)


def main():
    ev = carregar_evidencias()
    CONSTRUIR.mkdir(parents=True, exist_ok=True)
    logo = str(CONSTRUIR / "logo.png")
    pathlib.Path(logo).write_bytes((AQUI / "isutc.png").read_bytes())
    fig = {"arq": png_de_svg(SVG_ARQ, "arquitectura"), "2pc": png_de_svg(SVG_2PC, "sequencia_2pc")}

    doc = Document()
    configurar_estilos(doc)
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.left_margin = s.right_margin = Cm(2.2)
    s.top_margin = Cm(2.0)
    s.bottom_margin = Cm(1.8)
    s.different_first_page_header_footer = True
    contorno_primeira_pagina(s)
    rodape = s.footer.paragraphs[0]
    rodape.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = rodape.add_run("Global-Scale System — Kenneth Dembele, LECC31  ·  página ")
    r.font.size = Pt(9)
    campo(rodape, "PAGE", "1")
    capa(doc, logo)
    conteudo(doc, fig, ev)
    destino = pathlib.Path(os.environ.get("GS_RELATORIO", RAIZ / "docs" / "Relatorio_Tecnico_Global-Scale.docx"))
    doc.save(str(destino))
    print(destino, f"({len(ev)} evidencias)")


if __name__ == "__main__":
    main()
