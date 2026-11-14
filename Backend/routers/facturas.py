import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote as urlquote

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import text

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import EnlaceFactura, Usuario
from Backend.dinero import dinero
from Backend.routers.auth import requiere_admin, requiere_modulo, verificar_token
from Backend.security import es_color_hex, escapar_xml, limitar, sanear_texto
from Backend.services.email_service import enviar_factura, smtp_configurado
from Backend.tiempo import ZONA_POR_DEFECTO, a_local

load_dotenv()

FACTURAS_DIR = "facturas"
NOMBRE_NEGOCIO = os.getenv("NOMBRE_NEGOCIO", "Mi Negocio")
# Base de las URLs de descarga que se envían al cliente final.
PUBLIC_BASE_URL = (
    os.getenv("PUBLIC_BASE_URL") or os.getenv("FRONTEND_URL") or "http://localhost:5173"
).rstrip("/")

# Días que vive un enlace de factura compartido por WhatsApp.
ENLACE_DIAS_VALIDO = 7
PREFIJO_PAIS = "505"

DIAS_ES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

router = APIRouter(prefix="/facturas", tags=["Facturas"])

# Ver y enviar facturas lo necesita quien vende. La descarga por token es
# pública a propósito y no lleva esta dependencia.
_VENTAS = [Depends(requiere_modulo("ventas"))]


def fmt(valor) -> str:
    """Formato con separador de miles a partir del Decimal exacto."""
    return f"{dinero(valor):,.2f}"


def a_zona(fecha_hora, zona=ZONA_POR_DEFECTO) -> datetime:
    return a_local(fecha_hora, zona)


def formatear_fecha_hora(fecha_hora_str, zona=ZONA_POR_DEFECTO) -> str:
    dt = a_zona(fecha_hora_str, zona)
    return dt.strftime("%d/%m/%Y %I:%M %p")


def sanitizar_nombre_carpeta(nombre: str) -> str:
    limpio = re.sub(r"[^\w\s-]", "", nombre or "").strip()
    limpio = re.sub(r"\s+", "_", limpio)
    return limpio or "Negocio"


def carpeta_destino(nombre_negocio: str, fecha_local: datetime) -> str:
    from datetime import timedelta

    inicio_semana = fecha_local - timedelta(days=fecha_local.weekday())
    fin_semana = inicio_semana + timedelta(days=6)

    nombre_negocio_seguro = sanitizar_nombre_carpeta(nombre_negocio)
    nombre_semana = f"Semana_{inicio_semana.strftime('%Y-%m-%d')}_a_{fin_semana.strftime('%Y-%m-%d')}"
    nombre_dia = DIAS_ES[fecha_local.weekday()]

    return os.path.join(FACTURAS_DIR, nombre_negocio_seguro, nombre_semana, nombre_dia)


def get_config_negocio(session, usuario_id: int) -> dict:
    u = session.query(Usuario).filter(Usuario.id == usuario_id).first()

    if u:
        return {
            "nombre_negocio": u.nombre_negocio or NOMBRE_NEGOCIO,
            "color_acento": u.color_acento or "#1D9E75",
            "logo_path": u.logo_path,
            "tasa_cambio": u.tasa_cambio or 36.0,
            "zona_horaria": u.zona_horaria or ZONA_POR_DEFECTO,
        }

    return {
        "nombre_negocio": NOMBRE_NEGOCIO,
        "color_acento": "#1D9E75",
        "logo_path": None,
        "tasa_cambio": dinero(36),
        "zona_horaria": ZONA_POR_DEFECTO,
    }


