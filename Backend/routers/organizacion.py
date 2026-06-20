from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response, FileResponse
from Backend.db.database import get_db
from Backend.routers.auth import verificar_token
from Backend.routers.facturas import (
    fecha_a_nicaragua, generar_pdf, get_config_negocio,
    carpeta_destino, sanitizar_nombre_carpeta
)
from datetime import datetime, timedelta
from jose import JWTError, jwt
import zipfile
import io
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/organizacion", tags=["Organización"])

SECRET_KEY = os.getenv("SECRET_KEY", "clave_secreta_por_defecto")
ALGORITHM = "HS256"
security = HTTPBearer(auto_error=False)

FACTURAS_DIR = "facturas"

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

TRIMESTRE_LABELS = {
    1: "Q1 - Enero a Marzo",
    2: "Q2 - Abril a Junio",
    3: "Q3 - Julio a Septiembre",
    4: "Q4 - Octubre a Diciembre",
}

SEMESTRE_LABELS = {
    1: "H1 - Enero a Junio",
    2: "H2 - Julio a Diciembre",
}


def semestre_de_mes(mes: int) -> int:
    return 1 if mes <= 6 else 2


def trimestre_de_mes(mes: int) -> int:
    return (mes - 1) // 3 + 1


def ruta_jerarquica(fn: datetime) -> str:
    anio = fn.year
    mes = fn.month
    s = semestre_de_mes(mes)
    t = trimestre_de_mes(mes)
    inicio_semana = fn - timedelta(days=fn.weekday())
    return (f"{anio}/H{s}/Q{t}/{MESES[mes]}"
            f"/Semana_{inicio_semana.strftime('%Y-%m-%d')}"
            f"/{DIAS_SEMANA[fn.weekday()]}")


def obtener_o_generar_pdf(venta: dict, conn, usuario_id: int, usuario: str) -> str:
    config = get_config_negocio(conn, usuario)
    fecha_nica = fecha_a_nicaragua(venta["fecha_hora"])
    carpeta = carpeta_destino(config["nombre_negocio"], fecha_nica)
    pdf_path = os.path.join(carpeta, f"factura_{venta['id']}.pdf")

    if os.path.exists(pdf_path):
        return pdf_path

    items = conn.execute("""
        SELECT p.nombre, vi.cantidad, vi.precio_unitario
        FROM venta_items vi
        JOIN productos p ON vi.producto_id = p.id
        WHERE vi.venta_id = ?
    """, (venta["id"],)).fetchall()

    return generar_pdf(
        venta["id"], dict(venta), [dict(i) for i in items],
        config["nombre_negocio"], config["color_acento"], config["logo_path"]
    )


def ventas_en_periodo(conn, usuario_id, nivel, anio=None, semestre=None,
                      trimestre=None, mes=None, semana=None, fecha=None,
                      factura_id=None):
    where = ["v.usuario_id = ?"]
    params = [usuario_id]

    if nivel == "factura":
        where.append("v.id = ?")
        params.append(factura_id)
    elif nivel == "dia":
        where.append("DATE(datetime(v.fecha_hora, '-6 hours')) = ?")
        params.append(fecha)
    else:
        where.append(
            "CAST(strftime('%Y', datetime(v.fecha_hora, '-6 hours')) AS INTEGER) = ?"
        )
        params.append(anio)

        if nivel in ("semestre",):
            if semestre == 1:
                where.append(
                    "CAST(strftime('%m', datetime(v.fecha_hora, '-6 hours'))"
                    " AS INTEGER) BETWEEN 1 AND 6"
                )
            else:
                where.append(
                    "CAST(strftime('%m', datetime(v.fecha_hora, '-6 hours'))"
                    " AS INTEGER) BETWEEN 7 AND 12"
                )
        elif nivel in ("trimestre",):
            m_min = (trimestre - 1) * 3 + 1
            m_max = trimestre * 3
            where.append(
                "CAST(strftime('%m', datetime(v.fecha_hora, '-6 hours'))"
                f" AS INTEGER) BETWEEN ? AND ?"
            )
            params.extend([m_min, m_max])
        elif nivel in ("mes",):
            where.append(
                "CAST(strftime('%m', datetime(v.fecha_hora, '-6 hours'))"
                " AS INTEGER) = ?"
            )
            params.append(mes)
        elif nivel in ("semana",):
            where.append(
                "CAST(strftime('%m', datetime(v.fecha_hora, '-6 hours'))"
                " AS INTEGER) = ?"
            )
            params.append(mes)

    if nivel == "semana" and semana:
        # Filter by the specific week
        try:
            inicio = datetime.strptime(semana, "%Y-%m-%d")
            fin = inicio + timedelta(days=6)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de semana invalido")
        where.append(
            "DATE(datetime(v.fecha_hora, '-6 hours')) BETWEEN ? AND ?"
        )
        params.extend([inicio.strftime("%Y-%m-%d"), fin.strftime("%Y-%m-%d")])

    query = f"""
        SELECT v.id, v.total, v.fecha_hora, v.metodo_pago,
               COALESCE(c.nombre, 'Consumidor final') as cliente_nombre
        FROM ventas v
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE {' AND '.join(where)}
        ORDER BY v.fecha_hora
    """
    return conn.execute(query, params).fetchall()


