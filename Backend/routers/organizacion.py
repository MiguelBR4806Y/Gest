from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response, FileResponse
from Backend.db.database import get_db
from Backend.db.models import Usuario
from Backend.routers.auth import verificar_token
from Backend.routers.facturas import (
    a_zona, generar_pdf, get_config_negocio,
    carpeta_destino, sanitizar_nombre_carpeta
)
from sqlalchemy import text
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


def obtener_o_generar_pdf(venta: dict, session, usuario_id: int, usuario: str) -> str:
    config = get_config_negocio(session, usuario)
    fecha_nica = a_zona(venta["fecha_hora"], config["zona_horaria"])
    carpeta = carpeta_destino(config["nombre_negocio"], fecha_nica)
    pdf_path = os.path.join(carpeta, f"factura_{venta['id']}.pdf")

    if os.path.exists(pdf_path):
        return pdf_path

    items = session.execute(
        text("""
            SELECT p.nombre, vi.cantidad, vi.precio_unitario
            FROM venta_items vi
            JOIN productos p ON vi.producto_id = p.id
            WHERE vi.venta_id = :vid
        """),
        {"vid": venta["id"]}
    ).mappings().fetchall()

    return generar_pdf(
        venta["id"], dict(venta), [dict(i) for i in items],
        config["nombre_negocio"], config["color_acento"], config["logo_path"],
        config["tasa_cambio"], config["zona_horaria"]
    )


def ventas_en_periodo(session, usuario_id, nivel, anio=None, semestre=None,
                      trimestre=None, mes=None, semana=None, fecha=None,
                      factura_id=None):
    where = ["v.usuario_id = :uid"]
    params = {"uid": usuario_id}

    tz = "v.fecha_hora AT TIME ZONE 'America/Managua'"

    if nivel == "factura":
        where.append("v.id = :fid")
        params["fid"] = factura_id
    elif nivel == "dia":
        where.append(f"({tz})::date = :fecha")
        params["fecha"] = fecha
    else:
        where.append(f"EXTRACT(YEAR FROM {tz})::integer = :anio")
        params["anio"] = anio

        if nivel in ("semestre",):
            if semestre == 1:
                where.append(f"EXTRACT(MONTH FROM {tz})::integer BETWEEN 1 AND 6")
            else:
                where.append(f"EXTRACT(MONTH FROM {tz})::integer BETWEEN 7 AND 12")
        elif nivel in ("trimestre",):
            m_min = (trimestre - 1) * 3 + 1
            m_max = trimestre * 3
            where.append(f"EXTRACT(MONTH FROM {tz})::integer BETWEEN :m_min AND :m_max")
            params["m_min"] = m_min
            params["m_max"] = m_max
        elif nivel in ("mes",):
            where.append(f"EXTRACT(MONTH FROM {tz})::integer = :mes")
            params["mes"] = mes
        elif nivel in ("semana",):
            where.append(f"EXTRACT(MONTH FROM {tz})::integer = :mes")
            params["mes"] = mes

    if nivel == "semana" and semana:
        try:
            inicio = datetime.strptime(semana, "%Y-%m-%d")
            fin = inicio + timedelta(days=6)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de semana invalido")
        where.append(f"({tz})::date BETWEEN :semana_ini AND :semana_fin")
        params["semana_ini"] = inicio.strftime("%Y-%m-%d")
        params["semana_fin"] = fin.strftime("%Y-%m-%d")

    query = f"""
        SELECT v.id, v.total, v.fecha_hora, v.metodo_pago,
               COALESCE(c.nombre, 'Consumidor final') as cliente_nombre
        FROM ventas v
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE {' AND '.join(where)}
        ORDER BY v.fecha_hora
    """
    return session.execute(text(query), params).mappings().fetchall()


