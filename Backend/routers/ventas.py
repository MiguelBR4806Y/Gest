from fastapi import APIRouter, HTTPException
from backend.db.database import get_db
from backend.models.schemas import VentaCrear
from datetime import datetime, date

router = APIRouter(prefix="/ventas", tags=["Ventas"])


# Registrar venta completa
@router.post("/")
def crear_venta(venta: VentaCrear):
    with get_db() as conn:

        # Calcular total y verificar stock
        total = 0
        for item in venta.items:
            p = conn.execute(
                "SELECT stock, precio FROM productos WHERE id = ?",
                (item.producto_id,)
            ).fetchone()

            if not p:
                raise HTTPException(status_code=404, detail=f"Producto {item.producto_id} no encontrado")
            if p["stock"] < item.cantidad:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para producto {item.producto_id}")

            total += item.cantidad * item.precio_unitario

        # Verificar crédito si hay cliente
        if venta.cliente_id:
            c = conn.execute(
                "SELECT credito_limite, credito_usado FROM clientes WHERE id = ?",
                (venta.cliente_id,)
            ).fetchone()

            if not c:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")

            disponible = c["credito_limite"] - c["credito_usado"]
            if total > disponible:
                raise HTTPException(status_code=400, detail="Crédito insuficiente")

        # Insertar venta
        cursor = conn.execute(
            "INSERT INTO ventas (cliente_id, total) VALUES (?, ?)",
            (venta.cliente_id, total)
        )
        venta_id = cursor.lastrowid

        # Insertar items y descontar stock
        for item in venta.items:
            conn.execute(
                "INSERT INTO venta_items (venta_id, producto_id, cantidad, precio_unitario) VALUES (?, ?, ?, ?)",
                (venta_id, item.producto_id, item.cantidad, item.precio_unitario)
            )
            conn.execute(
                "UPDATE productos SET stock = stock - ? WHERE id = ?",
                (item.cantidad, item.producto_id)
            )

        # Actualizar crédito usado del cliente
        if venta.cliente_id:
            conn.execute(
                "UPDATE clientes SET credito_usado = credito_usado + ? WHERE id = ?",
                (total, venta.cliente_id)
            )

        return {"id": venta_id, "total": total}


# Resumen del día
@router.get("/resumen-dia")
def resumen_dia():
    with get_db() as conn:
        hoy = date.today().isoformat()

        resumen = conn.execute("""
            SELECT 
                COUNT(*) as numero_ventas,
                COALESCE(SUM(total), 0) as total_ventas
            FROM ventas
            WHERE DATE(fecha_hora) = ?
        """, (hoy,)).fetchone()

        ultimas = conn.execute("""
            SELECT 
                v.id,
                v.total,
                v.fecha_hora,
                c.nombre as cliente_nombre
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE DATE(v.fecha_hora) = ?
            ORDER BY v.fecha_hora DESC
            LIMIT 5
        """, (hoy,)).fetchall()

        return {
            "numero_ventas": resumen["numero_ventas"],
            "total_ventas": resumen["total_ventas"],
            "ultimas_ventas": [dict(u) for u in ultimas]
        }


# Listar todas las ventas
@router.get("/")
def listar_ventas():
    with get_db() as conn:
        ventas = conn.execute("""
            SELECT v.id, v.total, v.fecha_hora, c.nombre as cliente_nombre
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            ORDER BY v.fecha_hora DESC
        """).fetchall()
        return [dict(v) for v in ventas]


# Ver detalle de una venta
@router.get("/{id}")
def obtener_venta(id: int):
    with get_db() as conn:
        v = conn.execute("""
            SELECT v.id, v.total, v.fecha_hora, c.nombre as cliente_nombre
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.id = ?
        """, (id,)).fetchone()

        if not v:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        items = conn.execute("""
            SELECT p.nombre, vi.cantidad, vi.precio_unitario
            FROM venta_items vi
            JOIN productos p ON vi.producto_id = p.id
            WHERE vi.venta_id = ?
        """, (id,)).fetchall()

        return {
            **dict(v),
            "items": [dict(i) for i in items]
        }