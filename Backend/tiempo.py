"""Fechas y rangos en la zona horaria del negocio.

Antes el "día" se calculaba con una resta fija de seis horas (UTC-6), lo que
ignoraba la zona configurable y fallaba con el horario de verano. Aquí todo
se resuelve con ``zoneinfo`` y se devuelve en UTC para consultar la base.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ZONA_POR_DEFECTO = "America/Managua"


def zona(nombre: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(nombre or ZONA_POR_DEFECTO)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return ZoneInfo(ZONA_POR_DEFECTO)


def ahora_local(nombre: str | None = None) -> datetime:
    return datetime.now(zona(nombre))


def hoy_local(nombre: str | None = None) -> date:
    return ahora_local(nombre).date()


def fecha_de(valor: str | date | None, nombre: str | None = None) -> date:
    """Acepta YYYY-MM-DD o date; si falta, usa el día local de hoy."""
    if isinstance(valor, date):
        return valor
    if not valor:
        return hoy_local(nombre)
    return datetime.strptime(str(valor), "%Y-%m-%d").date()


def rango_dia(dia: date, nombre: str | None = None) -> tuple[datetime, datetime]:
    """Instantes UTC que delimitan un día completo en la zona del negocio."""
    tz = zona(nombre)
    inicio_local = datetime.combine(dia, time.min, tzinfo=tz)
    fin_local = datetime.combine(dia + timedelta(days=1), time.min, tzinfo=tz)
    return inicio_local.astimezone(timezone.utc), fin_local.astimezone(timezone.utc)


def rango_periodo(desde: date, hasta: date, nombre: str | None = None) -> tuple[datetime, datetime]:
    """Rango inclusivo por día, expresado en instantes UTC."""
    tz = zona(nombre)
    inicio = datetime.combine(desde, time.min, tzinfo=tz)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=tz)
    return inicio.astimezone(timezone.utc), fin.astimezone(timezone.utc)


def a_local(fecha_hora: datetime, nombre: str | None = None) -> datetime:
    """Normaliza un datetime (posiblemente naive) y lo lleva a la zona dada."""
    if fecha_hora.tzinfo is None:
        fecha_hora = fecha_hora.replace(tzinfo=timezone.utc)
    return fecha_hora.astimezone(zona(nombre))
