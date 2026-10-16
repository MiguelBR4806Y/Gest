"""Utilidades de seguridad transversales al backend.

Todo es autocontenido: no agrega dependencias nuevas al proyecto.
"""
from __future__ import annotations

import hmac
import ipaddress
import os
import re
import time
import unicodedata
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

# ─────────────────────────────────────────────────────────────
# Rate limiting por ventana deslizante (en memoria, thread-safe)
# ─────────────────────────────────────────────────────────────

_MAX_BUCKETS = 20_000


class RateLimiter:
    """Limitador de peticiones por clave y ventana deslizante.

    Vive en memoria, así que es por proceso: con varios workers de uvicorn
    cada uno lleva su propia cuenta. Para un despliegue multi-instancia hay
    que moverlo a Redis manteniendo esta misma interfaz.
    """

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _poda(self, ahora: float) -> None:
        if len(self._buckets) <= _MAX_BUCKETS:
            return
        vacios = [k for k, v in self._buckets.items() if not v or ahora - v[-1] > 3600]
        for k in vacios:
            del self._buckets[k]

    def registrar(self, scope: str, clave: str, maximo: int, ventana: float) -> tuple[bool, float]:
        """Devuelve (permitido, segundos_hasta_libre)."""
        ahora = time.monotonic()
        with self._lock:
            eventos = self._buckets[(scope, clave)]
            while eventos and ahora - eventos[0] > ventana:
                eventos.popleft()
            if len(eventos) >= maximo:
                self._poda(ahora)
                return False, max(ventana - (ahora - eventos[0]), 1.0)
            eventos.append(ahora)
            self._poda(ahora)
            return True, 0.0

    def limpiar(self, scope: str, clave: str) -> None:
        with self._lock:
            self._buckets.pop((scope, clave), None)


rate_limiter = RateLimiter()


def ip_cliente(request: Request) -> str:
    """IP real del cliente.

    Solo confía en X-Forwarded-For cuando TRUST_PROXY_HEADERS=1, porque si no
    cualquiera puede falsear la cabecera y saltarse los límites por IP.
    """
    if os.getenv("TRUST_PROXY_HEADERS", "0") == "1":
        reenvio = request.headers.get("x-forwarded-for", "")
        if reenvio:
            candidata = reenvio.split(",")[0].strip()
            try:
                return ipaddress.ip_address(candidata).compressed
            except ValueError:
                pass
    return request.client.host if request.client else "desconocida"


def limitar(peticiones: int, segundos: float, scope: str):
    """Dependencia de FastAPI que limita a `peticiones` por `segundos` e IP."""

    def dependencia(request: Request) -> None:
        permitido, reintento = rate_limiter.registrar(
            scope, ip_cliente(request), peticiones, segundos
        )
        if not permitido:
            espera = int(reintento) + 1
            raise HTTPException(
                status_code=429,
                detail="Demasiadas solicitudes. Intenta de nuevo en unos segundos.",
                headers={"Retry-After": str(espera)},
            )

    return dependencia


# ─────────────────────────────────────────────────────────────
# Contraseñas
# ─────────────────────────────────────────────────────────────

# bcrypt trunca (o falla) pasado este tamaño; se valida antes de hashear.
MAX_BYTES_PASSWORD = 72
MIN_CARACTERES_PASSWORD = 8

_DEBILES = {
    "12345678", "123456789", "password", "contrasena", "contraseña",
    "qwertyui", "11111111", "00000000", "abcdefgh", "iloveyou",
    "changeme", "bravogest",
}


def validar_password(password: str) -> str | None:
    """Devuelve el motivo del rechazo, o None si la contraseña es aceptable."""
    if not password:
        return "La contraseña es obligatoria"
    if len(password) < MIN_CARACTERES_PASSWORD:
        return f"La contraseña debe tener al menos {MIN_CARACTERES_PASSWORD} caracteres"
    if len(password.encode("utf-8")) > MAX_BYTES_PASSWORD:
        return f"La contraseña no puede superar los {MAX_BYTES_PASSWORD} bytes"
    if password.lower() in _DEBILES:
        return "Esa contraseña es demasiado común, elige otra"

    tiene_letra = any(c.isalpha() for c in password)
    tiene_numero = any(c.isdigit() for c in password)
    if not (tiene_letra and tiene_numero):
        return "La contraseña debe combinar letras y números"
    return None


