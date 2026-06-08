from fastapi import APIRouter, Depends
from Backend.db.database import get_db
from Backend.ai.ia_service import analizar_ventas
from Backend.routers.auth import verificar_token
from datetime import date

router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.get("/dashboard")
def dashboard(usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        hoy = date.today().isoformat()

        resumen = conn.execute("""
            SELECT COUNT(*) as numero_ventas, COALESCE(SUM(total), 0) as total_ventas
            FROM ventas WHERE usuario_id = ? AND DATE(fecha_hora) = ?
        """, (usuario_id, hoy)).fetchone()

        total_productos = conn.execute(
            "SELECT COUNT(*) as total FROM productos WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()["total"]

        total_clientes = conn.execute(
            "SELECT COUNT(*) as total FROM clientes WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()["total"]

        stock_bajo = conn.execute(
            "SELECT COUNT(*) as total FROM productos WHERE usuario_id = ? AND stock <= 5", (usuario_id,)
        ).fetchone()["total"]

        return {
            "resumen_dia": {
                "numero_ventas": resumen["numero_ventas"],
                "total_ventas": resumen["total_ventas"],
            },
            "total_productos": total_productos,
            "total_clientes": total_clientes,
            "stock_bajo": stock_bajo,
        }


@router.get("/ventas")
async def reporte_ventas(usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        hoy = date.today().isoformat()

        ventas = conn.execute("""
            SELECT v.id, v.total, v.fecha_hora, c.nombre as cliente_nombre,
                   GROUP_CONCAT(p.nombre) as productos
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            LEFT JOIN venta_items vi ON v.id = vi.venta_id
            LEFT JOIN productos p ON vi.producto_id = p.id
            WHERE v.usuario_id = ? AND DATE(v.fecha_hora) = ?
            GROUP BY v.id
            ORDER BY v.fecha_hora DESC
        """, (usuario_id, hoy)).fetchall()

        datos = [dict(v) for v in ventas]
        analisis = await analizar_ventas(datos)

        return {"ventas": datos, "analisis_ia": analisis}