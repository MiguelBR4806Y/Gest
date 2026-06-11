from fastapi import APIRouter, HTTPException, Query, Depends
from Backend.db.database import get_db
from Backend.models.schema import VentaCrear
from Backend.routers.auth import verificar_token
from datetime import date

router = APIRouter(prefix="/ventas", tags=["Ventas"])


@router.post("/")
def crear_venta(venta: VentaCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        total = 0
        for item in venta.items:
            p = conn.execute(
                "SELECT stock, precio FROM productos WHERE id = ? AND usuario_id = ?",
                (item.producto_id, usuario_id)
            ).fetchone()

            if not p:
                raise HTTPException(status_code=404, detail=f"Producto {item.producto_id} no encontrado")
            if p["stock"] < item.cantidad:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para producto {item.producto_id}")

            total += item.cantidad * item.precio_unitario

        if venta.cliente_id and venta.metodo_pago == "credito":
            c = conn.execute(
                "SELECT credito_limite, credito_usado FROM clientes WHERE id = ? AND usuario_id = ?",
                (venta.cliente_id, usuario_id)
            ).fetchone()

            if not c:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")

            disponible = c["credito_limite"] - c["credito_usado"]
            if total > disponible:
                raise HTTPException(status_code=400, detail="Crédito insuficiente")

        cursor = conn.execute(
            "INSERT INTO ventas (usuario_id, cliente_id, total, metodo_pago) VALUES (?, ?, ?, ?)",
            (usuario_id, venta.cliente_id, total, venta.metodo_pago)
        )
        venta_id = cursor.lastrowid

        for item in venta.items:
            conn.execute(
                "INSERT INTO venta_items (venta_id, producto_id, cantidad, precio_unitario) VALUES (?, ?, ?, ?)",
                (venta_id, item.producto_id, item.cantidad, item.precio_unitario)
            )
            conn.execute(
                "UPDATE productos SET stock = stock - ? WHERE id = ?",
                (item.cantidad, item.producto_id)
            )
            conn.execute(
                "INSERT INTO movimientos (producto_id, tipo, cantidad) VALUES (?, ?, ?)",
                (item.producto_id, "salida", item.cantidad)
            )

        if venta.cliente_id and venta.metodo_pago == "credito":
            conn.execute(
                "UPDATE clientes SET credito_usado = credito_usado + ? WHERE id = ?",
                (total, venta.cliente_id)
            )

        return {"id": venta_id, "total": total}


@router.get("/resumen-dia")
def resumen_dia(usuario_id: int = Depends(verificar_token), fecha: str = Query(default=None)):
    with get_db() as conn:
        hoy = fecha if fecha else date.today().isoformat()

        resumen = conn.execute("""
            SELECT COUNT(*) as numero_ventas, COALESCE(SUM(total), 0) as total_ventas
            FROM ventas
            WHERE usuario_id = ? AND DATE(fecha_hora) = ?
        """, (usuario_id, hoy)).fetchone()

        ultimas = conn.execute("""
            SELECT v.id, v.total, v.fecha_hora, v.metodo_pago, c.nombre as cliente_nombre
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.usuario_id = ? AND DATE(v.fecha_hora) = ?
            ORDER BY v.fecha_hora DESC
        """, (usuario_id, hoy)).fetchall()

        return {
            "numero_ventas": resumen["numero_ventas"],
            "total_ventas": resumen["total_ventas"],
            "ultimas_ventas": [dict(u) for u in ultimas]
        }


@router.get("/")
def listar_ventas(usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        ventas = conn.execute("""
            SELECT v.id, v.total, v.fecha_hora, v.metodo_pago, c.nombre as cliente_nombre
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.usuario_id = ?
            ORDER BY v.fecha_hora DESC
        """, (usuario_id,)).fetchall()
        return [dict(v) for v in ventas]


@router.get("/{id}")
def obtener_venta(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        v = conn.execute("""
            SELECT v.id, v.total, v.fecha_hora, v.metodo_pago, c.nombre as cliente_nombre
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.id = ? AND v.usuario_id = ?
        """, (id, usuario_id)).fetchone()

        if not v:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        items = conn.execute("""
            SELECT p.nombre, vi.cantidad, vi.precio_unitario
            FROM venta_items vi
            JOIN productos p ON vi.producto_id = p.id
            WHERE vi.venta_id = ?
        """, (id,)).fetchall()

        return {**dict(v), "items": [dict(i) for i in items]}