def comparar_seguro(a: str | None, b: str | None) -> bool:
    """Comparación en tiempo constante para códigos y secretos."""
    if a is None or b is None:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# ─────────────────────────────────────────────────────────────
# Validación de archivos subidos
# ─────────────────────────────────────────────────────────────

FIRMAS = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "pdf": (b"%PDF-",),
}

MIME_POR_FIRMA = {
    b"\x89PNG\r\n\x1a\n": ("png", "image/png"),
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"%PDF-": ("pdf", "application/pdf"),
}

MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_PLANTILLA_BYTES = 10 * 1024 * 1024


def detectar_tipo(cabecera: bytes) -> tuple[str, str] | None:
    """Identifica el archivo por sus bytes reales, no por el Content-Type declarado."""
    for firma, (extension, mime) in MIME_POR_FIRMA.items():
        if cabecera.startswith(firma):
            return extension, mime
    return None


async def leer_subida_segura(archivo, tipos: set[str], max_bytes: int, etiqueta: str) -> bytes:
    """Lee un UploadFile verificando tamaño real y firma de bytes.

    `tipos` usa las claves de FIRMAS ("png", "jpg", "pdf"). Lanza 400 si el
    contenido no coincide con lo declarado o si se pasa del límite.
    """
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=400, detail=f"El archivo {etiqueta} está vacío")
    if len(contenido) > max_bytes:
        limite_mb = max_bytes / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"El archivo {etiqueta} supera el límite de {limite_mb:.0f} MB",
        )

    detectado = detectar_tipo(contenido)
    if detectado is None or detectado[0] not in tipos:
        esperados = " o ".join(sorted(t.upper() for t in tipos))
        raise HTTPException(
            status_code=400,
            detail=f"El contenido real del archivo no es un {esperados} válido",
        )
    return contenido


def nombre_archivo_seguro(base: str, usuario_id: int, extension: str) -> str:
    """Nombre de archivo derivado solo del id de usuario: sin entrada del cliente."""
    return f"{base}_{int(usuario_id)}.{extension}"


def dentro_de(raiz: str, ruta: str) -> bool:
    """Comprueba que `ruta` resuelta quede dentro de `raiz` (anti path traversal)."""
    raiz_abs = os.path.realpath(raiz)
    ruta_abs = os.path.realpath(ruta)
    return ruta_abs == raiz_abs or ruta_abs.startswith(raiz_abs + os.sep)


# ─────────────────────────────────────────────────────────────
# Sanitización de texto
# ─────────────────────────────────────────────────────────────

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_ESPACIOS = re.compile(r"\s+")


def sanear_texto(valor: str | None, maximo: int = 200) -> str:
    """Normaliza unicode, quita caracteres de control y recorta longitud.

    Previene ataques de homoglifos y la inyección de marcado al generar PDFs
    con reportlab.
    """
    if not valor:
        return ""
    texto = unicodedata.normalize("NFKC", str(valor))
    texto = _CONTROL.sub("", texto)
    texto = _ESPACIOS.sub(" ", texto).strip()
    return texto[:maximo]


def escapar_xml(valor: str) -> str:
    """Escapa el marcado que reportlab interpretaría dentro de un Paragraph."""
    return (
        str(valor)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


_COLOR_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

ZONA_POR_DEFECTO = "America/Managua"


def es_color_hex(valor: str) -> bool:
    return bool(_COLOR_HEX.match(valor or ""))


def es_zona_horaria(valor: str) -> bool:
    from zoneinfo import ZoneInfo, available_timezones

    if not valor or len(valor) > 64:
        return False
    if valor not in available_timezones():
        return False
    try:
        ZoneInfo(valor)
        return True
    except Exception:
        return False
