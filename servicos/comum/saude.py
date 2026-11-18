"""Verificacao de saude usada pelo Docker (healthcheck): GET HTTPS com a CA do laboratorio.

    python -m comum.saude https://localhost:8001/saude
"""
import ssl
import sys
import urllib.request

from comum import config

try:
    ctx = ssl.create_default_context(cafile=str(config.CA))
    with urllib.request.urlopen(sys.argv[1], context=ctx, timeout=3) as r:
        sys.exit(0 if r.status == 200 else 1)
except Exception as e:
    print(e)
    sys.exit(1)
