"""Montantes: o JSON traz texto decimal ("125.50"); internamente usam-se centimos inteiros.

Nunca se usa float: 0.1 + 0.2 != 0.3 em virgula flutuante binaria.
"""
from decimal import Decimal, InvalidOperation

MAXIMO_CENTIMOS = 100_000_000_00   # 100 milhoes por transferencia (limite da demonstracao)


class MontanteInvalido(ValueError):
    pass


def para_centimos(texto: str) -> int:
    if not isinstance(texto, str):
        raise MontanteInvalido("o montante deve ser texto decimal, por exemplo \"125.50\"")
    try:
        valor = Decimal(texto.strip())
    except InvalidOperation:
        raise MontanteInvalido(f"montante invalido: {texto!r}") from None
    if not valor.is_finite():
        raise MontanteInvalido("montante invalido")
    if valor <= 0:
        raise MontanteInvalido("o montante tem de ser positivo")
    if valor.as_tuple().exponent < -2:
        raise MontanteInvalido("o montante tem no maximo 2 casas decimais")
    centimos = int(valor * 100)
    if centimos > MAXIMO_CENTIMOS:
        raise MontanteInvalido("montante acima do limite por transferencia")
    return centimos


def formatar(centimos: int) -> str:
    sinal = "-" if centimos < 0 else ""
    centimos = abs(centimos)
    return f"{sinal}{centimos // 100}.{centimos % 100:02d}"
