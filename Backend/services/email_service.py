import html
import logging
import os
import secrets
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

logger = logging.getLogger("app")

SMTP_HOST = os.getenv("SMTP_HOST", "")
try:
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
except ValueError:
    SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@bravosgest.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Minutos de validez del código de verificación de correo.
CODIGO_MINUTOS_VALIDO = 15

# Minutos de validez del enlace de recuperación de contraseña.
RESET_MINUTOS_VALIDO = 30
CODIGO_LONGITUD = 6
SMTP_TIMEOUT = 15


def generar_codigo() -> str:
    """Código numérico criptográficamente seguro."""
    limite = 10 ** CODIGO_LONGITUD
    return str(secrets.randbelow(limite - 10 ** (CODIGO_LONGITUD - 1)) + 10 ** (CODIGO_LONGITUD - 1))


def smtp_configurado() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


def enviar_verificacion(destinatario: str, codigo: str, nombre_negocio: str) -> bool:
    if not smtp_configurado():
        logger.warning("SMTP no configurado; no se pudo enviar el código de verificación")
        return False

    # `nombre_negocio` viene del usuario: se escapa para no inyectar HTML en el correo.
    negocio = html.escape(nombre_negocio or "tu negocio", quote=True)
    anio = datetime.now(timezone.utc).year
    asunto = f"Tu código de verificación - {nombre_negocio or 'Bravo\u2019s Gest'}"

    texto_plano = f"""{asunto}

Gracias por registrarte en {nombre_negocio}.

Tu código de verificación es: {codigo}
Caduca en {CODIGO_MINUTOS_VALIDO} minutos.

Si no solicitaste este código, ignora este mensaje.

© {anio} {nombre_negocio}
"""

    html_cuerpo = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;padding:40px 16px">
<tr><td align="center">
  <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden">
    <tr><td style="padding:36px 32px 24px">
      <h1 style="margin:0 0 16px;font-size:22px;color:#1a1a1a;font-weight:700;text-align:center">
        Código de verificación
      </h1>
      <p style="margin:0 0 24px;font-size:15px;color:#555;line-height:1.6;text-align:center">
        Gracias por registrarte en <strong style="color:#1a1a1a">{negocio}</strong>.
        Usa el siguiente código para verificar tu correo:
      </p>
      <div style="text-align:center;margin:24px 0 28px">
        <span style="display:inline-block;font-size:40px;font-weight:700;letter-spacing:10px;color:#1D9E75;background:#f0faf6;padding:12px 28px;border-radius:8px">
          {html.escape(codigo)}
        </span>
      </div>
      <p style="margin:0 0 8px;font-size:13px;color:#999;text-align:center">
        Caduca en {CODIGO_MINUTOS_VALIDO} minutos.
      </p>
      <p style="margin:0;font-size:13px;color:#999;text-align:center">
        Si no solicitaste este código, ignora este mensaje.
      </p>
    </td></tr>
    <tr><td style="padding:16px 32px;background-color:#fafafa;border-top:1px solid #eee">
      <p style="margin:0;font-size:12px;color:#aaa;text-align:center">
        © {anio} {negocio}
      </p>
    </td></tr>
  </table>
</td></tr></table></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = SMTP_FROM
    msg["To"] = destinatario
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg["Message-ID"] = f"<{secrets.token_hex(8)}.{datetime.now(timezone.utc).timestamp()}@bravosgest.local>"
    msg["MIME-Version"] = "1.0"
    msg.attach(MIMEText(texto_plano, "plain", "utf-8"))
    msg.attach(MIMEText(html_cuerpo, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [destinatario], msg.as_string())
        return True
    except Exception:
        # Se registra el tipo de error, nunca las credenciales ni el código.
        logger.exception("Fallo al enviar el correo de verificación")
        return False


def enlace_reset(token: str) -> str:
    """URL del formulario de nueva contraseña (token siempre escapado)."""
    base = FRONTEND_URL.rstrip("/")
    return f"{base}/reset?token={quote(token, safe='')}"


def _enviar_mensaje(destinatario: str, asunto: str, texto_plano: str, html_cuerpo: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = SMTP_FROM
    msg["To"] = destinatario
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg["Message-ID"] = (
        f"<{secrets.token_hex(8)}.{datetime.now(timezone.utc).timestamp()}@bravosgest.local>"
    )
    msg["MIME-Version"] = "1.0"
    msg.attach(MIMEText(texto_plano, "plain", "utf-8"))
    msg.attach(MIMEText(html_cuerpo, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [destinatario], msg.as_string())
    return True


def enviar_reset(destinatario: str, token: str, nombre_negocio: str) -> bool:
    """Envía el enlace para restablecer la contraseña.

    El token va en la URL; el correo solo lo ve quien controla el buzón.
    """
    if not smtp_configurado():
        logger.warning("SMTP no configurado; no se pudo enviar el enlace de recuperación")
        return False

    negocio = html.escape(nombre_negocio or "tu negocio", quote=True)
    anio = datetime.now(timezone.utc).year
    asunto = f"Restablece tu contraseña - {nombre_negocio or 'Bravo\u2019s Gest'}"
    enlace = enlace_reset(token)
    enlace_html = html.escape(enlace, quote=True)

    texto_plano = f"""{asunto}

Recibimos una solicitud para restablecer la contraseña de {nombre_negocio}.

Abre este enlace para crear una nueva contraseña:
{enlace}

El enlace caduca en {RESET_MINUTOS_VALIDO} minutos y solo puede usarse una vez.

Si no solicitaste este cambio, ignora este mensaje: tu contraseña actual sigue siendo válida.

© {anio} {nombre_negocio}
"""

    html_cuerpo = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;padding:40px 16px">
<tr><td align="center">
  <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden">
    <tr><td style="padding:36px 32px 24px">
      <h1 style="margin:0 0 16px;font-size:22px;color:#1a1a1a;font-weight:700;text-align:center">
        Restablece tu contraseña
      </h1>
      <p style="margin:0 0 24px;font-size:15px;color:#555;line-height:1.6;text-align:center">
        Recibimos una solicitud para la cuenta de
        <strong style="color:#1a1a1a">{negocio}</strong>.
      </p>
      <div style="text-align:center;margin:24px 0 28px">
        <a href="{enlace_html}" style="display:inline-block;background:#1D9E75;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:14px 28px;border-radius:8px">
          Crear nueva contraseña
        </a>
      </div>
      <p style="margin:0 0 8px;font-size:13px;color:#999;text-align:center">
        El enlace caduca en {RESET_MINUTOS_VALIDO} minutos y solo puede usarse una vez.
      </p>
      <p style="margin:0;font-size:13px;color:#999;text-align:center">
        Si no solicitaste este cambio, ignora este mensaje.
      </p>
    </td></tr>
    <tr><td style="padding:16px 32px;background-color:#fafafa;border-top:1px solid #eee">
      <p style="margin:0;font-size:12px;color:#aaa;text-align:center">© {anio} {negocio}</p>
    </td></tr>
  </table>
</td></tr></table></body></html>"""

    try:
        return _enviar_mensaje(destinatario, asunto, texto_plano, html_cuerpo)
    except Exception:
        logger.exception("Fallo al enviar el correo de recuperación")
        return False
