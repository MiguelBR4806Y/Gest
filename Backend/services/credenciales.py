"""Generación y cifrado de credenciales de vendedores.

El login sigue usando bcrypt (irreversible), pero el administrador debe poder
consultar la contraseña de sus vendedores en cualquier momento, así que se
guarda además una copia cifrada con Fernet. La clave se deriva de SECRET_KEY:
cambiarla invalida las credenciales guardadas, y entonces el admin debe
regenerarlas.
"""

import base64
import hashlib
import os
import re
import secrets
import string
import unicodedata

from cryptography.fernet import Fernet, InvalidToken

from Backend.security import validar_password

# Sin caracteres ambiguos: la contraseña se dicta por teléfono.
ALFABETO_PASSWORD = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
LONGITUD_PASSWORD = 12
MAX_INTENTOS_USUARIO = 100

_USUARIO_INVALIDO = re.compile(r"[^A-Za-z0-9._-]+")


def _clave_fernet() -> bytes:
    secreto = os.getenv("SECRET_KEY", "")
    if not secreto:
        raise RuntimeError("SECRET_KEY no está configurada en el entorno")
    return base64.urlsafe_b64encode(hashlib.sha256(secreto.encode("utf-8")).digest())


def cifrar_password(password: str) -> str:
    return Fernet(_clave_fernet()).encrypt(password.encode("utf-8")).decode("ascii")


def descifrar_password(cifrado: str | None) -> str | None:
    """Devuelve la contraseña o None si el texto está corrupto o la clave cambió."""
    if not cifrado:
        return None
    try:
        return Fernet(_clave_fernet()).decrypt(cifrado.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def _slug(texto: str, maximo: int = 40) -> str:
    """Nombre de usuario legible: sin acentos ni espacios."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c)
    )
    limpio = _USUARIO_INVALIDO.sub(".", sin_acentos).strip(".-_")
    return limpio.lower()[:maximo].strip(".-_")


def generar_usuario(nombre: str, session) -> str:
    """Usuario único a partir del nombre: `ana.perez`, `ana.perez2`, ..."""
    from Backend.db.models import Usuario

    base = _slug(nombre) or "vendedor"
    if len(base) < 3:
        base = f"{base}{secrets.randbelow(90) + 10}"
    candidato = base
    for intento in range(1, MAX_INTENTOS_USUARIO + 1):
        if not session.query(Usuario.id).filter(Usuario.usuario == candidato).first():
            return candidato[:64]
        sufijo = str(intento + 1)
        candidato = f"{base[: 64 - len(sufijo)]}{sufijo}"
    # Fallback improbable: sufijo aleatorio para no fallar por colisión.
    return f"{base[:56]}.{secrets.token_hex(3)}"


def generar_password() -> str:
    """Contraseña aleatoria que cumple la política (`validar_password`)."""
    while True:
        letras = "".join(secrets.choice(ALFABETO_PASSWORD) for _ in range(LONGITUD_PASSWORD - 4))
        digitos = "".join(secrets.choice(string.digits) for _ in range(4))
        caracteres = list(letras + digitos)
        secrets.SystemRandom().shuffle(caracteres)
        candidata = "".join(caracteres)
        if validar_password(candidata) is None:
            return candidata


def usuario_valido(usuario: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]{3,64}", usuario or ""))
