from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, update

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import Gasto, Proveedor, Usuario
from Backend.dinero import a_float, dinero
from Backend.models.schema import GastoCrear
from Backend.routers.auth import requiere_modulo, verificar_token
from Backend.tiempo import ZONA_POR_DEFECTO, fecha_de, rango_dia

router = APIRouter(
    prefix="/gastos",
    tags=["Gastos"],
    dependencies=[Depends(requiere_modulo("contabilidad"))],
)


def _serializar(g: Gasto, proveedor: str | None = None) -> dict:
    return {
        "id": g.id,
        "concepto": g.concepto,
        "categoria": g.categoria,
        "monto": a_float(g.monto),
        "proveedor_id": g.proveedor_id,
        "proveedor_nombre": proveedor,
        "compra_id": g.compra_id,
        "fecha": g.fecha.isoformat() if g.fecha else None,
        "creado_en": g.creado_en.isoformat() if g.creado_en else None,
    }


def _zona(session, usuario_id: int) -> str:
    return session.query(Usuario.zona_horaria).filter(
        Usuario.id == usuario_id
    ).scalar() or ZONA_POR_DEFECTO


def _rango(desde: str | None, hasta: str | None, zona: str):
    try:
        inicio = rango_dia(fecha_de(desde, zona), zona)[0] if desde else None
        fin = rango_dia(fecha_de(hasta, zona), zona)[1] if hasta else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas, use YYYY-MM-DD")
    if inicio and fin and fin < inicio:
        raise HTTPException(status_code=400, detail="La fecha final es anterior a la inicial")
    return inicio, fin


def _validar_proveedor(session, proveedor_id: int | None, usuario_id: int) -> int | None:
    if proveedor_id is None:
        return None
    existe = session.query(Proveedor.id).filter(
        Proveedor.id == proveedor_id,
        Proveedor.usuario_id == usuario_id,
    ).first()
    if not existe:
        raise HTTPException(status_code=400, detail="Proveedor no encontrado")
    return proveedor_id


@router.get("/")
def listar_gastos(
    usuario_id: int = Depends(verificar_token),
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
    categoria: str = Query(default=None, max_length=40),
):
    with get_db() as session:
        inicio, fin = _rango(desde, hasta, _zona(session, usuario_id))

        consulta = session.query(Gasto, Proveedor.nombre).outerjoin(
            Proveedor, Gasto.proveedor_id == Proveedor.id
        ).filter(Gasto.usuario_id == usuario_id)

        if inicio:
            consulta = consulta.filter(Gasto.fecha >= inicio)
        if fin:
            consulta = consulta.filter(Gasto.fecha < fin)
        if categoria:
            consulta = consulta.filter(Gasto.categoria == categoria.lower())

        filas = consulta.order_by(Gasto.fecha.desc()).limit(500).all()
        items = [_serializar(g, nombre) for g, nombre in filas]

        por_categoria = session.query(
            Gasto.categoria, func.count(Gasto.id), func.coalesce(func.sum(Gasto.monto), 0)
        ).filter(Gasto.usuario_id == usuario_id)
        if inicio:
            por_categoria = por_categoria.filter(Gasto.fecha >= inicio)
        if fin:
            por_categoria = por_categoria.filter(Gasto.fecha < fin)
        por_categoria = por_categoria.group_by(Gasto.categoria).order_by(
            func.sum(Gasto.monto).desc()
        ).all()

        return {
            "items": items,
            "total": a_float(sum((dinero(i["monto"]) for i in items), dinero(0))),
            "por_categoria": [
                {"categoria": nombre, "cantidad": cantidad, "total": a_float(total)}
                for nombre, cantidad, total in por_categoria
            ],
        }


@router.post("/", status_code=201)
def crear_gasto(datos: GastoCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        gasto = Gasto(
            usuario_id=usuario_id,
            concepto=datos.concepto,
            categoria=datos.categoria,
            monto=dinero(datos.monto),
            proveedor_id=_validar_proveedor(session, datos.proveedor_id, usuario_id),
            fecha=datos.fecha or datetime.now().astimezone(),
        )
        session.add(gasto)
        session.flush()
        registrar_evento(
            session, usuario_id, "gasto_registrado", "gasto", gasto.id,
            f"{gasto.concepto} C${gasto.monto}",
        )
        return _serializar(gasto)


@router.put("/{id}")
def editar_gasto(id: int, datos: GastoCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        gasto = session.query(Gasto).filter(
            Gasto.id == id,
            Gasto.usuario_id == usuario_id,
        ).with_for_update().first()
        if not gasto:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        if gasto.compra_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Este gasto proviene de una compra; anula la compra en su lugar",
            )

        session.execute(
            update(Gasto)
            .where(Gasto.id == id, Gasto.usuario_id == usuario_id)
            .values(
                concepto=datos.concepto,
                categoria=datos.categoria,
                monto=dinero(datos.monto),
                proveedor_id=_validar_proveedor(session, datos.proveedor_id, usuario_id),
                fecha=datos.fecha or gasto.fecha,
            )
        )
        registrar_evento(session, usuario_id, "gasto_editado", "gasto", id, datos.concepto)
        session.refresh(gasto)
        return _serializar(gasto)


@router.delete("/{id}")
def eliminar_gasto(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        gasto = session.query(Gasto).filter(
            Gasto.id == id,
            Gasto.usuario_id == usuario_id,
        ).with_for_update().first()
        if not gasto:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        if gasto.compra_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Este gasto proviene de una compra; anula la compra en su lugar",
            )

        session.delete(gasto)
        registrar_evento(session, usuario_id, "gasto_eliminado", "gasto", id, gasto.concepto)
        return {"mensaje": "Gasto eliminado"}
