from fastapi import APIRouter, Depends
from pydantic import BaseModel
from Backend.db.database import get_db
from Backend.ai.ia_service import analizar_ventas, responder_pregunta
from Backend.routers.auth import verificar_token
from datetime import date, timedelta
from collections import defaultdict

router = APIRouter(prefix="/reportes", tags=["Reportes"])

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


class PreguntaChat(BaseModel):
    pregunta: str


@router.get("/dashboard")
def dashboard(usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        hoy = date.today().isoformat()

        resumen = conn.execute("""
            SELECT COUNT(*) as numero_ventas, COALESCE(SUM(total), 0) as total_ventas
            FROM ventas 
            WHERE usuario_id = ? AND DATE(fecha_hora, '-6 hours') = ?
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
            SELECT v.id, v.total, datetime(v.fecha_hora, '-6 hours') as fecha_hora, c.nombre as cliente_nombre,
                   GROUP_CONCAT(p.nombre) as productos
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            LEFT JOIN venta_items vi ON v.id = vi.venta_id
            LEFT JOIN productos p ON vi.producto_id = p.id
            WHERE v.usuario_id = ? AND DATE(v.fecha_hora, '-6 hours') = ?
            GROUP BY v.id
            ORDER BY v.fecha_hora DESC
        """, (usuario_id, hoy)).fetchall()

        datos = [dict(v) for v in ventas]
        analisis = await analizar_ventas(datos)

        return {"ventas": datos, "analisis_ia": analisis}


@router.get("/predictivos")
def reportes_predictivos(usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        hoy = date.today()

        # ── 1. Productos a reabastecer pronto ──
        # Calculamos cuántas unidades se vendieron por producto en los últimos 30 días
        hace_30 = (hoy - timedelta(days=30)).isoformat()
        ventas_items = conn.execute("""
            SELECT vi.producto_id, SUM(vi.cantidad) as total_vendido
            FROM venta_items vi
            JOIN ventas v ON vi.venta_id = v.id
            WHERE v.usuario_id = ? AND DATE(v.fecha_hora, '-6 hours') >= ?
            GROUP BY vi.producto_id
        """, (usuario_id, hace_30)).fetchall()

        productos = conn.execute(
            "SELECT id, nombre, stock, stock_minimo FROM productos WHERE usuario_id = ?",
            (usuario_id,)
        ).fetchall()

        ritmo = {r["producto_id"]: r["total_vendido"] for r in ventas_items}
        reabastecer = []

        for p in productos:
            vendido_30d = ritmo.get(p["id"], 0)
            if vendido_30d > 0:
                unidades_por_dia = vendido_30d / 30
                dias_restantes = int(p["stock"] / unidades_por_dia) if unidades_por_dia > 0 else 999
                if dias_restantes <= 14:
                    reabastecer.append({
                        "nombre": p["nombre"],
                        "stock_actual": p["stock"],
                        "dias_restantes": dias_restantes,
                        "unidades_por_dia": round(unidades_por_dia, 1),
                    })

        reabastecer.sort(key=lambda x: x["dias_restantes"])

        # ── 2. Mejor día de la semana ──
        ventas_por_dia = conn.execute("""
            SELECT strftime('%w', datetime(fecha_hora, '-6 hours')) as dia_semana,
                   SUM(total) as total_ventas,
                   COUNT(*) as num_ventas
            FROM ventas
            WHERE usuario_id = ?
            GROUP BY dia_semana
            ORDER BY total_ventas DESC
        """, (usuario_id,)).fetchall()

        # SQLite: %w → 0=domingo, 1=lunes ... 6=sábado
        mapa_dias = {
            "0": "Domingo", "1": "Lunes", "2": "Martes",
            "3": "Miércoles", "4": "Jueves", "5": "Viernes", "6": "Sábado"
        }

        dias_ranking = []
        for v in ventas_por_dia:
            dias_ranking.append({
                "dia": mapa_dias.get(v["dia_semana"], "—"),
                "total_ventas": round(v["total_ventas"], 2),
                "num_ventas": v["num_ventas"],
            })

        # ── 3. Proyección de ventas próximos 7 días ──
        # Promedio diario basado en los últimos 30 días
        hace_30_dt = hoy - timedelta(days=30)
        ventas_30d = conn.execute("""
            SELECT DATE(fecha_hora, '-6 hours') as fecha, SUM(total) as total
            FROM ventas
            WHERE usuario_id = ? AND DATE(fecha_hora, '-6 hours') >= ?
            GROUP BY fecha
        """, (usuario_id, hace_30_dt.isoformat())).fetchall()

        if ventas_30d:
            total_30d = sum(v["total"] for v in ventas_30d)
            dias_con_ventas = len(ventas_30d)
            promedio_diario = total_30d / 30  # sobre 30 días corridos
            proyeccion_7d = round(promedio_diario * 7, 2)
            mejor_dia_30d = max(ventas_30d, key=lambda x: x["total"])
        else:
            promedio_diario = 0
            proyeccion_7d = 0
            dias_con_ventas = 0
            mejor_dia_30d = None

        return {
            "reabastecer": reabastecer[:5],  # top 5 más urgentes
            "dias_semana": dias_ranking,
            "proyeccion": {
                "promedio_diario": round(promedio_diario, 2),
                "proyeccion_7_dias": proyeccion_7d,
                "dias_con_ventas_30d": dias_con_ventas,
            }
        }


@router.post("/chat")
async def chat_ia(body: PreguntaChat, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        u = conn.execute(
            "SELECT nombre_negocio FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
        nombre_negocio = u["nombre_negocio"] if u else "el negocio"

        productos = conn.execute(
            """SELECT nombre, categoria, stock, stock_minimo, precio
               FROM productos WHERE usuario_id = ?""",
            (usuario_id,)
        ).fetchall()

        clientes = conn.execute(
            """SELECT nombre, telefono, credito_limite, credito_usado
               FROM clientes WHERE usuario_id = ?""",
            (usuario_id,)
        ).fetchall()

        ventas = conn.execute(
            """SELECT v.id, v.total, v.metodo_pago,
                      datetime(v.fecha_hora, '-6 hours') as fecha_hora,
                      c.nombre as cliente_nombre,
                      GROUP_CONCAT(p.nombre || ' (x' || vi.cantidad || ' a C$' || vi.precio_unitario || ')') as items
               FROM ventas v
               LEFT JOIN clientes c ON v.cliente_id = c.id
               LEFT JOIN venta_items vi ON v.id = vi.venta_id
               LEFT JOIN productos p ON vi.producto_id = p.id
               WHERE v.usuario_id = ?
               GROUP BY v.id
               ORDER BY v.fecha_hora DESC""",
            (usuario_id,)
        ).fetchall()

        movimientos = conn.execute(
            """SELECT p.nombre as producto, m.tipo, m.cantidad,
                      datetime(m.fecha_hora, '-6 hours') as fecha_hora
               FROM movimientos m
               JOIN productos p ON m.producto_id = p.id
               WHERE p.usuario_id = ?
               ORDER BY m.fecha_hora DESC
               LIMIT 100""",
            (usuario_id,)
        ).fetchall()

        contexto = {
            "nombre_negocio": nombre_negocio,
            "productos": [dict(p) for p in productos],
            "clientes": [dict(c) for c in clientes],
            "ventas": [dict(v) for v in ventas],
            "movimientos": [dict(m) for m in movimientos],
        }

    respuesta = await responder_pregunta(body.pregunta, contexto)
    return {"respuesta": respuesta}