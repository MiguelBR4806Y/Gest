"""Módulo de contabilidad: resumen de resultados y exportación.

No crea tablas: consolida lo que ya existe (ventas, costo congelado de las
líneas, gastos y compras). Es un resumen de gestión, no una contabilidad
formal ni una declaración fiscal: no calcula IVA ni partida doble.
"""

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text

from Backend.db.database import get_db
from Backend.db.models import Usuario
from Backend.dinero import a_float, dinero, restar
from Backend.routers.auth import requiere_modulo, verificar_token
from Backend.tiempo import ZONA_POR_DEFECTO, a_local, fecha_de, hoy_local, rango_dia

router = APIRouter(
    prefix="/contabilidad",
    tags=["Contabilidad"],
    dependencies=[Depends(requiere_modulo("contabilidad"))],
)

MAX_FILAS_EXPORT = 50_000


def _zona(session, usuario_id: int) -> str:
    return session.query(Usuario.zona_horaria).filter(
        Usuario.id == usuario_id
    ).scalar() or ZONA_POR_DEFECTO


def _periodo(
    desde: str | None,
    hasta: str | None,
    zona: str,
    por_defecto_mes_actual: bool = False,
) -> tuple[date, date, object, object]:
    """Normaliza el rango y devuelve también los límites UTC para SQL."""
    try:
        if desde or hasta:
            dia_desde = fecha_de(desde, zona) if desde else fecha_de(hasta, zona)
            dia_hasta = fecha_de(hasta, zona) if hasta else dia_desde
        else:
            hoy = hoy_local(zona)
            if por_defecto_mes_actual:
                dia_desde = hoy.replace(day=1)
                dia_hasta = hoy
            else:
                dia_desde = dia_hasta = hoy
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas, use YYYY-MM-DD")

    if dia_hasta < dia_desde:
        raise HTTPException(status_code=400, detail="La fecha final es anterior a la inicial")

    inicio = rango_dia(dia_desde, zona)[0]
    fin = rango_dia(dia_hasta, zona)[1]
    return dia_desde, dia_hasta, inicio, fin