@router.get("/anios")
def listar_anios(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        rows = session.execute(
            text("""
                SELECT EXTRACT(YEAR FROM fecha_hora AT TIME ZONE 'America/Managua')::integer as anio,
                       COUNT(*) as total_ventas,
                       COALESCE(SUM(total), 0) as total_ingresos
                FROM ventas
                WHERE usuario_id = :uid
                GROUP BY anio
                ORDER BY anio DESC
            """),
            {"uid": usuario_id}
        ).mappings().fetchall()
        return {"anios": [dict(r) for r in rows]}


@router.get("/{anio}/semestres")
def listar_semestres(anio: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        semestres = []
        for s, (m_min, m_max) in [(1, (1, 6)), (2, (7, 12))]:
            row = session.execute(
                text("""
                    SELECT COUNT(*) as total_ventas, COALESCE(SUM(total), 0) as total_ingresos
                    FROM ventas
                    WHERE usuario_id = :uid
                      AND EXTRACT(YEAR FROM fecha_hora AT TIME ZONE 'America/Managua')::integer = :anio
                      AND EXTRACT(MONTH FROM fecha_hora AT TIME ZONE 'America/Managua')::integer BETWEEN :m_min AND :m_max
                """),
                {"uid": usuario_id, "anio": anio, "m_min": m_min, "m_max": m_max}
            ).mappings().first()
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
    with get_db() as session:
        trimestres = []
        for t, m_min, m_max in ranges:
            row = session.execute(
                text("""
                    SELECT COUNT(*) as total_ventas, COALESCE(SUM(total), 0) as total_ingresos
                    FROM ventas
                    WHERE usuario_id = :uid
                      AND EXTRACT(YEAR FROM fecha_hora AT TIME ZONE 'America/Managua')::integer = :anio
                      AND EXTRACT(MONTH FROM fecha_hora AT TIME ZONE 'America/Managua')::integer BETWEEN :m_min AND :m_max
                """),
                {"uid": usuario_id, "anio": anio, "m_min": m_min, "m_max": m_max}
            ).mappings().first()
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
    with get_db() as session:
        rows = session.execute(
            text("""
                SELECT EXTRACT(MONTH FROM fecha_hora AT TIME ZONE 'America/Managua')::integer as mes,
                       COUNT(*) as total_ventas,
                       COALESCE(SUM(total), 0) as total_ingresos
                FROM ventas
                WHERE usuario_id = :uid
                  AND EXTRACT(YEAR FROM fecha_hora AT TIME ZONE 'America/Managua')::integer = :anio
                  AND EXTRACT(MONTH FROM fecha_hora AT TIME ZONE 'America/Managua')::integer BETWEEN :m_min AND :m_max
                GROUP BY mes
                ORDER BY mes
            """),
            {"uid": usuario_id, "anio": anio, "m_min": m_min, "m_max": m_max}
        ).mappings().fetchall()
        meses = []
        for r in rows:
            d = dict(r)
            d["label"] = MESES[d["mes"]]
            meses.append(d)
        return {"meses": meses}


@router.get("/{anio}/{mes}/semanas")
def listar_semanas(anio: int, mes: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        rows = session.execute(
            text("""
                SELECT (fecha_hora AT TIME ZONE 'America/Managua')::date -
                       ((EXTRACT(DOW FROM fecha_hora AT TIME ZONE 'America/Managua')::integer + 6) % 7) as inicio_semana,
                       COUNT(*) as total_ventas,
                       COALESCE(SUM(total), 0) as total_ingresos
                FROM ventas
                WHERE usuario_id = :uid
                  AND EXTRACT(YEAR FROM fecha_hora AT TIME ZONE 'America/Managua')::integer = :anio
                  AND EXTRACT(MONTH FROM fecha_hora AT TIME ZONE 'America/Managua')::integer = :mes
                GROUP BY inicio_semana
                ORDER BY inicio_semana
            """),
            {"uid": usuario_id, "anio": anio, "mes": mes}
        ).mappings().fetchall()

        result = []
        for r in rows:
            inicio = datetime.strptime(str(r["inicio_semana"]), "%Y-%m-%d")
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

    with get_db() as session:
        dias = []
        for i in range(7):
            dia = inicio_semana + timedelta(days=i)
            fecha_str = dia.strftime("%Y-%m-%d")
            row = session.execute(
                text("""
                    SELECT COUNT(*) as total_ventas, COALESCE(SUM(total), 0) as total_ingresos
                    FROM ventas
                    WHERE usuario_id = :uid
                      AND (fecha_hora AT TIME ZONE 'America/Managua')::date = :fecha
                """),
                {"uid": usuario_id, "fecha": fecha_str}
            ).mappings().first()
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
    with get_db() as session:
        rows = session.execute(
            text("""
                SELECT v.id, v.total, v.fecha_hora, v.metodo_pago,
                       COALESCE(c.nombre, 'Consumidor final') as cliente_nombre
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.usuario_id = :uid
                  AND (v.fecha_hora AT TIME ZONE 'America/Managua')::date = :fecha
                ORDER BY v.fecha_hora DESC
            """),
            {"uid": usuario_id, "fecha": fecha}
        ).mappings().fetchall()
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
        with get_db() as session:
            u = session.query(Usuario).filter(Usuario.usuario == usuario).first()
            if u:
                usuario_id = u.id
                nombre_usuario = u.usuario

    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    with get_db() as session:
        config = get_config_negocio(session, nombre_usuario)
        zona_horaria = config["zona_horaria"]

        ventas = ventas_en_periodo(
            session, usuario_id, nivel, anio, semestre, trimestre,
            mes, semana, fecha, factura_id
        )

        if not ventas:
            raise HTTPException(status_code=404, detail="No hay facturas en este periodo")

        if nivel == "factura":
            items = session.execute(
                text("""
                    SELECT p.nombre, vi.cantidad, vi.precio_unitario
                    FROM venta_items vi
                    JOIN productos p ON vi.producto_id = p.id
                    WHERE vi.venta_id = :vid
                """),
                {"vid": factura_id}
            ).mappings().fetchall()

            pdf_path = generar_pdf(
                factura_id, dict(ventas[0]), [dict(i) for i in items],
                config["nombre_negocio"], config["color_acento"], config["logo_path"],
                config["tasa_cambio"], zona_horaria
            )
            return FileResponse(
                pdf_path, media_type="application/pdf",
                filename=f"factura_{factura_id}.pdf",
                headers={"Content-Disposition": f"attachment; filename=factura_{factura_id}.pdf"}
            )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for v in ventas:
                fn = a_zona(v["fecha_hora"], zona_horaria)
                rel_path = ruta_jerarquica(fn)
                pdf_path = obtener_o_generar_pdf(v, session, usuario_id, nombre_usuario)
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
