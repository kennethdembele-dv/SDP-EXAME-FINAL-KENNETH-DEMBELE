"""Percorre a interface Web num Microsoft Edge real (Playwright) e grava capturas de ecra para o relatorio.

    python docs/relatorio/capturar_interface.py            # vistas normais
    python docs/relatorio/capturar_interface.py --falhas   # tambem a demonstracao de falha (para e arranca db-america)

As imagens ficam em docs/relatorio/capturas/ui_*.png. Erros de JavaScript fazem o script terminar com erro.
O Edge do laboratorio nao conhece a CA do projecto, por isso esta janela ignora o aviso do certificado.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
CAPTURAS = Path(__file__).resolve().parent / "capturas"
URL = "https://localhost:8001/"
DOCKER = r"D:\Docker\Programa\resources\bin\docker.exe"
erros: list[str] = []


def compose(*args):
    subprocess.run([DOCKER, "compose", *args], cwd=RAIZ, capture_output=True, timeout=300)


def foto(pagina, nome, pagina_inteira=False):
    time.sleep(0.8)
    destino = CAPTURAS / f"ui_{nome}.png"
    pagina.screenshot(path=str(destino), full_page=pagina_inteira)
    print("  ", destino.name)


def main():
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="msedge", headless=False, args=["--start-maximized"])
        ctx = navegador.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 1000}, device_scale_factor=2,
                                    locale="pt-PT")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
        # Respostas HTTP de erro esperadas (por exemplo 422 do saldo insuficiente) nao sao erros de JavaScript.
        pg.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text
              and erros.append(f"console: {m.text}"))

        pg.goto(URL)
        pg.wait_for_selector("#entrada:not([hidden])")
        foto(pg, "01_entrada")
        pg.click("text=ana")                                    # botao de demonstracao
        pg.wait_for_selector("#app:not([hidden])")
        pg.wait_for_function("document.getElementById('k-saldo').textContent.includes('€')")
        pg.wait_for_timeout(2500)
        foto(pg, "02_painel")

        pg.click("#menu a[data-vista=contas]")
        pg.wait_for_selector(".cartao-conta")
        pg.wait_for_timeout(1500)
        foto(pg, "03_contas")

        pg.click("#menu a[data-vista=transferir]")
        pg.select_option("#t-origem", "EU-1001")
        pg.fill("#t-destino", "US-2001")
        pg.fill("#t-montante", "250,00")
        pg.click("#b-transferir")
        pg.wait_for_selector("#t-linha .resumo-transf")
        pg.wait_for_function("document.querySelector('#t-linha').textContent.includes('BP-')", timeout=30000)
        foto(pg, "04_transferencia_2pc")

        pg.click("#b-repetir")                                  # mesma chave: idempotencia
        pg.wait_for_selector("text=repetido (idempotência)")
        foto(pg, "05_idempotencia")

        pg.wait_for_selector("#aviso", state="hidden", timeout=10000)
        pg.click("#t-linha [data-detalhe]")
        pg.wait_for_selector("#gaveta:not([hidden]) #g-b-parceiro")
        pg.click("#g-b-parceiro")
        pg.wait_for_selector("#g-parceiro pre")
        pg.click("#g-b-auditoria")
        pg.wait_for_selector("#g-auditoria table")
        pg.wait_for_timeout(800)
        pg.locator(".gaveta-painel").screenshot(path=str(CAPTURAS / "ui_06_detalhe_xml_auditoria.png"))
        print("   ui_06_detalhe_xml_auditoria.png")
        pg.keyboard.press("Escape")

        pg.select_option("#t-origem", "EU-1001")
        pg.fill("#t-destino", "US-2002")
        pg.fill("#t-montante", "999999")
        pg.click("#b-nova-chave")
        pg.click("#b-transferir")
        pg.wait_for_selector("#t-linha .e-ABORTADA")
        foto(pg, "07_saldo_insuficiente")

        pg.click("#menu a[data-vista=transferencias]")
        pg.wait_for_selector("#m-tabela table")
        foto(pg, "08_monitor_2pc")

        pg.click("#menu a[data-vista=relatorios]")
        pg.click("#b-gerar")
        pg.wait_for_selector("#r-conteudo table")
        foto(pg, "09_relatorios_dfs")

        pg.click("#menu a[data-vista=sistema]")
        pg.wait_for_selector("#s-topologia .no")
        pg.wait_for_timeout(1500)
        foto(pg, "10_sistema")

        pg.click("#menu a[data-vista=seguranca]")
        pg.wait_for_selector("#j-claims dl")
        foto(pg, "11_seguranca")

        if "--falhas" in sys.argv:
            # Falha de um no: o painel mostra-o a vermelho e a transferencia aborta sem mexer em saldos.
            compose("stop", "db-america")
            pg.click("#menu a[data-vista=sistema]")
            pg.wait_for_selector("#s-topologia .no.falha", timeout=30000)
            pg.wait_for_timeout(1500)
            foto(pg, "12_sistema_no_em_baixo")
            pg.click("#menu a[data-vista=transferir]")
            pg.select_option("#t-origem", "EU-1001")
            pg.fill("#t-destino", "US-2001")
            pg.fill("#t-montante", "10,00")
            pg.click("#b-nova-chave")
            pg.click("#b-transferir")
            pg.wait_for_selector("#t-linha .e-ABORTADA", timeout=40000)
            foto(pg, "13_transferencia_no_em_baixo")
            compose("start", "db-america")
            pg.click("#menu a[data-vista=sistema]")
            pg.wait_for_function("!document.querySelector('#s-topologia .no.falha')", timeout=90000)
            foto(pg, "14_sistema_recuperado")

        navegador.close()
    if erros:
        print("ERROS DE JAVASCRIPT:\n" + "\n".join(erros))
        sys.exit(1)
    print("sem erros de JavaScript")


if __name__ == "__main__":
    main()