@router.get("/anios")
def listar_anios(usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT CAST(strftime('%Y', datetime(fecha_hora, '-6 hours')) AS INTEGER) as anio,
                   COUNT(*) as total_ventas,
                   COALESCE(SUM(total), 0) as total_ingresos
            FROM ventas
            WHERE usuario_id = ?
            GROUP BY anio
            ORDER BY anio DESC
        """, (usuario_id,)).fetchall()
        return {"anios": [dict(r) for r in rows]}


@router.get("/{anio}/semestres")
def listar_semestres(anio: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        semestres = []
        for s, (m_min, m_max) in [(1, (1, 6)), (2, (7, 12))]:
            row = conn.execute("""
                SELECT COUNT(*) as total_ventas, COALESCE(SUM(total), 0) as total_ingresos
                FROM ventas
                WHERE usuario_id = ?
                  AND CAST(strftime('%Y', datetime(fecha_hora, '-6 hours')) AS INTEGER) = ?
                  AND CAST(strftime('%m', datetime(fecha_hora, '-6 hours')) AS INTEGER) BETWEEN ? AND ?
            """, (usuario_id, anio, m_min, m_max)).fetchone()
            semestres.append({
                "semestre": s,
                "label": SEMESTRE_LABELS[s],
                "total_ventas": row["total_ventas"],
                "total_ingresos": row["total_ingresos"],
            })
        return {"semestres": semestres}


@router.get("/{anio}/{semestre}/trimestres")
def listar_trimestres(anio: int, semestre: int, usuario_id: int = Depends(verificar_token)):
    ranges = [(1, 1, 3), (2, 4, 6)] if semestre == 1 else [(3, 7, 9), (4, 10, 12)]
    with get_db() as conn:
        trimestres = []
        for t, m_min, m_max in ranges:
            row = conn.execute("""
                SELECT COUNT(*) as total_ventas, COALESCE(SUM(total), 0) as total_ingresos
                FROM ventas
                WHERE usuario_id = ?
                  AND CAST(strftime('%Y', datetime(fecha_hora, '-6 hours')) AS INTEGER) = ?
                  AND CAST(strftime('%m', datetime(fecha_hora, '-6 hours')) AS INTEGER) BETWEEN ? AND ?
            """, (usuario_id, anio, m_min, m_max)).fetchone()
            trimestres.append({
                "trimestre": t,
                "label": TRIMESTRE_LABELS[t],
                "total_ventas": row["total_ventas"],
                "total_ingresos": row["total_ingresos"],
            })
        return {"trimestres": trimestres}


@router.get("/{anio}/{trimestre}/meses")
def listar_meses(anio: int, trimestre: int, usuario_id: int = Depends(verificar_token)):
    m_min = (trimestre - 1) * 3 + 1
    m_max = trimestre * 3
    with get_db() as conn:
        rows = conn.execute("""
            SELECT CAST(strftime('%m', datetime(fecha_hora, '-6 hours')) AS INTEGER) as mes,
                   COUNT(*) as total_ventas,
                   COALESCE(SUM(total), 0) as total_ingresos
            FROM ventas
            WHERE usuario_id = ?
              AND CAST(strftime('%Y', datetime(fecha_hora, '-6 hours')) AS INTEGER) = ?
              AND CAST(strftime('%m', datetime(fecha_hora, '-6 hours')) AS INTEGER) BETWEEN ? AND ?
            GROUP BY mes
            ORDER BY mes
        """, (usuario_id, anio, m_min, m_max)).fetchall()
        meses = []
        for r in rows:
            d = dict(r)
            d["label"] = MESES[d["mes"]]
            meses.append(d)
        return {"meses": meses}


@router.get("/{anio}/{mes}/semanas")
def listar_semanas(anio: int, mes: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT DATE(datetime(fecha_hora, '-6 hours'),
                 '-' || ((CAST(strftime('%w', datetime(fecha_hora, '-6 hours')) AS INTEGER) + 6) % 7) || ' days') as inicio_semana,
                   COUNT(*) as total_ventas,
                   COALESCE(SUM(total), 0) as total_ingresos
            FROM ventas
            WHERE usuario_id = ?
              AND CAST(strftime('%Y', datetime(fecha_hora, '-6 hours')) AS INTEGER) = ?
              AND CAST(strftime('%m', datetime(fecha_hora, '-6 hours')) AS INTEGER) = ?
            GROUP BY inicio_semana
            ORDER BY inicio_semana
        """, (usuario_id, anio, mes)).fetchall()

        result = []
        for r in rows:
            inicio = datetime.strptime(r["inicio_semana"], "%Y-%m-%d")
            fin = inicio + timedelta(days=6)
            result.append({
                "inicio_semana": r["inicio_semana"],
                "label": f"Semana del {inicio.strftime('%d/%m')} al {fin.strftime('%d/%m')}",
                "total_ventas": r["total_ventas"],
                "total_ingresos": r["total_ingresos"],
            })
        return {"semanas": result}


