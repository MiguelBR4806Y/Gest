from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from Backend.db.database import get_db
import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

FACTURAS_DIR = "facturas"
NOMBRE_NEGOCIO = os.getenv("NOMBRE_NEGOCIO", "Mi Negocio")

DIAS_ES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

router = APIRouter(prefix="/facturas", tags=["Facturas"])


def fecha_a_nicaragua(fecha_hora_str: str) -> datetime:
    """Convierte una fecha UTC (texto) de la BD a un objeto datetime en hora de Nicaragua (GMT-6)."""
    limpio = fecha_hora_str.replace("T", " ")
    dt = datetime.strptime(limpio[:19], "%Y-%m-%d %H:%M:%S")
    return dt - timedelta(hours=6)


def formatear_fecha_hora(fecha_hora_str: str) -> str:
    """Texto legible en formato 12h para mostrar en la factura."""
    dt_nica = fecha_a_nicaragua(fecha_hora_str)
    return dt_nica.strftime("%d/%m/%Y %I:%M %p")


def sanitizar_nombre_carpeta(nombre: str) -> str:
    """Convierte el nombre del negocio en algo seguro para usar como carpeta."""
    limpio = re.sub(r"[^\w\s-]", "", nombre or "").strip()
    limpio = re.sub(r"\s+", "_", limpio)
    return limpio or "Negocio"


def carpeta_destino(nombre_negocio: str, fecha_nica: datetime) -> str:
    """
    Calcula la ruta de carpeta donde debe vivir la factura, siguiendo el esquema:
    facturas/{Nombre_Negocio}/Semana_{inicio}_a_{fin}/{DiaSemana}/
    La semana inicia en Lunes.
    """
    inicio_semana = fecha_nica - timedelta(days=fecha_nica.weekday())  # Lunes
    fin_semana = inicio_semana + timedelta(days=6)  # Domingo

    nombre_negocio_seguro = sanitizar_nombre_carpeta(nombre_negocio)
    nombre_semana = f"Semana_{inicio_semana.strftime('%Y-%m-%d')}_a_{fin_semana.strftime('%Y-%m-%d')}"
    nombre_dia = DIAS_ES[fecha_nica.weekday()]

    return os.path.join(FACTURAS_DIR, nombre_negocio_seguro, nombre_semana, nombre_dia)


def get_config_negocio(conn, usuario: str) -> dict:
    """Obtiene nombre, color y logo configurados por el usuario."""
    u = conn.execute(
        "SELECT nombre_negocio, color_acento, logo_path FROM usuarios WHERE usuario = ?",
        (usuario,)
    ).fetchone()

    if u:
        return {
            "nombre_negocio": u["nombre_negocio"] or NOMBRE_NEGOCIO,
            "color_acento": u["color_acento"] or "#1D9E75",
            "logo_path": u["logo_path"],
        }

    return {"nombre_negocio": NOMBRE_NEGOCIO, "color_acento": "#1D9E75", "logo_path": None}


def generar_pdf(venta_id, venta: dict, items: list, nombre_negocio: str = None, color_acento: str = None, logo_path: str = None) -> str:
    nombre = nombre_negocio or NOMBRE_NEGOCIO
    color = color_acento or "#1D9E75"

    # Determinar la carpeta permanente según el negocio y la fecha real de la venta
    fecha_nica = fecha_a_nicaragua(venta["fecha_hora"])
    carpeta = carpeta_destino(nombre, fecha_nica)
    os.makedirs(carpeta, exist_ok=True)

    path = os.path.join(carpeta, f"factura_{venta_id}.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    elementos = []

    # Logo (si existe y el archivo está en disco)
    if logo_path and os.path.exists(logo_path):
        try:
            elementos.append(Image(logo_path, width=1.5 * inch, height=1.5 * inch, kind='proportional'))
            elementos.append(Spacer(1, 0.1 * inch))
        except Exception:
            pass  # Si el archivo está dañado, simplemente no se muestra

    # Encabezado
    elementos.append(Paragraph(f"<b>{nombre}</b>", styles["Title"]))
    elementos.append(Spacer(1, 0.2 * inch))
    elementos.append(Paragraph(f"<b>Factura #</b>{venta_id}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Fecha:</b> {formatear_fecha_hora(venta['fecha_hora'])}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Cliente:</b> {venta['cliente_nombre'] or 'Consumidor final'}", styles["Normal"]))
    elementos.append(Spacer(1, 0.3 * inch))

    # Tabla de productos
    data = [["Producto", "Cantidad", "Precio unit.", "Subtotal"]]
    for item in items:
        subtotal = item["cantidad"] * item["precio_unitario"]
        data.append([
            item["nombre"],
            str(item["cantidad"]),
            f"C$ {item['precio_unitario']:.2f}",
            f"C$ {subtotal:.2f}"
        ])

    data.append(["", "", "Total:", f"C$ {venta['total']:.2f}"])

    tabla = Table(data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
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
    usuario: str = Query(default="root"),
):
    with get_db() as conn:
        config = get_config_negocio(conn, usuario)

    venta_dict = {
        "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cliente_nombre": "Cliente de ejemplo",
        "total": 20500.00,
    }
    items_list = [
        {"nombre": "PlayStation 5", "cantidad": 1, "precio_unitario": 20500.00}
    ]

    path = generar_pdf("preview", venta_dict, items_list, nombre_negocio, color_acento, config["logo_path"])
    return FileResponse(path, media_type="application/pdf")


@router.get("/{venta_id}")
def obtener_factura(venta_id: int, usuario: str = Query(default="root")):
    with get_db() as conn:
        config = get_config_negocio(conn, usuario)

        venta = conn.execute("""
            SELECT v.id, v.total, v.fecha_hora, c.nombre as cliente_nombre
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.id = ?
        """, (venta_id,)).fetchone()

        if not venta:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        items = conn.execute("""
            SELECT p.nombre, vi.cantidad, vi.precio_unitario
            FROM venta_items vi
            JOIN productos p ON vi.producto_id = p.id
            WHERE vi.venta_id = ?
        """, (venta_id,)).fetchall()

        venta_dict = dict(venta)
        items_list = [dict(i) for i in items]

    path = generar_pdf(venta_id, venta_dict, items_list, config["nombre_negocio"], config["color_acento"], config["logo_path"])
    return FileResponse(path, media_type="application/pdf")