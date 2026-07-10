from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from Backend.db.database import get_db
from Backend.db.models import Usuario
from Backend.routers.auth import verificar_token
from sqlalchemy import text
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

FACTURAS_DIR = "facturas"
NOMBRE_NEGOCIO = os.getenv("NOMBRE_NEGOCIO", "Mi Negocio")

DIAS_ES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

router = APIRouter(prefix="/facturas", tags=["Facturas"])


def fmt(valor: float) -> str:
    return f"{valor:,.2f}"


def a_zona(fecha_hora, zona="America/Managua") -> datetime:
    tz = ZoneInfo(zona)
    if isinstance(fecha_hora, datetime):
        return fecha_hora.astimezone(tz)
    limpio = fecha_hora.replace("T", " ")
    dt = datetime.strptime(limpio[:19], "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)


def formatear_fecha_hora(fecha_hora_str: str, zona="America/Managua") -> str:
    dt = a_zona(fecha_hora_str, zona)
    return dt.strftime("%d/%m/%Y %I:%M %p")


def sanitizar_nombre_carpeta(nombre: str) -> str:
    limpio = re.sub(r"[^\w\s-]", "", nombre or "").strip()
    limpio = re.sub(r"\s+", "_", limpio)
    return limpio or "Negocio"


def carpeta_destino(nombre_negocio: str, fecha_nica: datetime) -> str:
    inicio_semana = fecha_nica - timedelta(days=fecha_nica.weekday())
    fin_semana = inicio_semana + timedelta(days=6)

    nombre_negocio_seguro = sanitizar_nombre_carpeta(nombre_negocio)
    nombre_semana = f"Semana_{inicio_semana.strftime('%Y-%m-%d')}_a_{fin_semana.strftime('%Y-%m-%d')}"
    nombre_dia = DIAS_ES[fecha_nica.weekday()]

    return os.path.join(FACTURAS_DIR, nombre_negocio_seguro, nombre_semana, nombre_dia)


def get_config_negocio(session, usuario_id: int) -> dict:
    u = session.query(Usuario).filter(Usuario.id == usuario_id).first()

    if u:
        return {
            "nombre_negocio": u.nombre_negocio or NOMBRE_NEGOCIO,
            "color_acento": u.color_acento or "#1D9E75",
            "logo_path": u.logo_path,
            "tasa_cambio": u.tasa_cambio or 36.0,
            "zona_horaria": u.zona_horaria or "America/Managua",
        }

    return {"nombre_negocio": NOMBRE_NEGOCIO, "color_acento": "#1D9E75", "logo_path": None, "tasa_cambio": 36.0, "zona_horaria": "America/Managua"}


def generar_pdf(venta_id, venta: dict, items: list, nombre_negocio: str = None, color_acento: str = None, logo_path: str = None, tasa_cambio: float = 36.0, zona_horaria: str = "America/Managua") -> str:
    nombre = nombre_negocio or NOMBRE_NEGOCIO
    color = color_acento or "#1D9E75"

    fecha_nica = a_zona(venta["fecha_hora"], zona_horaria)
    carpeta = carpeta_destino(nombre, fecha_nica)
    os.makedirs(carpeta, exist_ok=True)

    path = os.path.join(carpeta, f"factura_{venta_id}.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    elementos = []

    if logo_path and os.path.exists(logo_path):
        try:
            elementos.append(Image(logo_path, width=1.5 * inch, height=1.5 * inch, kind='proportional'))
            elementos.append(Spacer(1, 0.1 * inch))
        except Exception:
            pass

    elementos.append(Paragraph(f"<b>{nombre}</b>", styles["Title"]))
    elementos.append(Spacer(1, 0.2 * inch))
    elementos.append(Paragraph(f"<b>Factura #</b>{venta_id}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Fecha:</b> {formatear_fecha_hora(venta['fecha_hora'], zona_horaria)}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Cliente:</b> {venta['cliente_nombre'] or 'Consumidor final'}", styles["Normal"]))
    elementos.append(Spacer(1, 0.3 * inch))

    cell_style = ParagraphStyle("CellStyle", parent=styles["Normal"], fontSize=8)

    data = [[
        Paragraph("Producto", styles["Normal"]),
        Paragraph("Cant.", styles["Normal"]),
        Paragraph("Precio Unit.", styles["Normal"]),
        Paragraph("Subtotal", styles["Normal"])
    ]]
    for item in items:
        subtotal = item["cantidad"] * item["precio_unitario"]
        subtotal_usd = subtotal / tasa_cambio
        pu_usd = item["precio_unitario"] / tasa_cambio
        data.append([
            Paragraph(item["nombre"], cell_style),
            Paragraph(str(item["cantidad"]), cell_style),
            Paragraph(f"C$ {fmt(item['precio_unitario'])}<br/>US$ {fmt(pu_usd)}", cell_style),
            Paragraph(f"C$ {fmt(subtotal)}<br/>US$ {fmt(subtotal_usd)}", cell_style),
        ])

    total_usd = venta["total"] / tasa_cambio
    data.append([
        Paragraph("", cell_style),
        Paragraph("", cell_style),
        Paragraph("<b>Total:</b>", styles["Normal"]),
        Paragraph(f"<b>C$ {fmt(venta['total'])}</b><br/><b>US$ {fmt(total_usd)}</b>", styles["Normal"]),
    ])

    tabla = Table(data, colWidths=[3*inch, 0.7*inch, 1.65*inch, 1.65*inch])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 0.3 * inch))
    elementos.append(Paragraph("Gracias por su compra.", styles["Normal"]))

    doc.build(elementos)
    return path


@router.get("/preview")
def previsualizar_factura(
    nombre_negocio: str = Query(default="Mi Negocio"),
    color_acento: str = Query(default="#1D9E75"),
    usuario_id: int = Depends(verificar_token),
):
    with get_db() as session:
        config = get_config_negocio(session, usuario_id)

    venta_dict = {
        "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cliente_nombre": "Cliente de ejemplo",
        "total": 20500.00,
    }
    items_list = [
        {"nombre": "PlayStation 5", "cantidad": 1, "precio_unitario": 20500.00}
    ]

    path = generar_pdf("preview", venta_dict, items_list, nombre_negocio, color_acento, config["logo_path"], config["tasa_cambio"], config["zona_horaria"])
    return FileResponse(path, media_type="application/pdf")


@router.get("/{venta_id}")
def obtener_factura(venta_id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        config = get_config_negocio(session, usuario_id)

        venta = session.execute(
            text("""
                SELECT v.id, v.total, v.fecha_hora, c.nombre as cliente_nombre
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.id = :vid AND v.usuario_id = :uid
            """),
            {"vid": venta_id, "uid": usuario_id}
        ).mappings().first()

        if not venta:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        items = session.execute(
            text("""
                SELECT p.nombre, vi.cantidad, vi.precio_unitario
                FROM venta_items vi
                JOIN productos p ON vi.producto_id = p.id
                WHERE vi.venta_id = :vid
            """),
            {"vid": venta_id}
        ).mappings().fetchall()

        venta_dict = dict(venta)
        items_list = [dict(i) for i in items]

    path = generar_pdf(venta_id, venta_dict, items_list, config["nombre_negocio"], config["color_acento"], config["logo_path"], config["tasa_cambio"], config["zona_horaria"])
    return FileResponse(path, media_type="application/pdf")
