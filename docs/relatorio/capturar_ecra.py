"""Capturas de ecra reais para o relatorio: abre janelas neste PC, corre os comandos e fotografa a janela.

    python docs/relatorio/capturar_ecra.py cenarios     # 13 cenarios, uma janela de PowerShell cada
    python docs/relatorio/capturar_ecra.py extras       # ambiente, testes, cliente, Swagger (Edge), Docker Desktop
    python docs/relatorio/capturar_ecra.py dois_pcs     # ensaio dos dois PCs (o sistema principal tem de estar parado)
    python docs/relatorio/capturar_ecra.py teste        # uma janela de teste

As imagens ficam em docs/relatorio/capturas/. So se fotografam as janelas abertas por este script
(PrintWindow da API do Windows), nunca o ecra inteiro, para nao apanhar outras janelas do utilizador.
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
CAPTURAS = AQUI / "capturas"
EDGE = os.environ.get("EDGE", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
DOCKER_BIN = r"D:\Docker\Programa\resources\bin"

ctypes.windll.shcore.SetProcessDpiAwareness(2)          # coordenadas e capturas em pixeis fisicos
user32, gdi32, dwm = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.dwmapi


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


def procurar_janela(texto: str, exacto=False, timeout=90) -> int:
    encontradas = []
    PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def ver(h, _):
        if user32.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(h, buf, 512)
            if (buf.value == texto) if exacto else (texto in buf.value):
                encontradas.append(h)
        return True
    fim = time.time() + timeout
    while time.time() < fim:
        encontradas.clear()
        user32.EnumWindows(PROC(ver), 0)
        if encontradas:
            return encontradas[0]
        time.sleep(0.4)
    raise TimeoutError(f"janela nao encontrada: {texto}")


def fotografar(hwnd: int, destino: Path, cortar_fundo=False) -> Path:
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    dc_janela = user32.GetWindowDC(hwnd)
    dc = gdi32.CreateCompatibleDC(dc_janela)
    bmp = gdi32.CreateCompatibleBitmap(dc_janela, w, h)
    gdi32.SelectObject(dc, bmp)
    user32.PrintWindow(hwnd, dc, 2)                       # PW_RENDERFULLCONTENT
    bih = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(dc, bmp, 0, h, buf, ctypes.byref(bih), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(dc)
    user32.ReleaseDC(hwnd, dc_janela)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    moldura = wt.RECT()                                   # sem a moldura invisivel do Windows 10
    if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(moldura), ctypes.sizeof(moldura)) == 0:
        img = img.crop((moldura.left - r.left, moldura.top - r.top, moldura.right - r.left, moldura.bottom - r.top))
    if cortar_fundo:                                      # consola: corta as linhas vazias do fim
        conteudo = img.crop((0, 0, img.width - 80, img.height)).convert("L").point(lambda v: 255 if v > 70 else 0)
        caixa = conteudo.getbbox()
        if caixa:
            img = img.crop((0, 0, img.width, min(img.height, caixa[3] + 40)))
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    print(f"  {destino.name}: {img.width}x{img.height}")
    return destino


def ambiente(extra=None) -> dict:
    env = dict(os.environ)
    env["PATH"] = DOCKER_BIN + os.pathsep + env.get("PATH", "")
    env.update(extra or {})
    return env


def terminal(titulo: str, comando: str, destino: Path, colunas=124, linhas=80, fonte=10, timeout=900, extra_env=None):
    """Abre uma janela de PowerShell, corre o comando (varios separados por ;;) e fotografa a janela."""
    marcador = Path(tempfile.gettempdir()) / f"gs-captura-{uuid.uuid4().hex}.ok"
    p = subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(AQUI / "terminal.ps1"),
                          "-Titulo", titulo, "-Comando", comando, "-Marcador", str(marcador), "-Colunas", str(colunas),
                          "-Linhas", str(linhas), "-Fonte", str(fonte)],
                         creationflags=subprocess.CREATE_NEW_CONSOLE, env=ambiente(extra_env))
    try:
        h = procurar_janela(titulo, exacto=True)
        user32.SetWindowPos(h, 0, 0, 0, 0, 0, 0x0001 | 0x0004)      # canto superior esquerdo, sem mudar o tamanho
        fim = time.time() + timeout
        while not marcador.exists() and time.time() < fim:
            time.sleep(0.5)
        time.sleep(1.2)
        try:
            usadas, visiveis = (int(x) for x in marcador.read_text(encoding="utf-8-sig").split())
        except (OSError, ValueError):
            usadas, visiveis = 0, 1
        if usadas < visiveis:                                       # coube tudo numa imagem
            return fotografar(h, destino, cortar_fundo=True)
        # Nao coube: fotografa o fim, pede a janela rolada ate ao inicio e fotografa o inicio.
        fotografar(h, destino.with_name(destino.stem + "_2" + destino.suffix))
        Path(str(marcador) + ".topo").write_text("ok")
        while not Path(str(marcador) + ".topo.ok").exists() and time.time() < fim:
            time.sleep(0.3)
        time.sleep(1.0)
        return fotografar(h, destino.with_name(destino.stem + "_1" + destino.suffix))
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        for f in (marcador, Path(str(marcador) + ".topo"), Path(str(marcador) + ".topo.ok")):
            f.unlink(missing_ok=True)


def edge(url: str, texto_titulo: str, destino: Path, espera=5):
    perfil = tempfile.mkdtemp(prefix="gs-edge-")
    # O Edge nao conhece a CA do laboratorio: so nesta captura ignora o erro do certificado.
    p = subprocess.Popen([EDGE, f"--user-data-dir={perfil}", "--no-first-run", "--no-default-browser-check",
                          "--ignore-certificate-errors", "--test-type", "--inprivate", "--force-device-scale-factor=1.25", "--disable-features=msEdgeOnRampFRE,msWelcomePage",
                          "--new-window", "--window-position=0,0",
                          "--window-size=1280,680", url])
    try:
        h = procurar_janela(texto_titulo)
        time.sleep(espera)
        return fotografar(h, destino)
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)


def docker_desktop(destino: Path):
    subprocess.Popen([r"D:\Docker\Programa\Docker Desktop.exe"])      # abre o painel (vista Containers)
    h = procurar_janela("Containers - Docker Desktop")
    user32.ShowWindow(h, 9)                                          # SW_RESTORE
    user32.SetWindowPos(h, 0, 0, 0, 3200, 1700, 0x0004)              # 1280x680 logicos a 250 %
    time.sleep(6)
    return fotografar(h, destino)


def cenarios():
    for n in range(13):
        terminal(f"Global-Scale - cenario {n}", f"python testes/cenarios.py {n}", CAPTURAS / f"cenario_{n:02d}.png",
                 extra_env={"GS_MOSTRAR": "1"})


def extras():
    terminal("Global-Scale - ambiente", "docker compose ps --format 'table {{.Name}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' ;; "
             "docker network inspect global-scale_interna --format '{{range .Containers}}{{.IPv4Address}}  {{.Name}}{{println}}{{end}}' ;; "
             "docker network inspect global-scale_frontal --format '{{range .Containers}}{{.IPv4Address}}  {{.Name}}{{println}}{{end}}'",
             CAPTURAS / "ambiente.png")
    terminal("Global-Scale - testes unitarios", "python -m pytest testes/unitarios -v -p no:cacheprovider",
             CAPTURAS / "testes_unitarios.png")
    terminal("Global-Scale - cliente", "python scripts/cliente.py -u ana -p 'Ana#2026' saldo EU-1001 ;; "
             "python scripts/cliente.py -u ana -p 'Ana#2026' transferir EU-1001 US-2001 25.00",
             CAPTURAS / "cliente_transferencia.png", linhas=70)
    edge("https://localhost:8001/docs#/", "Swagger UI", CAPTURAS / "swagger_edge.png", espera=8)
    try:
        docker_desktop(CAPTURAS / "docker_desktop.png")
    except Exception as e:
        print("  Docker Desktop nao capturado:", e)


def dois_pcs():
    terminal("Global-Scale - ensaio de dois PCs", "python testes/ensaio_distribuido.py", CAPTURAS / "ensaio_dois_pcs.png",
             linhas=70, timeout=1500)


if __name__ == "__main__":
    accao = sys.argv[1] if len(sys.argv) > 1 else "teste"
    if accao == "teste":
        terminal("Global-Scale - teste", "docker compose ps --format 'table {{.Name}}\t{{.Status}}'", CAPTURAS / "teste.png")
    else:
        {"cenarios": cenarios, "extras": extras, "dois_pcs": dois_pcs}[accao]()