def generar_pdf(
    venta_id,
    venta: dict,
    items: list,
    nombre_negocio: str = None,
    color_acento: str = None,
    logo_path: str = None,
    tasa_cambio=36,
    zona_horaria: str = ZONA_POR_DEFECTO,
    estado: str = "completada",
) -> str:
    # Estos valores llegan por query string y acaban dentro de un Paragraph de
    # reportlab, que interpreta marcado tipo <b>. Se sanean antes de usarlos.
    nombre = sanear_texto(nombre_negocio, 120) or NOMBRE_NEGOCIO
    color = color_acento if es_color_hex(color_acento or "") else "#1D9E75"
    tasa = dinero(tasa_cambio) or dinero(36)

    fecha_local = a_zona(venta["fecha_hora"], zona_horaria)
    carpeta = carpeta_destino(nombre, fecha_local)
    os.makedirs(carpeta, exist_ok=True)

    path = os.path.join(carpeta, f"factura_{venta_id}.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    elementos = []

    if logo_path and os.path.exists(logo_path):
        try:
            elementos.append(Image(logo_path, width=1.5 * inch, height=1.5 * inch, kind="proportional"))
            elementos.append(Spacer(1, 0.1 * inch))
        except Exception:
            pass

    elementos.append(Paragraph(f"<b>{escapar_xml(nombre)}</b>", styles["Title"]))
    elementos.append(Spacer(1, 0.2 * inch))

    if estado == "anulada":
        aviso = ParagraphStyle(
            "Anulada", parent=styles["Normal"], textColor=colors.HexColor("#B91C1C"),
            fontSize=13, spaceBefore=4, spaceAfter=8,
        )
        elementos.append(Paragraph("<b>VENTA ANULADA</b>", aviso))

    elementos.append(Paragraph(f"<b>Factura #</b>{venta_id}", styles["Normal"]))
    elementos.append(Paragraph(
        f"<b>Fecha:</b> {formatear_fecha_hora(venta['fecha_hora'], zona_horaria)}",
        styles["Normal"],
    ))
    cliente = escapar_xml(sanear_texto(venta.get("cliente_nombre"), 120) or "Consumidor final")
    elementos.append(Paragraph(f"<b>Cliente:</b> {cliente}", styles["Normal"]))
    elementos.append(Spacer(1, 0.3 * inch))

    cell_style = ParagraphStyle("CellStyle", parent=styles["Normal"], fontSize=8)

    data = [[
        Paragraph("Producto", styles["Normal"]),
        Paragraph("Cant.", styles["Normal"]),
        Paragraph("Precio Unit.", styles["Normal"]),
        Paragraph("Subtotal", styles["Normal"]),
    ]]
    for item in items:
        precio = dinero(item["precio_unitario"])
        subtotal = dinero(precio * int(item["cantidad"]))
        data.append([
            Paragraph(escapar_xml(sanear_texto(item["nombre"], 120)), cell_style),
            Paragraph(str(item["cantidad"]), cell_style),
            Paragraph(f"C$ {fmt(precio)}<br/>US$ {fmt(precio / tasa)}", cell_style),
            Paragraph(f"C$ {fmt(subtotal)}<br/>US$ {fmt(subtotal / tasa)}", cell_style),
        ])

    total = dinero(venta["total"])
    data.append([
        Paragraph("", cell_style),
        Paragraph("", cell_style),
        Paragraph("<b>Total:</b>", styles["Normal"]),
        Paragraph(f"<b>C$ {fmt(total)}</b><br/><b>US$ {fmt(total / tasa)}</b>", styles["Normal"]),
    ])

    tabla = Table(data, colWidths=[3 * inch, 0.7 * inch, 1.65 * inch, 1.65 * inch])
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

    # Detalle del cobro en efectivo, si lo hubo.
    efectivo = venta.get("efectivo_recibido")
    vuelto = venta.get("vuelto")
    if efectivo is not None:
        elementos.append(Spacer(1, 0.15 * inch))
        elementos.append(Paragraph(
            f"<b>Efectivo recibido:</b> C$ {fmt(efectivo)}", styles["Normal"]
        ))
        if vuelto is not None:
            elementos.append(Paragraph(
                f"<b>Vuelto:</b> C$ {fmt(vuelto)}", styles["Normal"]
            ))

    elementos.append(Spacer(1, 0.3 * inch))
    elementos.append(Paragraph("Gracias por su compra.", styles["Normal"]))

    doc.build(elementos)
    return path


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _datos_venta(session, venta_id: int, usuario_id: int) -> tuple[dict, list[dict]]:
    venta = session.execute(
        text("""
            SELECT v.id, v.total, v.fecha_hora, v.estado,
                   v.efectivo_recibido, v.vuelto,
                   c.nombre AS cliente_nombre, c.telefono AS cliente_telefono,
                   c.email AS cliente_email
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.id = :vid AND v.usuario_id = :uid
        """),
        {"vid": venta_id, "uid": usuario_id},
    ).mappings().first()

    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    items = session.execute(
        text("""
            SELECT p.nombre, vi.cantidad, vi.precio_unitario
            FROM venta_items vi
            JOIN productos p ON vi.producto_id = p.id
            JOIN ventas v ON vi.venta_id = v.id
            WHERE vi.venta_id = :vid AND v.usuario_id = :uid
        """),
        {"vid": venta_id, "uid": usuario_id},
    ).mappings().fetchall()

    return dict(venta), [dict(i) for i in items]


def _generar_archivo(session, venta_id: int, usuario_id: int) -> tuple[str, dict]:
    """Genera (o regenera) el PDF y devuelve su ruta junto a los datos de venta."""
    config = get_config_negocio(session, usuario_id)
    venta_dict, items_list = _datos_venta(session, venta_id, usuario_id)
    path = generar_pdf(
        venta_id, venta_dict, items_list, config["nombre_negocio"],
        config["color_acento"], config["logo_path"], config["tasa_cambio"],
        config["zona_horaria"], venta_dict.get("estado", "completada"),
    )
    return path, venta_dict


def _normalizar_telefono(telefono: str | None) -> str:
    """Deja solo dígitos y añade el prefijo de país si parece local."""
    digitos = re.sub(r"\D", "", telefono or "")
    if not digitos:
        return ""
    if len(digitos) == 8:
        return PREFIJO_PAIS + digitos
    return digitos


def _crear_enlace(session, usuario_id: int, venta_id: int) -> dict:
    token = secrets.token_urlsafe(24)
    expira = datetime.now(timezone.utc) + timedelta(days=ENLACE_DIAS_VALIDO)
    enlace = EnlaceFactura(
        usuario_id=usuario_id,
        venta_id=venta_id,
        token_hash=_hash_token(token),
        expira=expira,
    )
    session.add(enlace)
    session.flush()
    return {
        "url": f"{PUBLIC_BASE_URL}/facturas/descarga/{token}",
        "token": token,
        "expira": expira.isoformat(),
    }


class EnvioFactura(BaseModel):
    canal: str = Field(pattern="^(email|whatsapp)$")
    destinatario: str | None = Field(default=None, max_length=254)


@router.get("/preview", dependencies=[Depends(requiere_admin)])
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
        "total": dinero(20500),
    }
    items_list = [
        {"nombre": "PlayStation 5", "cantidad": 1, "precio_unitario": dinero(20500)}
    ]

    path = generar_pdf(
        "preview", venta_dict, items_list, nombre_negocio, color_acento,
        config["logo_path"], config["tasa_cambio"], config["zona_horaria"],
    )
    return FileResponse(path, media_type="application/pdf")


