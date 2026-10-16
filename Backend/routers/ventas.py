from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import joinedload

from Backend.db.database import get_db
from Backend.db.models import Cliente, Movimiento, Producto, Venta, VentaItem
from Backend.models.schema import VentaCrear
from Backend.routers.auth import verificar_token

router = APIRouter(prefix="/ventas", tags=["Ventas"])

MAX_VENTAS_LISTADAS = 1000


def _calcular_precio_final(p: Producto, cantidad: int, precio_unitario: float) -> tuple[float, str]:
    """Devuelve (subtotal, nota_promocion) usando el precio unitario indicado."""
    if not p.promocion or not p.promocion.activa:
        return precio_unitario * cantidad, ""
    promo = p.promocion
    if promo.tipo == "porcentaje":
        desc = precio_unitario * cantidad * (promo.valor / 100)
        return precio_unitario * cantidad - desc, f"desc. {promo.valor}%"
    elif promo.tipo == "2x1":
        gratis = cantidad // 2
        pagar = cantidad - gratis
        return pagar * precio_unitario, "2x1"
    elif promo.tipo == "monto_fijo":
        total = precio_unitario * cantidad
        desc = min(promo.valor, total)
        return total - desc, f"C${promo.valor:.0f} desc."
    return precio_unitario * cantidad, ""


