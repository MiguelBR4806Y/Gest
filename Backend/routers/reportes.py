import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from Backend.ai.ia_service import analizar_ventas, responder_pregunta
from Backend.db.database import get_db
from Backend.db.models import ChatMensaje, Evento, Usuario
from Backend.dinero import a_float, dinero, sumar
from Backend.routers.auth import requiere_admin, requiere_modulo, verificar_token
from Backend.security import limitar
from Backend.tiempo import ZONA_POR_DEFECTO, a_local, fecha_de, hoy_local, rango_dia

router = APIRouter(
    prefix="/reportes",
    tags=["Reportes"],
)

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Tope de filas que se mandan al modelo: acota coste y tamaño del prompt.
MAX_VENTAS_EN_CONTEXTO = 300
MAX_MOVIMIENTOS_EN_CONTEXTO = 100
MAX_HISTORIAL = 200
MAX_FILAS_EXPORT = 50_000


class PreguntaChat(BaseModel):
    pregunta: str = Field(min_length=1, max_length=1000)


def _zona_usuario(session, usuario_id: int) -> str:
    return session.query(Usuario.zona_horaria).filter(
        Usuario.id == usuario_id
    ).scalar() or ZONA_POR_DEFECTO


@router.get("/dashboard", dependencies=[Depends(requiere_admin)])
def dashboard(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        zona_horaria = _zona_usuario(session, usuario_id)
        dia_hoy = hoy_local(zona_horaria)
        inicio, fin = rango_dia(dia_hoy, zona_horaria)

        # Una sola pasada para las métricas del día; antes eran varias rondas.
        resumen = session.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (WHERE estado = 'completada') AS numero_ventas,
                    COALESCE(SUM(total) FILTER (WHERE estado = 'completada'), 0) AS total_ventas,
                    COUNT(*) FILTER (WHERE estado = 'anulada') AS numero_anuladas,
                    COALESCE(SUM(total) FILTER (WHERE estado = 'anulada'), 0) AS total_anulado
                FROM ventas
                WHERE usuario_id = :uid AND fecha_hora >= :inicio AND fecha_hora < :fin
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().first()

        hoy = dia_hoy.isoformat()
        ayer_inicio, ayer_fin = rango_dia(
            dia_hoy - timedelta(days=1), zona_horaria
        )
        ganancia = session.execute(
            text("""
                SELECT COALESCE(SUM(v.total), 0) - COALESCE(SUM(
                    (SELECT SUM(vi.costo_unitario * vi.cantidad)
                     FROM venta_items vi WHERE vi.venta_id = v.id)
                ), 0) AS ganancia
                FROM ventas v
                WHERE v.usuario_id = :uid AND v.estado = 'completada'
                  AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).scalar()

        ayer = session.execute(
            text("""
                SELECT COALESCE(SUM(total), 0) AS total
                FROM ventas
                WHERE usuario_id = :uid AND estado = 'completada'
                  AND fecha_hora >= :inicio AND fecha_hora < :fin
            """),
            {"uid": usuario_id, "inicio": ayer_inicio, "fin": ayer_fin},
        ).scalar()

        conteos = session.execute(
            text("""
                SELECT
                    (SELECT COUNT(*) FROM productos WHERE usuario_id = :uid) AS productos,
                    (SELECT COUNT(*) FROM clientes WHERE usuario_id = :uid) AS clientes,
                    (SELECT COUNT(*) FROM productos
                     WHERE usuario_id = :uid AND stock <= stock_minimo) AS stock_bajo
            """),
            {"uid": usuario_id},
        ).mappings().first()

        numero = resumen["numero_ventas"] or 0
        total_hoy = dinero(resumen["total_ventas"])
        total_ayer = dinero(ayer)
        ganancia_hoy = dinero(ganancia)

        variacion = None
        if total_ayer > 0:
            variacion = a_float((total_hoy - total_ayer) / total_ayer * 100)

        return {
            "fecha": hoy,
            "resumen_dia": {
                "numero_ventas": numero,
                "total_ventas": a_float(total_hoy),
                "ticket_promedio": a_float(total_hoy / numero) if numero else 0.0,
                "ganancia": a_float(ganancia_hoy),
                "margen_pct": a_float(ganancia_hoy / total_hoy * 100) if total_hoy > 0 else 0.0,
                "variacion_vs_ayer": variacion,
                "anuladas": {
                    "numero": resumen["numero_anuladas"] or 0,
                    "total": a_float(resumen["total_anulado"]),
                },
            },
            "total_productos": conteos["productos"],
            "total_clientes": conteos["clientes"],
            "stock_bajo": conteos["stock_bajo"],
        }


@router.get("/tendencia", dependencies=[Depends(requiere_modulo("contabilidad"))])
def tendencia(
    dias: int = Query(default=7, ge=1, le=30),
    usuario_id: int = Depends(verificar_token),
):
    """Ventas y ganancia por día, rellenando con cero los días sin movimiento."""
    with get_db() as session:
        zona_horaria = _zona_usuario(session, usuario_id)
        hasta = hoy_local(zona_horaria)
        desde = hasta - timedelta(days=dias - 1)

        filas = session.execute(
            text("""
                WITH rango AS (
                    SELECT generate_series(
                        CAST(:desde AS date), CAST(:hasta AS date), interval '1 day'
                    )::date AS dia
                ),
                costos AS (
                    SELECT venta_id, SUM(costo_unitario * cantidad) AS costo
                    FROM venta_items GROUP BY venta_id
                )
                SELECT r.dia AS fecha,
                       COALESCE(SUM(v.total), 0) AS total,
                       COALESCE(SUM(v.total), 0) - COALESCE(SUM(c.costo), 0) AS ganancia,
                       COUNT(v.id) AS operaciones
                FROM rango r
                LEFT JOIN ventas v
                    ON v.usuario_id = :uid
                   AND v.estado = 'completada'
                   AND (v.fecha_hora AT TIME ZONE :tz)::date = r.dia
                LEFT JOIN costos c ON c.venta_id = v.id
                GROUP BY r.dia
                ORDER BY r.dia
            """),
            {
                "uid": usuario_id,
                "tz": zona_horaria,
                "desde": desde.isoformat(),
                "hasta": hasta.isoformat(),
            },
        ).mappings().fetchall()

        puntos = [{
            "fecha": f["fecha"].isoformat() if hasattr(f["fecha"], "isoformat") else str(f["fecha"]),
            "total": a_float(f["total"]),
            "ganancia": a_float(f["ganancia"]),
            "operaciones": int(f["operaciones"] or 0),
        } for f in filas]

        total_periodo = sumar(p["total"] for p in puntos)
        return {
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
            "dias": puntos,
            "total_periodo": a_float(total_periodo),
            "promedio_diario": a_float(total_periodo / max(len(puntos), 1)),
        }


@router.get("/ventas", dependencies=[Depends(requiere_modulo("contabilidad"))])
async def reporte_ventas(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        zona_horaria = _zona_usuario(session, usuario_id)
        inicio, fin = rango_dia(hoy_local(zona_horaria), zona_horaria)
        ventas = session.execute(
            text("""
                SELECT v.id, v.total, v.fecha_hora, v.estado,
                       c.nombre AS cliente_nombre,
                       STRING_AGG(p.nombre, ', ') AS productos
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                LEFT JOIN venta_items vi ON v.id = vi.venta_id
                LEFT JOIN productos p ON vi.producto_id = p.id
                WHERE v.usuario_id = :uid AND v.estado = 'completada'
                  AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin
                GROUP BY v.id, c.nombre
                ORDER BY v.fecha_hora DESC
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().fetchall()

        datos = [dict(v) for v in ventas]
        analisis = await analizar_ventas(datos)

        return {"ventas": datos, "analisis_ia": analisis}


@router.get("/predictivos", dependencies=[Depends(requiere_modulo("contabilidad"))])
def reportes_predictivos(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        zona_horaria = _zona_usuario(session, usuario_id)
        hace_30 = datetime.now(timezone.utc) - timedelta(days=30)

        ventas_items = session.execute(
            text("""
                SELECT vi.producto_id, SUM(vi.cantidad) AS total_vendido
                FROM venta_items vi
                JOIN ventas v ON vi.venta_id = v.id
                WHERE v.usuario_id = :uid AND v.estado = 'completada'
                  AND v.fecha_hora >= :hace30
                GROUP BY vi.producto_id
            """),
            {"uid": usuario_id, "hace30": hace_30},
        ).mappings().fetchall()

        productos = session.execute(
            text("""
                SELECT id, nombre, stock, stock_minimo
                FROM productos WHERE usuario_id = :uid
            """),
            {"uid": usuario_id},
        ).mappings().fetchall()

        ritmo = {r["producto_id"]: r["total_vendido"] for r in ventas_items}
        reabastecer = []

        for p in productos:
            vendido_30d = ritmo.get(p["id"], 0)
            if vendido_30d > 0:
                unidades_por_dia = vendido_30d / 30
                dias_restantes = int(p["stock"] / unidades_por_dia)
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
                SELECT EXTRACT(DOW FROM fecha_hora AT TIME ZONE :tz)::int AS dia_semana,
                       SUM(total) AS total_ventas,
                       COUNT(*) AS num_ventas
                FROM ventas
                WHERE usuario_id = :uid AND estado = 'completada'
                GROUP BY dia_semana
                ORDER BY total_ventas DESC
            """),
            {"uid": usuario_id, "tz": zona_horaria},
        ).mappings().fetchall()

        mapa_dias = {
            0: "Domingo", 1: "Lunes", 2: "Martes", 3: "Miércoles",
            4: "Jueves", 5: "Viernes", 6: "Sábado",
        }
        dias_ranking = [{
            "dia": mapa_dias.get(v["dia_semana"], "—"),
            "total_ventas": a_float(v["total_ventas"]),
            "num_ventas": v["num_ventas"],
        } for v in ventas_por_dia]

        ventas_30d = session.execute(
            text("""
                SELECT (fecha_hora AT TIME ZONE :tz)::date AS fecha, SUM(total) AS total
                FROM ventas
                WHERE usuario_id = :uid AND estado = 'completada'
                  AND fecha_hora >= :hace30
                GROUP BY fecha
            """),
            {"uid": usuario_id, "hace30": hace_30, "tz": zona_horaria},
        ).mappings().fetchall()

        if ventas_30d:
            total_30d = sumar(v["total"] for v in ventas_30d)
            promedio_diario = total_30d / 30
            proyeccion_7d = promedio_diario * 7
            dias_con_ventas = len(ventas_30d)
        else:
            promedio_diario = Decimal("0.00")
            proyeccion_7d = Decimal("0.00")
            dias_con_ventas = 0

        return {
            "reabastecer": reabastecer[:5],
            "dias_semana": dias_ranking,
            "proyeccion": {
                "promedio_diario": a_float(promedio_diario),
                "proyeccion_7_dias": a_float(proyeccion_7d),
                "dias_con_ventas_30d": dias_con_ventas,
            },
        }


@router.get("/margenes", dependencies=[Depends(requiere_modulo("contabilidad"))])
def reporte_margenes(
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
    usuario_id: int = Depends(verificar_token),
):
    """Ganancia y margen por producto en un periodo.

    El descuento de cada venta se reparte entre sus líneas en proporción al
    importe bruto, para que una promoción no infle los ingresos del producto.
    """
    with get_db() as session:
        zona_horaria = _zona_usuario(session, usuario_id)
        try:
            dia_hasta = fecha_de(hasta, zona_horaria) if hasta else hoy_local(zona_horaria)
            dia_desde = (
                fecha_de(desde, zona_horaria)
                if desde
                else dia_hasta - timedelta(days=29)
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Fechas inválidas, use YYYY-MM-DD")

        if dia_hasta < dia_desde:
            raise HTTPException(status_code=400, detail="La fecha final es anterior a la inicial")

        inicio = rango_dia(dia_desde, zona_horaria)[0]
        fin = rango_dia(dia_hasta, zona_horaria)[1]

        filas = session.execute(
            text("""
                WITH lineas AS (
                    SELECT v.id AS venta_id, v.total AS total_venta,
                           vi.producto_id, vi.cantidad,
                           vi.precio_unitario * vi.cantidad AS bruto,
                           vi.costo_unitario * vi.cantidad AS costo
                    FROM venta_items vi
                    JOIN ventas v ON vi.venta_id = v.id
                    WHERE v.usuario_id = :uid AND v.estado = 'completada'
                      AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin
                ),
                brutos AS (
                    SELECT venta_id, SUM(bruto) AS bruto_venta
                    FROM lineas GROUP BY venta_id
                )
                SELECT l.producto_id,
                       COALESCE(p.nombre, 'Producto eliminado') AS nombre,
                       SUM(l.cantidad) AS unidades,
                       SUM(
                           CASE WHEN b.bruto_venta > 0
                                THEN l.bruto * l.total_venta / b.bruto_venta
                                ELSE 0 END
                       ) AS ingresos,
                       SUM(l.costo) AS costo
                FROM lineas l
                JOIN brutos b ON b.venta_id = l.venta_id
                LEFT JOIN productos p ON p.id = l.producto_id
                GROUP BY l.producto_id, p.nombre
                ORDER BY (SUM(
                    CASE WHEN b.bruto_venta > 0
                         THEN l.bruto * l.total_venta / b.bruto_venta
                         ELSE 0 END
                ) - SUM(l.costo)) DESC
                LIMIT 200
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().fetchall()

        productos = []
        ingresos_total = Decimal("0.00")
        costo_total = Decimal("0.00")
        unidades_total = 0

        for f in filas:
            ingresos = dinero(f["ingresos"])
            costo = dinero(f["costo"])
            ganancia = ingresos - costo
            ingresos_total += ingresos
            costo_total += costo
            unidades_total += int(f["unidades"] or 0)
            productos.append({
                "producto_id": f["producto_id"],
                "nombre": f["nombre"],
                "unidades": int(f["unidades"] or 0),
                "ingresos": a_float(ingresos),
                "costo": a_float(costo),
                "ganancia": a_float(ganancia),
                "margen_pct": a_float(ganancia / ingresos * 100) if ingresos > 0 else 0.0,
            })

        ganancia_total = ingresos_total - costo_total
        return {
            "desde": dia_desde.isoformat(),
            "hasta": dia_hasta.isoformat(),
            "totales": {
                "unidades": unidades_total,
                "ingresos": a_float(ingresos_total),
                "costo": a_float(costo_total),
                "ganancia": a_float(ganancia_total),
                "margen_pct": (
                    a_float(ganancia_total / ingresos_total * 100)
                    if ingresos_total > 0 else 0.0
                ),
            },
            "productos": productos,
        }


@router.get(
    "/exportar",
    dependencies=[
        Depends(limitar(10, 300, "exportar-csv")),
        Depends(requiere_modulo("contabilidad")),
    ],
)
def exportar_csv(
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
    usuario_id: int = Depends(verificar_token),
):
    """Ventas del periodo en CSV (con BOM, para que Excel lo abra bien)."""
    with get_db() as session:
        zona_horaria = _zona_usuario(session, usuario_id)
        try:
            dia_desde = fecha_de(desde, zona_horaria) if desde else hoy_local(zona_horaria)
            dia_hasta = fecha_de(hasta, zona_horaria) if hasta else dia_desde
        except ValueError:
            raise HTTPException(status_code=400, detail="Fechas inválidas, use YYYY-MM-DD")

        if dia_hasta < dia_desde:
            raise HTTPException(status_code=400, detail="La fecha final es anterior a la inicial")

        inicio = rango_dia(dia_desde, zona_horaria)[0]
        fin = rango_dia(dia_hasta, zona_horaria)[1]

        filas = session.execute(
            text("""
                SELECT v.id, v.fecha_hora, v.metodo_pago, v.estado, v.total,
                       v.efectivo_recibido, v.vuelto,
                       COALESCE(SUM(vi.costo_unitario * vi.cantidad), 0) AS costo,
                       COALESCE(c.nombre, 'Consumidor final') AS cliente,
                       COALESCE(STRING_AGG(p.nombre || ' x' || vi.cantidad, ' | '), '') AS productos
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                LEFT JOIN venta_items vi ON v.id = vi.venta_id
                LEFT JOIN productos p ON vi.producto_id = p.id
                WHERE v.usuario_id = :uid AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin
                GROUP BY v.id, c.nombre
                ORDER BY v.fecha_hora
                LIMIT :limite
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin, "limite": MAX_FILAS_EXPORT},
        ).mappings().fetchall()

        salida = io.StringIO()
        escritor = csv.writer(salida, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        escritor.writerow([
            "Factura", "Fecha", "Hora", "Cliente", "Método de pago",
            "Estado", "Productos", "Total C$", "Costo C$", "Ganancia C$",
            "Efectivo recibido C$", "Vuelto C$",
        ])
        for f in filas:
            local = a_local(f["fecha_hora"], zona_horaria)
            escritor.writerow([
                f["id"],
                local.strftime("%Y-%m-%d"),
                local.strftime("%H:%M:%S"),
                f["cliente"],
                f["metodo_pago"],
                f["estado"],
                f["productos"],
                f"{dinero(f['total']):.2f}",
                f"{dinero(f['costo']):.2f}",
                f"{(dinero(f['total']) - dinero(f['costo'])):.2f}",
                f"{dinero(f['efectivo_recibido']):.2f}" if f["efectivo_recibido"] is not None else "",
                f"{dinero(f['vuelto']):.2f}" if f["vuelto"] is not None else "",
            ])

        nombre = f"ventas_{dia_desde}_{dia_hasta}.csv"
        return Response(
            content="\ufeff" + salida.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
        )


@router.get("/eventos", dependencies=[Depends(requiere_admin)])
def listar_eventos(
    usuario_id: int = Depends(verificar_token),
    limite: int = Query(default=50, ge=1, le=200),
    tipo: str = Query(default=None, max_length=40),
):
    """Bitácora de auditoría de la cuenta."""
    with get_db() as session:
        consulta = session.query(Evento).filter(Evento.usuario_id == usuario_id)
        if tipo:
            consulta = consulta.filter(Evento.tipo == tipo)
        eventos = consulta.order_by(Evento.fecha_hora.desc()).limit(limite).all()
        return [{
            "id": e.id,
            "tipo": e.tipo,
            "entidad": e.entidad,
            "entidad_id": e.entidad_id,
            "detalle": e.detalle,
            "fecha_hora": e.fecha_hora,
        } for e in eventos]


@router.post(
    "/chat",
    dependencies=[
        Depends(limitar(20, 300, "chat-ia")),
        Depends(requiere_modulo("contabilidad")),
    ],
)
async def chat_ia(body: PreguntaChat, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        nombre_negocio = u.nombre_negocio if u else "el negocio"
        zona_horaria = u.zona_horaria if u and u.zona_horaria else ZONA_POR_DEFECTO

        productos = session.execute(
            text("""
                SELECT nombre, categoria, stock, stock_minimo, precio
                FROM productos WHERE usuario_id = :uid
            """),
            {"uid": usuario_id},
        ).mappings().fetchall()

        clientes = session.execute(
            text("""
                SELECT nombre, telefono, credito_limite, credito_usado
                FROM clientes WHERE usuario_id = :uid
            """),
            {"uid": usuario_id},
        ).mappings().fetchall()

        ventas = session.execute(
            text("""
                SELECT v.id, v.total, v.metodo_pago,
                       (v.fecha_hora AT TIME ZONE :tz) AS fecha_hora,
                       c.nombre AS cliente_nombre,
                       STRING_AGG(p.nombre || ' (x' || vi.cantidad || ' a C$' || vi.precio_unitario || ')', ', ') AS items
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                LEFT JOIN venta_items vi ON v.id = vi.venta_id
                LEFT JOIN productos p ON vi.producto_id = p.id
                WHERE v.usuario_id = :uid AND v.estado = 'completada'
                GROUP BY v.id, c.nombre
                ORDER BY v.fecha_hora DESC
                LIMIT :limite
            """),
            {"uid": usuario_id, "limite": MAX_VENTAS_EN_CONTEXTO, "tz": zona_horaria},
        ).mappings().fetchall()

        movimientos = session.execute(
            text("""
                SELECT p.nombre AS producto, m.tipo, m.cantidad,
                       (m.fecha_hora AT TIME ZONE :tz) AS fecha_hora
                FROM movimientos m
                JOIN productos p ON m.producto_id = p.id
                WHERE p.usuario_id = :uid
                ORDER BY m.fecha_hora DESC
                LIMIT :limite
            """),
            {"uid": usuario_id, "limite": MAX_MOVIMIENTOS_EN_CONTEXTO, "tz": zona_horaria},
        ).mappings().fetchall()

        tasa_cambio = u.tasa_cambio if u else 36.0
        contexto = {
            "nombre_negocio": nombre_negocio,
            "tasa_cambio": a_float(tasa_cambio),
            "productos": [dict(p) for p in productos],
            "clientes": [dict(c) for c in clientes],
            "ventas": [dict(v) for v in ventas],
            "movimientos": [dict(m) for m in movimientos],
        }

    respuesta = await responder_pregunta(body.pregunta, contexto)

    with get_db() as session:
        session.add(ChatMensaje(usuario_id=usuario_id, role="user", text=body.pregunta))
        session.add(ChatMensaje(usuario_id=usuario_id, role="ai", text=respuesta))

    return {"respuesta": respuesta}


@router.get("/chat/historial", dependencies=[Depends(requiere_modulo("contabilidad"))])
def historial_chat(
    usuario_id: int = Depends(verificar_token),
    limite: int = Query(default=50, ge=1, le=MAX_HISTORIAL),
):
    with get_db() as session:
        mensajes = session.query(ChatMensaje).filter(
            ChatMensaje.usuario_id == usuario_id
        ).order_by(ChatMensaje.creado_en.asc()).limit(limite).all()

        return [{
            "id": m.id,
            "role": m.role,
            "text": m.text,
            "creado_en": m.creado_en.isoformat(),
        } for m in mensajes]
