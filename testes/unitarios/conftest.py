import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "servicos"))
os.environ.setdefault("SEGREDOS", str(RAIZ / "segredos"))
os.environ.setdefault("SPOOL", str(RAIZ / "testes" / ".tmp-espera"))