@router.get("/descarga/{token}", dependencies=[Depends(limitar(60, 300, "descarga-factura"))])
def descargar_por_token(token: str):
    """Descarga pública de una factura compartida. No requiere sesión.

    El token es aleatorio, caduca y no se guarda en claro: quien lo tiene puede
    descargar la factura, y solo esa.
    """
    if not token or len(token) < 20 or len(token) > 128:
        raise HTTPException(status_code=404, detail="Enlace no válido")

    with get_db() as session:
        enlace = session.query(EnlaceFactura).filter(
            EnlaceFactura.token_hash == _hash_token(token)
        ).first()

        if not enlace:
            raise HTTPException(status_code=404, detail="Enlace no válido")

        expira = enlace.expira
        if expira is not None:
            if expira.tzinfo is None:
                expira = expira.replace(tzinfo=timezone.utc)
            if expira < datetime.now(timezone.utc):
                raise HTTPException(status_code=404, detail="El enlace ha caducado")

        path, _venta = _generar_archivo(session, enlace.venta_id, enlace.usuario_id)
        venta_id = enlace.venta_id
        enlace.usos = (enlace.usos or 0) + 1

    with open(path, "rb") as archivo:
        contenido = archivo.read()

    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="factura_{venta_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{venta_id}/enlace", dependencies=_VENTAS)