@router.post("/")
def crear_venta(venta: VentaCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        # Primero se resuelven y validan todos los productos: o entra la venta
        # completa, o no entra nada.
        resueltos = []
        for item in venta.items:
            p = session.query(Producto).options(
                joinedload(Producto.promocion)
            ).filter(
                Producto.id == item.producto_id,
                Producto.usuario_id == usuario_id
            ).first()

            if not p:
                raise HTTPException(status_code=404, detail=f"Producto {item.producto_id} no encontrado")
            if p.stock < item.cantidad:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para producto {item.producto_id}")

            # El precio sale siempre de la BD, nunca del cuerpo de la petición.
            precio = float(p.precio or 0.0)
            subtotal, nota = _calcular_precio_final(p, item.cantidad, precio)
            resueltos.append((p, item.cantidad, precio, subtotal, nota))

        total = sum(r[3] for r in resueltos)
        promos_aplicadas = [f"{r[0].nombre}: {r[4]}" for r in resueltos if r[4]]

        if venta.metodo_pago == "credito":
            if not venta.cliente_id:
                raise HTTPException(status_code=400, detail="Una venta a crédito requiere un cliente")
            c = session.query(Cliente).filter(
                Cliente.id == venta.cliente_id,
                Cliente.usuario_id == usuario_id
            ).first()
            if not c:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")

            disponible = (c.credito_limite or 0.0) - (c.credito_usado or 0.0)
            if total > disponible:
                raise HTTPException(status_code=400, detail="Crédito insuficiente")
        elif venta.cliente_id:
            existe_cliente = session.query(Cliente).filter(
                Cliente.id == venta.cliente_id,
                Cliente.usuario_id == usuario_id
            ).first()
            if not existe_cliente:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")

        v = Venta(
            usuario_id=usuario_id,
            cliente_id=venta.cliente_id,
            total=total,
            metodo_pago=venta.metodo_pago,
        )
        session.add(v)
        session.flush()
        venta_id = v.id

        for p, cantidad, precio, _subtotal, _nota in resueltos:
            session.add(VentaItem(
                venta_id=venta_id,
                producto_id=p.id,
                cantidad=cantidad,
                precio_unitario=precio,
            ))
            session.query(Producto).filter(
                Producto.id == p.id,
                Producto.usuario_id == usuario_id
            ).update({Producto.stock: Producto.stock - cantidad})
            session.add(Movimiento(producto_id=p.id, tipo="salida", cantidad=cantidad))

        if venta.metodo_pago == "credito":
            session.query(Cliente).filter(
                Cliente.id == venta.cliente_id,
                Cliente.usuario_id == usuario_id
            ).update({Cliente.credito_usado: Cliente.credito_usado + total})

        return {"id": venta_id, "total": total, "promos_aplicadas": promos_aplicadas}


@router.delete("/{id}")
def anular_venta(id: int, usuario_id: int = Depends(verificar_token)):
    """Anula una venta: devuelve el stock, revierte el crédito y borra el registro."""
    with get_db() as session:
        v = session.query(Venta).filter(
            Venta.id == id,
            Venta.usuario_id == usuario_id
        ).first()
        if not v:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        items = session.query(VentaItem).filter(VentaItem.venta_id == v.id).all()

        for it in items:
            if it.producto_id is None:
                continue
            session.query(Producto).filter(
                Producto.id == it.producto_id,
                Producto.usuario_id == usuario_id
            ).update({Producto.stock: Producto.stock + it.cantidad})
            session.add(Movimiento(
                producto_id=it.producto_id, tipo="entrada", cantidad=it.cantidad
            ))

        if v.metodo_pago == "credito" and v.cliente_id:
            session.query(Cliente).filter(
                Cliente.id == v.cliente_id,
                Cliente.usuario_id == usuario_id
            ).update({
                Cliente.credito_usado: Cliente.credito_usado - v.total
            })

        session.query(VentaItem).filter(VentaItem.venta_id == v.id).delete()
        session.query(Venta).filter(
            Venta.id == v.id,
            Venta.usuario_id == usuario_id
        ).delete()

        return {"mensaje": "Venta anulada y stock restaurado"}


def _rango_del_dia(d) -> tuple[datetime, datetime]:
    inicio = datetime(d.year, d.month, d.day, 6, 0, 0, tzinfo=timezone.utc)
    return inicio, inicio + timedelta(days=1)


def _parsear_fecha(fecha: str | None):
    if not fecha:
        return (datetime.now(timezone.utc) - timedelta(hours=6)).date()
    try:
        return datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido, use YYYY-MM-DD")


@router.get("/resumen-dia")
def resumen_dia(usuario_id: int = Depends(verificar_token), fecha: str = Query(default=None, max_length=10)):
    with get_db() as session:
        inicio, fin = _rango_del_dia(_parsear_fecha(fecha))

        resumen = session.execute(
            text("""
                SELECT COUNT(*) as numero_ventas, COALESCE(SUM(total), 0) as total_ventas
                FROM ventas
                WHERE usuario_id = :uid AND fecha_hora >= :inicio AND fecha_hora < :fin
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin}
        ).mappings().first()

        ultimas = session.execute(
            text("""
                SELECT
                    v.id,
                    v.total,
                    v.fecha_hora,
                    v.metodo_pago,
                    c.nombre as cliente_nombre,
                    (
                        SELECT STRING_AGG(p.nombre || ' (x' || vi.cantidad || ')', ', ')
                        FROM venta_items vi
                        JOIN productos p ON vi.producto_id = p.id
                        WHERE vi.venta_id = v.id
                    ) as productos
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.usuario_id = :uid AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin
                ORDER BY v.fecha_hora DESC
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin}
        ).mappings().fetchall()

        return {
            "numero_ventas": resumen["numero_ventas"],
            "total_ventas": resumen["total_ventas"],
            "ultimas_ventas": [dict(u) for u in ultimas],
        }


@router.get("/")
def listar_ventas(
    usuario_id: int = Depends(verificar_token),
    limite: int = Query(default=200, ge=1, le=MAX_VENTAS_LISTADAS),
):
    with get_db() as session:
        ventas = session.execute(
            text("""
                SELECT v.id, v.total, v.fecha_hora, v.metodo_pago, c.nombre as cliente_nombre
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.usuario_id = :uid
                ORDER BY v.fecha_hora DESC
                LIMIT :limite
            """),
            {"uid": usuario_id, "limite": limite}
        ).mappings().fetchall()
        return [dict(v) for v in ventas]


@router.get("/{id}")
def obtener_venta(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        v = session.execute(
            text("""
                SELECT v.id, v.total, v.fecha_hora, v.metodo_pago, c.nombre as cliente_nombre
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.id = :vid AND v.usuario_id = :uid
            """),
            {"vid": id, "uid": usuario_id}
        ).mappings().first()

        if not v:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        items = session.execute(
            text("""
                SELECT p.nombre, vi.cantidad, vi.precio_unitario,
                       (vi.cantidad * vi.precio_unitario) AS subtotal
                FROM venta_items vi
                JOIN productos p ON vi.producto_id = p.id
                JOIN ventas v ON vi.venta_id = v.id
                WHERE vi.venta_id = :vid AND v.usuario_id = :uid
            """),
            {"vid": id, "uid": usuario_id}
        ).mappings().fetchall()

        return {**dict(v), "items": [dict(i) for i in items]}
