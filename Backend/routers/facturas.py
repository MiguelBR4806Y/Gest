from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from Backend.db.database import get_db
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FACTURAS_DIR = "facturas"
NOMBRE_NEGOCIO = os.getenv("NOMBRE_NEGOCIO", "Mi Negocio")

router = APIRouter(prefix="/facturas", tags=["Facturas"])

def get_nombre_negocio(conn, usuario: str) -> str:
    u = conn.execute(
        "SELECT nombre_negocio FROM usuarios WHERE usuario = ?",
        (usuario,)
    ).fetchone()
    return u["nombre_negocio"] if u else os.getenv("NOMBRE_NEGOCIO", "Mi Negocio")


def generar_pdf(venta_id: int, venta: dict, items: list, nombre_negocio: str = None) -> str:
    nombre = nombre_negocio or NOMBRE_NEGOCIO
    path = os.path.join(FACTURAS_DIR, f"factura_{venta_id}.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    elementos = []

    # Encabezado
    elementos.append(Paragraph(f"<b>{nombre}</b>", styles["Title"]))
    elementos.append(Spacer(1, 0.2 * inch))
    elementos.append(Paragraph(f"<b>Factura #</b>{venta_id}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Fecha:</b> {venta['fecha_hora']}", styles["Normal"]))
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

    # Total
    data.append(["", "", "Total:", f"C$ {venta['total']:.2f}"])

    tabla = Table(data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D9E75")),
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


@router.get("/{venta_id}")
def obtener_factura(venta_id: int, usuario: str = Query(default="root")):
    path = os.path.join(FACTURAS_DIR, f"factura_{venta_id}.pdf")

    with get_db() as conn:
        # Obtener nombre del negocio desde la BD
        nombre = get_nombre_negocio(conn, usuario)

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

    # Siempre regenerar para reflejar nombre actualizado
    generar_pdf(venta_id, venta_dict, items_list, nombre)
    return FileResponse(path, media_type="application/pdf")