def enlace_factura(venta_id: int, usuario_id: int = Depends(verificar_token)):
    """Crea un enlace de descarga y el texto listo para WhatsApp."""
    with get_db() as session:
        config = get_config_negocio(session, usuario_id)
        venta, _items = _datos_venta(session, venta_id, usuario_id)
        enlace = _crear_enlace(session, usuario_id, venta_id)

    telefono = _normalizar_telefono(venta.get("cliente_telefono"))
    mensaje = (
        f"Hola {venta.get('cliente_nombre') or ''}, aquí está tu factura #{venta_id} "
        f"de {config['nombre_negocio']}: {enlace['url']}"
    ).replace("  ", " ").strip()

    whatsapp_url = f"https://wa.me/{telefono}?text={urlquote(mensaje)}" if telefono else None
    return {
        "url": enlace["url"],
        "expira": enlace["expira"],
        "telefono": telefono,
        "mensaje": mensaje,
        "whatsapp_url": whatsapp_url,
    }


@router.post("/{venta_id}/enviar", dependencies=_VENTAS)
def enviar_factura_venta(
    venta_id: int,
    datos: EnvioFactura,
    usuario_id: int = Depends(verificar_token),
):
    with get_db() as session:
        path, venta = _generar_archivo(session, venta_id, usuario_id)
        config = get_config_negocio(session, usuario_id)

        if datos.canal == "email":
            destinatario = sanear_texto(datos.destinatario, 254) or venta.get("cliente_email")
            if not destinatario:
                raise HTTPException(
                    status_code=400,
                    detail="El cliente no tiene correo; escribe uno para enviarla",
                )
            if not smtp_configurado():
                raise HTTPException(
                    status_code=503, detail="El envío de correo no está configurado"
                )

            with open(path, "rb") as archivo:
                pdf = archivo.read()

            enlace = _crear_enlace(session, usuario_id, venta_id)
            enviado = enviar_factura(
                destinatario, pdf, config["nombre_negocio"], venta_id, enlace["url"]
            )
            if not enviado:
                raise HTTPException(
                    status_code=502, detail="No se pudo enviar el correo, intenta de nuevo"
                )

            registrar_evento(
                session, usuario_id, "factura_enviada", "venta", venta_id,
                f"canal=email destino={destinatario[:64]}",
            )
            return {"mensaje": "Factura enviada por correo", "destinatario": destinatario}

        # WhatsApp: no hay API de Meta; se devuelve el enlace wa.me listo.
        enlace = _crear_enlace(session, usuario_id, venta_id)
        telefono = _normalizar_telefono(datos.destinatario or venta.get("cliente_telefono"))
        mensaje = (
            f"Hola {venta.get('cliente_nombre') or ''}, aquí está tu factura #{venta_id} "
            f"de {config['nombre_negocio']}: {enlace['url']}"
        ).replace("  ", " ").strip()

        registrar_evento(
            session, usuario_id, "factura_enviada", "venta", venta_id,
            f"canal=whatsapp destino={telefono or 'sin teléfono'}",
        )
        return {
            "mensaje": "Enlace de WhatsApp generado",
            "url": enlace["url"],
            "telefono": telefono or None,
            "mensaje_texto": mensaje,
            "whatsapp_url": (
                f"https://wa.me/{telefono}?text={urlquote(mensaje)}" if telefono else None
            ),
        }


@router.get("/{venta_id}", dependencies=_VENTAS)
def obtener_factura(venta_id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        path, _venta = _generar_archivo(session, venta_id, usuario_id)
    return FileResponse(path, media_type="application/pdf")
