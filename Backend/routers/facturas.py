from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from Backend.db.database import get_db
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

FACTURAS_DIR = "facturas"
NOMBRE_NEGOCIO = os.getenv("NOMBRE_NEGOCIO", "Mi Negocio")

router = APIRouter(prefix="/facturas", tags=["Facturas"])


def formatear_fecha_hora(fecha_hora_str: str) -> str:
    """Convierte una fecha UTC de la BD a hora de Nicaragua (GMT-6) en formato 12h."""
    limpio = fecha_hora_str.replace("T", " ")
    dt = datetime.strptime(limpio[:19], "%Y-%m-%d %H:%M:%S")
    dt_nica = dt - timedelta(hours=6)
    return dt_nica.strftime("%d/%m/%Y %I:%M %p")


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

    os.makedirs(FACTURAS_DIR, exist_ok=True)

    path = os.path.join(FACTURAS_DIR, f"factura_{venta_id}.pdf")
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