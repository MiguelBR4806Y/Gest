"""Bitácora de auditoría.

Se escribe dentro de la misma transacción que la operación, así que un evento
nunca queda registrado si la operación falla, y viceversa.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from Backend.db.models import Evento
from Backend.security import sanear_texto


def registrar_evento(
    session: Session,
    usuario_id: int,
    tipo: str,
    entidad: str,
    entidad_id: int | None = None,
    detalle: str | None = None,
) -> None:
    session.add(
        Evento(
            usuario_id=usuario_id,
            tipo=tipo[:40],
            entidad=entidad[:40],
            entidad_id=entidad_id,
            detalle=sanear_texto(detalle, 500) or None,
        )
    )
