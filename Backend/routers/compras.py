"""Compras a proveedor.

Una compra sube el stock, recalcula el costo promedio ponderado del producto y
deja un gasto vinculado en la misma transacción. Anularla revierte el stock; el
costo promedio no se recalcula hacia atrás porque ya se usó para calcular
márgenes de ventas posteriores.
"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, update

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import Compra, CompraItem, Gasto, Movimiento, Producto, Proveedor, Usuario
from Backend.dinero import a_float, dinero, multiplicar, sumar
from Backend.models.schema import CompraCrear
from Backend.routers.auth import requiere_modulo, verificar_token
from Backend.tiempo import ZONA_POR_DEFECTO, fecha_de, rango_dia

router = APIRouter(
    prefix="/compras",
    tags=["Compras"],
    dependencies=[Depends(requiere_modulo("contabilidad"))],
)

MAX_COMPRAS_LISTADAS = 300


def _zona(session, usuario_id: int) -> str:
    return session.query(Usuario.zona_horaria).filter(
        Usuario.id == usuario_id
    ).scalar() or ZONA_POR_DEFECTO


def _numero(compra_id: int) -> str:
    return f"C-{compra_id:06d}"


def _serializar(c: Compra, proveedor: str | None, items: list[dict]) -> dict:
    return {
        "id": c.id,
        "numero": c.numero or _numero(c.id),
        "proveedor_id": c.proveedor_id,
        "proveedor_nombre": proveedor,
        "total": a_float(c.total),
        "estado": c.estado,
        "nota": c.nota,
        "fecha": c.fecha.isoformat() if c.fecha else None,
        "items": items,
    }


def _items_de(session, compra_id: int) -> list[dict]:
    filas = session.query(CompraItem, Producto.nombre).outerjoin(
        Producto, CompraItem.producto_id == Producto.id
    ).filter(CompraItem.compra_id == compra_id).all()
    return [
        {
            "producto_id": item.producto_id,
            "producto_nombre": nombre or "Producto eliminado",
            "cantidad": item.cantidad,
            "costo_unitario": a_float(item.costo_unitario),
            "subtotal": a_float(multiplicar(item.costo_unitario, item.cantidad)),
        }
        for item, nombre in filas
    ]


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
def listar_compras(
    usuario_id: int = Depends(verificar_token),
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
    proveedor_id: int | None = Query(default=None, gt=0),
):
    with get_db() as session:
        zona = _zona(session, usuario_id)
        consulta = session.query(Compra, Proveedor.nombre).outerjoin(
            Proveedor, Compra.proveedor_id == Proveedor.id
        ).filter(Compra.usuario_id == usuario_id)

        try:
            if desde:
                consulta = consulta.filter(
                    Compra.fecha >= rango_dia(fecha_de(desde, zona), zona)[0]
                )
            if hasta:
                consulta = consulta.filter(
                    Compra.fecha < rango_dia(fecha_de(hasta, zona), zona)[1]
                )
        except ValueError:
            raise HTTPException(status_code=400, detail="Fechas inválidas, use YYYY-MM-DD")

        if proveedor_id:
            consulta = consulta.filter(Compra.proveedor_id == proveedor_id)

        filas = consulta.order_by(Compra.fecha.desc()).limit(MAX_COMPRAS_LISTADAS).all()
        return {
            "items": [
                _serializar(c, nombre, _items_de(session, c.id)) for c, nombre in filas
            ],
            "total": len(filas),
        }


@router.get("/resumen/por-proveedor")
def resumen_por_proveedor(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        filas = session.query(
            Proveedor.id,
            Proveedor.nombre,
            func.count(Compra.id),
            func.coalesce(func.sum(Compra.total), 0),
        ).outerjoin(
            Compra,
            (Compra.proveedor_id == Proveedor.id) & (Compra.estado == "completada"),
        ).filter(Proveedor.usuario_id == usuario_id).group_by(
            Proveedor.id, Proveedor.nombre
        ).order_by(func.sum(Compra.total).desc()).all()

        return [
            {
                "proveedor_id": pid,
                "nombre": nombre,
                "compras": cantidad,
                "total": a_float(total),
            }
            for pid, nombre, cantidad, total in filas
        ]


@router.get("/{id}")
def obtener_compra(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        fila = session.query(Compra, Proveedor.nombre).outerjoin(
            Proveedor, Compra.proveedor_id == Proveedor.id
        ).filter(
            Compra.id == id,
            Compra.usuario_id == usuario_id,
        ).first()
        if not fila:
            raise HTTPException(status_code=404, detail="Compra no encontrada")
        compra, proveedor = fila
        return _serializar(compra, proveedor, _items_de(session, compra.id))


@router.post("/", status_code=201)
def crear_compra(datos: CompraCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        proveedor_id = _validar_proveedor(session, datos.proveedor_id, usuario_id)

        # Se agrupa por producto para que dos líneas del mismo artículo
        # calculen el promedio ponderado sobre la cantidad total, no por partes.
        agrupados: dict[int, tuple[int, Decimal]] = {}
        for item in datos.items:
            cantidad, costo = agrupados.get(item.producto_id, (0, Decimal("0")))
            nueva_cantidad = cantidad + item.cantidad
            valor_previo = multiplicar(costo, cantidad)
            costo_promedio = (
                valor_previo + multiplicar(dinero(item.costo_unitario), item.cantidad)
            ) / nueva_cantidad
            agrupados[item.producto_id] = (nueva_cantidad, dinero(costo_promedio))

        ids = sorted(agrupados)
        productos = session.query(Producto).filter(
            Producto.id.in_(ids),
            Producto.usuario_id == usuario_id,
        ).order_by(Producto.id).with_for_update(of=Producto).all()
        por_id = {p.id: p for p in productos}

        for producto_id in ids:
            if producto_id not in por_id:
                raise HTTPException(
                    status_code=404, detail=f"Producto {producto_id} no encontrado"
                )

        total = sumar(
            multiplicar(costo, cantidad) for cantidad, costo in agrupados.values()
        )

        compra = Compra(
            usuario_id=usuario_id,
            proveedor_id=proveedor_id,
            total=total,
            estado="completada",
            nota=datos.nota,
            fecha=datetime.now().astimezone(),
        )
        session.add(compra)
        session.flush()
        compra.numero = _numero(compra.id)

        for producto_id, (cantidad, costo_unitario) in agrupados.items():
            p = por_id[producto_id]
            stock_previo = int(p.stock or 0)
            costo_previo = dinero(p.costo)
            nuevo_stock = stock_previo + cantidad
            # Costo promedio ponderado: el valor del inventario anterior más
            # el de la compra, repartido entre las unidades resultantes.
            costo_nuevo = dinero(
                (multiplicar(costo_previo, stock_previo) + multiplicar(costo_unitario, cantidad))
                / nuevo_stock
            )

            resultado = session.execute(
                update(Producto)
                .where(Producto.id == p.id, Producto.usuario_id == usuario_id)
                .values(stock=Producto.stock + cantidad, costo=costo_nuevo)
            )
            if resultado.rowcount != 1:
                raise HTTPException(status_code=409, detail="No se pudo actualizar el stock")

            session.add(CompraItem(
                compra_id=compra.id,
                producto_id=p.id,
                cantidad=cantidad,
                costo_unitario=costo_unitario,
            ))
            session.add(Movimiento(producto_id=p.id, tipo="entrada", cantidad=cantidad))

        gasto = Gasto(
            usuario_id=usuario_id,
            proveedor_id=proveedor_id,
            compra_id=compra.id,
            concepto=f"Compra {compra.numero}",
            categoria="compra",
            monto=total,
            fecha=compra.fecha,
        )
        session.add(gasto)
        # Los items se consultan por SQL: hay que volcarlos antes de leerlos.
        session.flush()

        registrar_evento(
            session, usuario_id, "compra_registrada", "compra", compra.id,
            f"{compra.numero} total={total}",
        )
        nombre_proveedor = (
            _nombre_proveedor(session, proveedor_id) if proveedor_id else None
        )
        return _serializar(compra, nombre_proveedor, _items_de(session, compra.id))


def _nombre_proveedor(session, proveedor_id: int) -> str | None:
    return session.query(Proveedor.nombre).filter(Proveedor.id == proveedor_id).scalar()


@router.post("/{id}/anular")
def anular_compra(id: int, usuario_id: int = Depends(verificar_token)):
    """Revierte el stock. El costo promedio queda como está (ver docstring)."""
    with get_db() as session:
        compra = session.query(Compra).filter(
            Compra.id == id,
            Compra.usuario_id == usuario_id,
        ).with_for_update().first()
        if not compra:
            raise HTTPException(status_code=404, detail="Compra no encontrada")
        if compra.estado == "anulada":
            raise HTTPException(status_code=409, detail="La compra ya está anulada")

        items = session.query(CompraItem).filter(CompraItem.compra_id == compra.id).all()

        for item in items:
            resultado = session.execute(
                update(Producto)
                .where(
                    Producto.id == item.producto_id,
                    Producto.usuario_id == usuario_id,
                    Producto.stock >= item.cantidad,
                )
                .values(stock=Producto.stock - item.cantidad)
            )
            if resultado.rowcount != 1:
                raise HTTPException(
                    status_code=409,
                    detail="No hay stock suficiente para revertir esta compra: "
                           "parte de la mercancía ya se vendió",
                )
            session.add(Movimiento(
                producto_id=item.producto_id, tipo="salida", cantidad=item.cantidad
            ))

        compra.estado = "anulada"
        session.query(Gasto).filter(
            Gasto.compra_id == compra.id,
            Gasto.usuario_id == usuario_id,
        ).delete(synchronize_session=False)

        registrar_evento(
            session, usuario_id, "compra_anulada", "compra", compra.id, compra.numero
        )
        return {"mensaje": "Compra anulada; el stock fue restaurado", "id": compra.id}

