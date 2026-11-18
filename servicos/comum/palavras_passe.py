"""Hash de palavras-passe com scrypt (biblioteca padrao do Python).

scrypt e lento e usa muita memoria de proposito: torna caro testar milhoes de palavras-passe
se a tabela de utilizadores for roubada. Parametros N=2^14, r=8, p=5 (uma das configuracoes
recomendadas pela OWASP). Formato guardado: scrypt$N$r$p$sal_hex$hash_hex
"""
import hashlib
import hmac
import os

N, R, P = 2 ** 14, 8, 5


def gerar_hash(palavra_passe: str) -> str:
    sal = os.urandom(16)
    h = hashlib.scrypt(palavra_passe.encode(), salt=sal, n=N, r=R, p=P, dklen=32)
    return f"scrypt${N}${R}${P}${sal.hex()}${h.hex()}"


def verificar(palavra_passe: str, guardado: str) -> bool:
    try:
        algoritmo, n, r, p, sal, h = guardado.split("$")
    except ValueError:
        return False
    if algoritmo != "scrypt":
        return False
    calculado = hashlib.scrypt(palavra_passe.encode(), salt=bytes.fromhex(sal),
                               n=int(n), r=int(r), p=int(p), dklen=len(h) // 2)
    return hmac.compare_digest(calculado.hex(), h)   # comparacao em tempo constante


# Hash de uma palavra-passe que nao existe: usado quando o utilizador nao existe, para a
# resposta demorar o mesmo tempo e nao revelar quais os nomes validos.
HASH_FICTICIO = gerar_hash("utilizador-inexistente")
