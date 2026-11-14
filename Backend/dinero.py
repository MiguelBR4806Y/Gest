"""Aritmética monetaria exacta.

Todo importe del sistema se calcula con ``Decimal`` y se redondea a dos
decimales con ``ROUND_HALF_UP`` (el criterio comercial habitual, no el
bancario). En la base de datos las columnas son ``NUMERIC(12, 2)``; el
``float`` solo aparece en el borde HTTP, al serializar para JSON.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable

CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")
CIEN = Decimal("100")
DIEZMIL = Decimal("0.0001")


def tasa_cambio(valor) -> Decimal:
    """La tasa se guarda con cuatro decimales; no se redondea a centavos."""
    if valor is None or valor == "":
        return CERO
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return CERO
    if not numero.is_finite():
        return CERO
    return numero.quantize(DIEZMIL, rounding=ROUND_HALF_UP)


def dinero(valor) -> Decimal:
    """Convierte cualquier entrada numérica a un Decimal de dos decimales."""
    if valor is None or valor == "":
        return CERO
    if isinstance(valor, Decimal):
        numero = valor
    else:
        try:
            numero = Decimal(str(valor))
        except (InvalidOperation, ValueError, TypeError):
            return CERO
    if not numero.is_finite():
        return CERO
    return numero.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def multiplicar(precio, cantidad) -> Decimal:
    """Importe de una línea: precio unitario por cantidad entera."""
    return dinero(dinero(precio) * int(cantidad))


def sumar(valores: Iterable) -> Decimal:
    total = CERO
    for v in valores:
        total += dinero(v)
    return dinero(total)


def restar(a, b) -> Decimal:
    return dinero(dinero(a) - dinero(b))


def porcentaje(base, pct) -> Decimal:
    return dinero(dinero(base) * dinero(pct) / CIEN)


def dividir(a, b) -> Decimal:
    """División protegida: devuelve cero si el divisor es cero."""
    divisor = dinero(b) if not isinstance(b, Decimal) else b
    if divisor == 0:
        return CERO
    return dinero(Decimal(str(a)) / Decimal(str(divisor)))


def a_float(valor) -> float:
    """Salida JSON. El redondeo ya está hecho, así que es seguro."""
    return float(dinero(valor))


def a_texto(valor, decimales: int = 2) -> str:
    """Formato con separador de miles para PDFs y CSV."""
    d = dinero(valor)
    return f"{d:,.{decimales}f}"
