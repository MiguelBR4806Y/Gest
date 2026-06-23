from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from Backend.db.database import get_db
from Backend.db.models import Usuario
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
    with get_db() as session:
        hoy = date.today().isoformat()

        resumen = session.execute(
            text("""
                SELECT COUNT(*) as numero_ventas, COALESCE(SUM(total), 0) as total_ventas
                FROM ventas
                WHERE usuario_id = :uid AND (fecha_hora AT TIME ZONE 'America/Managua')::date = :hoy
            """),
            {"uid": usuario_id, "hoy": hoy}
        ).mappings().first()

        total_productos = session.execute(
            text("SELECT COUNT(*) as total FROM productos WHERE usuario_id = :uid"),
            {"uid": usuario_id}
        ).mappings().first()["total"]

        total_clientes = session.execute(
            text("SELECT COUNT(*) as total FROM clientes WHERE usuario_id = :uid"),
            {"uid": usuario_id}
        ).mappings().first()["total"]

        stock_bajo = session.execute(
            text("SELECT COUNT(*) as total FROM productos WHERE usuario_id = :uid AND stock <= 5"),
            {"uid": usuario_id}
        ).mappings().first()["total"]

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
    with get_db() as session:
        hoy = date.today().isoformat()
        ventas = session.execute(
            text("""
                SELECT v.id, v.total,
                       (v.fecha_hora AT TIME ZONE 'America/Managua') as fecha_hora,
                       c.nombre as cliente_nombre,
                       STRING_AGG(p.nombre, ', ') as productos
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                LEFT JOIN venta_items vi ON v.id = vi.venta_id
                LEFT JOIN productos p ON vi.producto_id = p.id
                WHERE v.usuario_id = :uid AND (v.fecha_hora AT TIME ZONE 'America/Managua')::date = :hoy
                GROUP BY v.id, c.nombre
                ORDER BY v.fecha_hora DESC
            """),
            {"uid": usuario_id, "hoy": hoy}
        ).mappings().fetchall()

        datos = [dict(v) for v in ventas]
        analisis = await analizar_ventas(datos)

        return {"ventas": datos, "analisis_ia": analisis}


@router.get("/predictivos")
def reportes_predictivos(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        hoy = date.today()

        hace_30 = (hoy - timedelta(days=30)).isoformat()
        ventas_items = session.execute(
            text("""
                SELECT vi.producto_id, SUM(vi.cantidad) as total_vendido
                FROM venta_items vi
                JOIN ventas v ON vi.venta_id = v.id
                WHERE v.usuario_id = :uid AND (v.fecha_hora AT TIME ZONE 'America/Managua')::date >= :hace30
                GROUP BY vi.producto_id
            """),
            {"uid": usuario_id, "hace30": hace_30}
        ).mappings().fetchall()

        productos = session.execute(
            text("""
                SELECT id, nombre, stock, stock_minimo
                FROM productos WHERE usuario_id = :uid
            """),
            {"uid": usuario_id}
        ).mappings().fetchall()

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

        ventas_por_dia = session.execute(
            text("""
                SELECT EXTRACT(DOW FROM fecha_hora AT TIME ZONE 'America/Managua')::text as dia_semana,
                       SUM(total) as total_ventas,
                       COUNT(*) as num_ventas
                FROM ventas
                WHERE usuario_id = :uid
                GROUP BY dia_semana
                ORDER BY total_ventas DESC
            """),
            {"uid": usuario_id}
        ).mappings().fetchall()

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

        hace_30_dt = hoy - timedelta(days=30)
        ventas_30d = session.execute(
            text("""
                SELECT (fecha_hora AT TIME ZONE 'America/Managua')::date as fecha, SUM(total) as total
                FROM ventas
                WHERE usuario_id = :uid AND (fecha_hora AT TIME ZONE 'America/Managua')::date >= :hace30
                GROUP BY fecha
            """),
            {"uid": usuario_id, "hace30": hace_30_dt.isoformat()}
        ).mappings().fetchall()

        if ventas_30d:
            total_30d = sum(v["total"] for v in ventas_30d)
            dias_con_ventas = len(ventas_30d)
            promedio_diario = total_30d / 30
            proyeccion_7d = round(promedio_diario * 7, 2)
            mejor_dia_30d = max(ventas_30d, key=lambda x: x["total"])
        else:
            promedio_diario = 0
            proyeccion_7d = 0
            dias_con_ventas = 0
            mejor_dia_30d = None

        return {
            "reabastecer": reabastecer[:5],
            "dias_semana": dias_ranking,
            "proyeccion": {
                "promedio_diario": round(promedio_diario, 2),
                "proyeccion_7_dias": proyeccion_7d,
                "dias_con_ventas_30d": dias_con_ventas,
            }
        }


@router.post("/chat")
async def chat_ia(body: PreguntaChat, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        nombre_negocio = u.nombre_negocio if u else "el negocio"

        productos = session.execute(
            text("""
                SELECT nombre, categoria, stock, stock_minimo, precio
                FROM productos WHERE usuario_id = :uid
            """),
            {"uid": usuario_id}
        ).mappings().fetchall()

        clientes = session.execute(
            text("""
                SELECT nombre, telefono, credito_limite, credito_usado
                FROM clientes WHERE usuario_id = :uid
            """),
            {"uid": usuario_id}
        ).mappings().fetchall()

        ventas = session.execute(
            text("""
                SELECT v.id, v.total, v.metodo_pago,
                       (v.fecha_hora AT TIME ZONE 'America/Managua') as fecha_hora,
                       c.nombre as cliente_nombre,
                       STRING_AGG(p.nombre || ' (x' || vi.cantidad || ' a C$' || vi.precio_unitario || ')', ', ') as items
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                LEFT JOIN venta_items vi ON v.id = vi.venta_id
                LEFT JOIN productos p ON vi.producto_id = p.id
                WHERE v.usuario_id = :uid
                GROUP BY v.id, c.nombre
                ORDER BY v.fecha_hora DESC
            """),
            {"uid": usuario_id}
        ).mappings().fetchall()

        movimientos = session.execute(
            text("""
                SELECT p.nombre as producto, m.tipo, m.cantidad,
                       (m.fecha_hora AT TIME ZONE 'America/Managua') as fecha_hora
                FROM movimientos m
                JOIN productos p ON m.producto_id = p.id
                WHERE p.usuario_id = :uid
                ORDER BY m.fecha_hora DESC
                LIMIT 100
            """),
            {"uid": usuario_id}
        ).mappings().fetchall()

        contexto = {
            "nombre_negocio": nombre_negocio,
            "productos": [dict(p) for p in productos],
            "clientes": [dict(c) for c in clientes],
            "ventas": [dict(v) for v in ventas],
            "movimientos": [dict(m) for m in movimientos],
        }

    respuesta = await responder_pregunta(body.pregunta, contexto)
    return {"respuesta": respuesta}