@router.get("/resumen")
def resumen_contable(
    usuario_id: int = Depends(verificar_token),
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
):
    """Ingresos, costo, gastos y utilidad del periodo (por defecto, el mes)."""
    with get_db() as session:
        zona = _zona(session, usuario_id)
        dia_desde, dia_hasta, inicio, fin = _periodo(desde, hasta, zona, True)

        ventas = session.execute(
            text("""
                SELECT
                    COUNT(*) AS numero_ventas,
                    COALESCE(SUM(v.total), 0) AS ingresos,
                    COALESCE(SUM((
                        SELECT SUM(vi.costo_unitario * vi.cantidad)
                        FROM venta_items vi WHERE vi.venta_id = v.id
                    )), 0) AS costo
                FROM ventas v
                WHERE v.usuario_id = :uid
                  AND v.estado = 'completada'
                  AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().first()

        gastos = session.execute(
            text("""
                SELECT COALESCE(SUM(monto), 0) AS total, COUNT(*) AS cantidad
                FROM gastos
                WHERE usuario_id = :uid AND fecha >= :inicio AND fecha < :fin
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().first()

        por_categoria = session.execute(
            text("""
                SELECT categoria, COUNT(*) AS cantidad, COALESCE(SUM(monto), 0) AS total
                FROM gastos
                WHERE usuario_id = :uid AND fecha >= :inicio AND fecha < :fin
                GROUP BY categoria
                ORDER BY SUM(monto) DESC
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().fetchall()

        ingresos = dinero(ventas["ingresos"])
        costo = dinero(ventas["costo"])
        total_gastos = dinero(gastos["total"])
        ganancia_bruta = restar(ingresos, costo)
        utilidad = restar(ganancia_bruta, total_gastos)
        margen = a_float(utilidad / ingresos * 100) if ingresos > 0 else 0.0

        return {
            "desde": dia_desde.isoformat(),
            "hasta": dia_hasta.isoformat(),
            "numero_ventas": ventas["numero_ventas"],
            "ingresos": a_float(ingresos),
            "costo_ventas": a_float(costo),
            "ganancia_bruta": a_float(ganancia_bruta),
            "gastos": a_float(total_gastos),
            "numero_gastos": gastos["cantidad"],
            "utilidad": a_float(utilidad),
            "margen_pct": margen,
            "gastos_por_categoria": [
                {
                    "categoria": fila["categoria"],
                    "cantidad": fila["cantidad"],
                    "total": a_float(fila["total"]),
                }
                for fila in por_categoria
            ],
            "nota": "Resumen de gestión. No incluye IVA ni asientos contables.",
        }


@router.get("/serie")
def serie_contable(
    usuario_id: int = Depends(verificar_token),
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
    agrupacion: str = Query(default="dia", pattern="^(dia|mes)$"),
):
    """Ingresos, gastos y utilidad por día o por mes, para el gráfico."""
    with get_db() as session:
        zona = _zona(session, usuario_id)
        dia_desde, dia_hasta, inicio, fin = _periodo(desde, hasta, zona, True)

        formato = "YYYY-MM-DD" if agrupacion == "dia" else "YYYY-MM"
        # Se agrupa en la zona del negocio, no en UTC: el día contable es el local.
        filas = session.execute(
            text(f"""
                WITH dias AS (
                    SELECT to_char(fecha_hora AT TIME ZONE :zona, '{formato}') AS periodo,
                           SUM(total) AS ingresos,
                           SUM((
                               SELECT SUM(vi.costo_unitario * vi.cantidad)
                               FROM venta_items vi WHERE vi.venta_id = v.id
                           )) AS costo
                    FROM ventas v
                    WHERE v.usuario_id = :uid
                      AND v.estado = 'completada'
                      AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin
                    GROUP BY 1
                ),
                egresos AS (
                    SELECT to_char(fecha AT TIME ZONE :zona, '{formato}') AS periodo,
                           SUM(monto) AS gastos
                    FROM gastos
                    WHERE usuario_id = :uid AND fecha >= :inicio AND fecha < :fin
                    GROUP BY 1
                )
                SELECT COALESCE(d.periodo, e.periodo) AS periodo,
                       COALESCE(d.ingresos, 0) AS ingresos,
                       COALESCE(d.costo, 0) AS costo,
                       COALESCE(e.gastos, 0) AS gastos
                FROM dias d
                FULL OUTER JOIN egresos e ON d.periodo = e.periodo
                ORDER BY 1
            """),
            {"uid": usuario_id, "zona": zona, "inicio": inicio, "fin": fin},
        ).mappings().fetchall()

        puntos = []
        for fila in filas:
            ingresos = dinero(fila["ingresos"])
            costo = dinero(fila["costo"])
            gastos = dinero(fila["gastos"])
            puntos.append({
                "periodo": fila["periodo"],
                "ingresos": a_float(ingresos),
                "costo": a_float(costo),
                "gastos": a_float(gastos),
                "utilidad": a_float(restar(restar(ingresos, costo), gastos)),
            })

        return {
            "agrupacion": agrupacion,
            "desde": dia_desde.isoformat(),
            "hasta": dia_hasta.isoformat(),
            "puntos": puntos,
        }


@router.get("/exportar")
def exportar_contabilidad(
    usuario_id: int = Depends(verificar_token),
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
):
    """CSV con ventas y gastos del periodo, consolidados por fecha."""
    with get_db() as session:
        zona = _zona(session, usuario_id)
        dia_desde, dia_hasta, inicio, fin = _periodo(desde, hasta, zona, True)

        movimientos = session.execute(
            text("""
                SELECT 'Venta' AS tipo, v.id AS referencia,
                       v.fecha_hora AS fecha, v.total AS ingreso,
                       COALESCE((
                           SELECT SUM(vi.costo_unitario * vi.cantidad)
                           FROM venta_items vi WHERE vi.venta_id = v.id
                       ), 0) AS costo,
                       0 AS gasto,
                       COALESCE(c.nombre, 'Consumidor final') AS detalle
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.usuario_id = :uid AND v.estado = 'completada'
                  AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin

                UNION ALL

                SELECT 'Gasto' AS tipo, g.id AS referencia,
                       g.fecha, 0 AS ingreso, 0 AS costo, g.monto AS gasto,
                       g.concepto || ' (' || g.categoria || ')' AS detalle
                FROM gastos g
                WHERE g.usuario_id = :uid
                  AND g.fecha >= :inicio AND g.fecha < :fin

                ORDER BY fecha
                LIMIT :limite
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin, "limite": MAX_FILAS_EXPORT},
        ).mappings().fetchall()

        salida = io.StringIO()
        escritor = csv.writer(salida, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        escritor.writerow([
            "Tipo", "Referencia", "Fecha", "Detalle",
            "Ingreso C$", "Costo C$", "Gasto C$", "Resultado C$",
        ])

        total_ingreso = total_costo = total_gasto = dinero(0)
        for fila in movimientos:
            local = a_local(fila["fecha"], zona)
            ingreso = dinero(fila["ingreso"])
            costo = dinero(fila["costo"])
            gasto = dinero(fila["gasto"])
            resultado = restar(restar(ingreso, costo), gasto)
            total_ingreso += ingreso
            total_costo += costo
            total_gasto += gasto
            escritor.writerow([
                fila["tipo"],
                fila["referencia"],
                local.strftime("%Y-%m-%d %H:%M"),
                fila["detalle"],
                f"{ingreso:.2f}",
                f"{costo:.2f}",
                f"{gasto:.2f}",
                f"{resultado:.2f}",
            ])

        escritor.writerow([])
        escritor.writerow([
            "TOTAL", "", "", "",
            f"{dinero(total_ingreso):.2f}",
            f"{dinero(total_costo):.2f}",
            f"{dinero(total_gasto):.2f}",
            f"{restar(restar(total_ingreso, total_costo), total_gasto):.2f}",
        ])

        nombre = f"contabilidad_{dia_desde}_{dia_hasta}.csv"
        return Response(
            content="\ufeff" + salida.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
        )
