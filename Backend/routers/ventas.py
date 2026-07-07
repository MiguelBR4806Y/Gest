from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import joinedload
from Backend.db.database import get_db
from Backend.db.models import Venta, VentaItem, Producto, Cliente, Movimiento, Promocion
from Backend.models.schema import VentaCrear
from Backend.routers.auth import verificar_token
from datetime import date, datetime, timezone, timedelta

router = APIRouter(prefix="/ventas", tags=["Ventas"])


def _calcular_precio_final(p: Producto, cantidad: int, precio_unitario: float) -> tuple[float, str]:
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
        total = 0
        promos_aplicadas = []
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

            subtotal, nota = _calcular_precio_final(p, item.cantidad, item.precio_unitario)
            total += subtotal
            if nota:
                promos_aplicadas.append(f"{p.nombre}: {nota}")

        if venta.cliente_id and venta.metodo_pago == "credito":
            c = session.query(Cliente).filter(
                Cliente.id == venta.cliente_id,
                Cliente.usuario_id == usuario_id
            ).first()

            if not c:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")

            disponible = c.credito_limite - c.credito_usado
            if total > disponible:
                raise HTTPException(status_code=400, detail="Crédito insuficiente")

        v = Venta(
            usuario_id=usuario_id,
            cliente_id=venta.cliente_id,
            total=total,
            metodo_pago=venta.metodo_pago,
        )
        session.add(v)
        session.flush()
        venta_id = v.id

        for item in venta.items:
            session.add(VentaItem(
                venta_id=venta_id,
                producto_id=item.producto_id,
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
            ))
            session.query(Producto).filter(Producto.id == item.producto_id).update({
                Producto.stock: Producto.stock - item.cantidad
            })
            session.add(Movimiento(
                producto_id=item.producto_id,
                tipo="salida",
                cantidad=item.cantidad,
            ))

        if venta.cliente_id and venta.metodo_pago == "credito":
            session.query(Cliente).filter(Cliente.id == venta.cliente_id).update({
                Cliente.credito_usado: Cliente.credito_usado + total
            })

        return {"id": venta_id, "total": total, "promos_aplicadas": promos_aplicadas}


@router.get("/resumen-dia")
def resumen_dia(usuario_id: int = Depends(verificar_token), fecha: str = Query(default=None)):
    with get_db() as session:
        if fecha:
            d = datetime.fromisoformat(fecha)
        else:
            d = (datetime.now(timezone.utc) - timedelta(hours=6)).date()
        inicio = datetime(d.year, d.month, d.day, 6, 0, 0, tzinfo=timezone.utc)
        fin = inicio + timedelta(days=1)

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
def listar_ventas(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        ventas = session.execute(
            text("""
                SELECT v.id, v.total, v.fecha_hora, v.metodo_pago, c.nombre as cliente_nombre
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.usuario_id = :uid
                ORDER BY v.fecha_hora DESC
            """),
            {"uid": usuario_id}
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
                WHERE vi.venta_id = :vid
            """),
            {"vid": id}
        ).mappings().fetchall()

        return {**dict(v), "items": [dict(i) for i in items]}
