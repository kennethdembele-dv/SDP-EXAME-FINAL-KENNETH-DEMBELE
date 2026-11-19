"""Captura de ecra do Swagger (OpenAPI) da api-1 para o relatorio: evidencias/swagger.png.

    python scripts/capturar_swagger.py

Precisa do sistema a correr e do Microsoft Edge. O Edge nao conhece a CA do laboratorio, por isso
corre com --ignore-certificate-errors (so nesta captura; os servicos verificam sempre os certificados).
"""
import os
import subprocess
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EDGE = os.environ.get("EDGE", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
destino = RAIZ / "evidencias" / "swagger.png"
destino.unlink(missing_ok=True)
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                "--ignore-certificate-errors", f"--user-data-dir={tempfile.mkdtemp()}",
                "--window-size=1280,1500", "--virtual-time-budget=8000", f"--screenshot={destino}",
                "https://localhost:8001/docs"], capture_output=True, timeout=120)
for _ in range(120):
    if destino.exists() and destino.stat().st_size > 0:
        break
    time.sleep(0.25)
print(destino, destino.exists() and destino.stat().st_size)