@router.get("/{anio}/{mes}/{semana}/dias")
def listar_dias(anio: int, mes: int, semana: str, usuario_id: int = Depends(verificar_token)):
    try:
        inicio_semana = datetime.strptime(semana, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de semana invalido, use YYYY-MM-DD")

    with get_db() as conn:
        dias = []
        for i in range(7):
            dia = inicio_semana + timedelta(days=i)
            fecha_str = dia.strftime("%Y-%m-%d")
            row = conn.execute("""
                SELECT COUNT(*) as total_ventas, COALESCE(SUM(total), 0) as total_ingresos
                FROM ventas
                WHERE usuario_id = ?
                  AND DATE(datetime(fecha_hora, '-6 hours')) = ?
            """, (usuario_id, fecha_str)).fetchone()
            dias.append({
                "fecha": fecha_str,
                "dia_semana": i,
                "label": f"{DIAS_SEMANA[i]} {dia.strftime('%d/%m/%Y')}",
                "total_ventas": row["total_ventas"],
                "total_ingresos": row["total_ingresos"],
            })
        return {"dias": dias}


@router.get("/dia/{fecha}")
def facturas_del_dia(fecha: str, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT v.id, v.total, v.fecha_hora, v.metodo_pago,
                   COALESCE(c.nombre, 'Consumidor final') as cliente_nombre
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.usuario_id = ?
              AND DATE(datetime(v.fecha_hora, '-6 hours')) = ?
            ORDER BY v.fecha_hora DESC
        """, (usuario_id, fecha)).fetchall()
        return {"facturas": [dict(r) for r in rows]}


@router.get("/descargar")
def descargar(
    nivel: str = Query(...),
    anio: int = Query(default=None),
    semestre: int = Query(default=None),
    trimestre: int = Query(default=None),
    mes: int = Query(default=None),
    semana: str = Query(default=None),
    fecha: str = Query(default=None),
    factura_id: int = Query(default=None),
    usuario: str = Query(default=None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    usuario_id = None
    nombre_usuario = usuario or "root"

    if credentials:
        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            usuario_id = int(payload.get("sub"))
            nombre_usuario = payload.get("usuario", nombre_usuario)
        except JWTError:
            pass

    if usuario_id is None and usuario:
        with get_db() as conn:
            u = conn.execute(
                "SELECT id, usuario FROM usuarios WHERE usuario = ?", (usuario,)
            ).fetchone()
            if u:
                usuario_id = u["id"]
                nombre_usuario = u["usuario"]

    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    with get_db() as conn:
        ventas = ventas_en_periodo(
            conn, usuario_id, nivel, anio, semestre, trimestre,
            mes, semana, fecha, factura_id
        )

        if not ventas:
            raise HTTPException(status_code=404, detail="No hay facturas en este periodo")

        if nivel == "factura":
            items = conn.execute("""
                SELECT p.nombre, vi.cantidad, vi.precio_unitario
                FROM venta_items vi
                JOIN productos p ON vi.producto_id = p.id
                WHERE vi.venta_id = ?
            """, (factura_id,)).fetchall()

            config = get_config_negocio(conn, nombre_usuario)
            pdf_path = generar_pdf(
                factura_id, dict(ventas[0]), [dict(i) for i in items],
                config["nombre_negocio"], config["color_acento"], config["logo_path"]
            )
            return FileResponse(
                pdf_path, media_type="application/pdf",
                filename=f"factura_{factura_id}.pdf",
                headers={"Content-Disposition": f"attachment; filename=factura_{factura_id}.pdf"}
            )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for v in ventas:
                fn = fecha_a_nicaragua(v["fecha_hora"])
                rel_path = ruta_jerarquica(fn)
                pdf_path = obtener_o_generar_pdf(v, conn, usuario_id, nombre_usuario)
                arcname = f"{rel_path}/factura_{v['id']}.pdf"
                zf.write(pdf_path, arcname)

    buffer.seek(0)

    nombre_archivo = {
        "anio": f"facturas_{anio}",
        "semestre": f"facturas_{anio}_H{semestre}",
        "trimestre": f"facturas_{anio}_Q{trimestre}",
        "mes": f"facturas_{anio}_{MESES[mes] if mes else ''}",
        "semana": f"facturas_semana_{semana}",
        "dia": f"facturas_{fecha}",
    }.get(nivel, "facturas")

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}.zip"},
    )
