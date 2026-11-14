import hashlib
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import NamedTuple, Optional

import bcrypt
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import (
    ChatMensaje,
    Cliente,
    Compra,
    CompraItem,
    Empleado,
    EnlaceFactura,
    Evento,
    Gasto,
    Movimiento,
    Producto,
    Promocion,
    Proveedor,
    Usuario,
    Venta,
    VentaItem,
)
from Backend.dinero import a_float
from Backend.dinero import tasa_cambio as tasa_decimal
from Backend.models.schema import (
    GoogleOAuthData,
    RecuperarPassword,
    ResetPassword,
    TasaCambioData,
)
from Backend.security import (
    MAX_LOGO_BYTES,
    MAX_PLANTILLA_BYTES,
    ZONA_POR_DEFECTO,
    comparar_seguro,
    es_color_hex,
    es_zona_horaria,
    ip_cliente,
    leer_subida_segura,
    limitar,
    nombre_archivo_seguro,
    rate_limiter,
    sanear_texto,
    validar_password,
)
from Backend.services.email_service import (
    CODIGO_MINUTOS_VALIDO,
    RESET_MINUTOS_VALIDO,
    enlace_reset,
    enviar_reset,
    enviar_verificacion,
    generar_codigo,
)

logger = logging.getLogger("app")

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está configurada en el entorno")
if len(SECRET_KEY) < 32:
    # No es fatal, pero una clave corta debilita todo el esquema de JWT.
    logger.warning("SECRET_KEY tiene menos de 32 caracteres; genera una clave más larga")

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "12"))

# Módulos que el admin puede conceder a una cuenta hija. El admin los tiene
# todos implícitamente; una cuenta hija solo los asignados.
MODULOS = ("ventas", "rrhh", "contabilidad")

# Intentos de verificación de código antes de invalidarlo.
MAX_INTENTOS_CODIGO = 5

# Recuperación de contraseña: enlace de un solo uso y enfriamiento entre
# solicitudes para que nadie pueda inundar el buzón de un usuario.
RESET_COOLDOWN_SEGUNDOS = 60

LOGOS_DIR = "logos"
PLANTILLAS_DIR = "plantillas"

security = HTTPBearer(auto_error=False)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s.]+(\.[^@\s.]+)+$")

# Hash ficticio para que el login tarde lo mismo exista o no el usuario,
# evitando enumerar cuentas midiendo el tiempo de respuesta.
_HASH_DUMMY = bcrypt.hashpw(b"comparacion-de-tiempo-constante", bcrypt.gensalt()).decode()


class LoginData(BaseModel):
    usuario: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("usuario")
    @classmethod
    def _sanear_usuario(cls, v: str) -> str:
        limpio = sanear_texto(v, 64)
        if not limpio:
            raise ValueError("El usuario es obligatorio")
        return limpio


class RegistroData(BaseModel):
    usuario: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    email: Optional[str] = Field(default=None, max_length=254)
    nombre_negocio: str = Field(default="Mi Negocio", min_length=1, max_length=120)
    tasa_cambio: float = Field(default=36.0, gt=0, le=1_000_000)

    @field_validator("usuario")
    @classmethod
    def _sanear_usuario(cls, v: str) -> str:
        limpio = sanear_texto(v, 64)
        if not re.fullmatch(r"[A-Za-z0-9._-]{3,64}", limpio):
            raise ValueError("El usuario solo admite letras, números, punto, guion y guion bajo")
        return limpio

    @field_validator("password")
    @classmethod
    def _politica(cls, v: str) -> str:
        problema = validar_password(v)
        if problema:
            raise ValueError(problema)
        return v

    @field_validator("email")
    @classmethod
    def _validar_email(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("El correo electrónico no es válido")
        return v

    @field_validator("nombre_negocio")
    @classmethod
    def _sanear_negocio(cls, v: str) -> str:
        limpio = sanear_texto(v, 120)
        if not limpio:
            raise ValueError("El nombre del negocio es obligatorio")
        return limpio


class PerfilData(BaseModel):
    nombre_negocio: str = Field(min_length=1, max_length=120)
    email: Optional[str] = Field(default=None, max_length=254)
    color_acento: str = Field(default="#1D9E75", max_length=9)
    tasa_cambio: float = Field(default=36.0, gt=0, le=1_000_000)
    zona_horaria: str = Field(default=ZONA_POR_DEFECTO, max_length=64)

    @field_validator("nombre_negocio")
    @classmethod
    def _sanear_negocio(cls, v: str) -> str:
        limpio = sanear_texto(v, 120)
        if not limpio:
            raise ValueError("El nombre del negocio es obligatorio")
        return limpio

    @field_validator("email")
    @classmethod
    def _validar_email(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("El correo electrónico no es válido")
        return v

    @field_validator("color_acento")
    @classmethod
    def _validar_color(cls, v: str) -> str:
        color = (v or "").strip()
        if not es_color_hex(color):
            raise ValueError("El color de acento debe ser hexadecimal, ej. #1D9E75")
        return color.upper()

    @field_validator("zona_horaria")
    @classmethod
    def _validar_zona(cls, v: str) -> str:
        zona = (v or ZONA_POR_DEFECTO).strip()
        if not es_zona_horaria(zona):
            raise ValueError("Zona horaria no reconocida")
        return zona


class CambioPasswordData(BaseModel):
    password_actual: str = Field(min_length=1, max_length=128)
    password_nuevo: str = Field(min_length=1, max_length=128)

    @field_validator("password_nuevo")
    @classmethod
    def _politica(cls, v: str) -> str:
        problema = validar_password(v)
        if problema:
            raise ValueError(problema)
        return v


class EliminarCuentaData(BaseModel):
    password: str = Field(default="", max_length=128)


class VerificarCodigoData(BaseModel):
    codigo: str = Field(min_length=4, max_length=12)

    @field_validator("codigo")
    @classmethod
    def _solo_digitos(cls, v: str) -> str:
        limpio = re.sub(r"\D", "", v)
        if not limpio:
            raise ValueError("El código debe ser numérico")
        return limpio


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def crear_token(usuario_id: int, usuario: str, version: int = 0) -> str:
    ahora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(usuario_id),
            "usuario": usuario,
            "ver": int(version or 0),
            "iat": int(ahora.timestamp()),
            "exp": ahora + timedelta(hours=TOKEN_EXPIRE_HOURS),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


class SesionActual(NamedTuple):
    """Identidad de la petición separada en cuenta y negocio.

    `usuario_id` es la cuenta que inició sesión (admin o subordinado);
    `negocio_id` es el dueño de los datos sobre los que se opera. Para el admin
    ambos coinciden; para una cuenta hija, `negocio_id` es el id de su dueño.

    `modulos` define qué puede hacer: el admin los tiene todos, y una cuenta
    hija solo los que el admin le asignó. `rol` se conserva como jerarquía
    (dueño vs. subordinado) porque ya está en la base y en los JWT existentes.
    """

    usuario_id: int
    negocio_id: int
    rol: str
    nombre: str
    modulos: frozenset[str]
    es_admin: bool


def modulos_de(u: Usuario) -> frozenset[str]:
    """Módulos efectivos de una cuenta. El admin siempre tiene los tres."""
    if (u.rol or "admin") == "admin":
        return frozenset(MODULOS)
    # Cuentas anteriores a los módulos: se les deja el acceso de ventas que
    # tenían, en vez de dejarlas sin nada.
    crudos = (u.modulos or "").split(",")
    return frozenset(m.strip() for m in crudos if m.strip() in MODULOS) or frozenset(
        {"ventas"}
    )


def sesion_actual(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> SesionActual:
    """Valida el JWT y comprueba en BD que la cuenta siga activa y no revocada."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = int(payload["sub"])
        version = int(payload.get("ver", 0))
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido")

    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=401, detail="Token inválido")
        # Revocación exacta: cambiar la contraseña incrementa la versión y
        # todos los tokens emitidos con la versión anterior dejan de valer.
        if version != (u.token_version or 0):
            raise HTTPException(status_code=401, detail="Sesión expirada, inicia sesión de nuevo")
        if u.activo is False:
            raise HTTPException(status_code=401, detail="Cuenta desactivada")

        rol = u.rol or "admin"
        es_admin = rol == "admin"
        if es_admin:
            negocio_id = u.id
        else:
            negocio_id = u.dueno_id
            if not negocio_id:
                raise HTTPException(status_code=401, detail="Token inválido")

        return SesionActual(
            usuario_id=u.id,
            negocio_id=negocio_id,
            rol=rol,
            nombre=u.nombre or u.usuario,
            modulos=modulos_de(u),
            es_admin=es_admin,
        )


def verificar_token(sesion: SesionActual = Depends(sesion_actual)) -> int:
    """Id del negocio dueño de los datos.

    Se mantiene el nombre para que los routers existentes no cambien: cada
    consulta sigue filtrando por `usuario_id`, pero ahora un vendedor opera
    sobre los datos de su admin.
    """
    return sesion.negocio_id


def requiere_admin(sesion: SesionActual = Depends(sesion_actual)) -> SesionActual:
    if not sesion.es_admin:
        raise HTTPException(status_code=403, detail="Solo el administrador puede hacer esto")
    return sesion


def requiere_modulo(*modulos: str):
    """Dependencia que exige al menos uno de los módulos indicados.

    Devuelve una función para poder usarse como `Depends(requiere_modulo("rrhh"))`.
    El admin pasa siempre, sin importar la lista.
    """
    exigidos = set(modulos)

    def _dependencia(sesion: SesionActual = Depends(sesion_actual)) -> SesionActual:
        if sesion.es_admin or exigidos & sesion.modulos:
            return sesion
        raise HTTPException(status_code=403, detail="No tienes acceso a este módulo")

    return _dependencia


def usuario_a_respuesta(u: Usuario, session) -> dict:
    negocio = u
    if u.rol == "vendedor" and u.dueno_id:
        # El vendedor hereda la configuración visual y operativa del negocio.
        negocio = session.query(Usuario).filter(Usuario.id == u.dueno_id).first() or u
    return {
        "token": crear_token(u.id, u.usuario, u.token_version or 0),
        "usuario": u.usuario,
        "nombre": u.nombre or u.usuario,
        "rol": u.rol or "admin",
        "modulos": sorted(modulos_de(u)),
        "negocio_id": negocio.id,
        "email": u.email,
        "email_verified": u.email_verified,
        "provider": u.provider,
        "nombre_negocio": negocio.nombre_negocio,
        "color_acento": negocio.color_acento,
        "tasa_cambio": a_float(negocio.tasa_cambio),
        "tasa_cambio_configurada": negocio.tasa_cambio_configurada,
        "zona_horaria": negocio.zona_horaria,
    }


def _hash_token(token: str) -> str:
    """Se guarda el SHA-256: una filtración de la tabla no permite usarlo."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Respuesta idéntica exista o no la cuenta: no se puede enumerar usuarios.
MENSAJE_RECUPERACION = (
    "Si el usuario o correo existe y tiene un correo configurado, "
    "te enviamos un enlace para restablecer la contraseña."
)


def _enviar_reset(email: str, token: str, nombre_negocio: str) -> None:
    if enviar_reset(email, token, nombre_negocio):
        return
    logger.warning("SMTP no disponible; no se pudo enviar el enlace de recuperación a %s", email)
    # El enlace solo se registra si se pide explícitamente (entornos de
    # desarrollo sin SMTP). En producción nunca debe acabar en el log.
    if os.getenv("LOG_RESET_LINK", "0") == "1":
        logger.warning("Enlace de recuperación para %s: %s", email, enlace_reset(token))


def _emitir_codigo(u: Usuario) -> str:
    """Genera y persiste un código de verificación con fecha de caducidad."""
    codigo = generar_codigo()
    u.verificacion_token = codigo
    u.verificacion_intentos = 0
    u.verificacion_expira = datetime.now(timezone.utc) + timedelta(minutes=CODIGO_MINUTOS_VALIDO)
    return codigo


def _enviar_codigo(email: str, codigo: str, nombre_negocio: str) -> None:
    if enviar_verificacion(email, codigo, nombre_negocio):
        return
    # Sin SMTP el flujo no puede completarse: queda en el log del servidor,
    # nunca se devuelve al cliente.
    logger.warning("SMTP no disponible; código de verificación para %s: %s", email, codigo)


@router.post("/registro", dependencies=[Depends(limitar(5, 3600, "registro"))])
def registro(datos: RegistroData):
    with get_db() as session:
        if session.query(Usuario).filter(Usuario.usuario == datos.usuario).first():
            raise HTTPException(status_code=400, detail="El usuario ya existe")

        if datos.email:
            if session.query(Usuario).filter(Usuario.email == datos.email).first():
                raise HTTPException(status_code=400, detail="El email ya está registrado")

        usuario = Usuario(
            usuario=datos.usuario,
            password=hash_password(datos.password),
            email=datos.email,
            nombre_negocio=datos.nombre_negocio,
            tasa_cambio=tasa_decimal(datos.tasa_cambio),
            tasa_cambio_configurada=True,
        )
        session.add(usuario)
        session.flush()

        codigo = None
        if datos.email:
            codigo = _emitir_codigo(usuario)
            session.flush()

    if codigo:
        _enviar_codigo(datos.email, codigo, datos.nombre_negocio)

    return {
        "mensaje": "Usuario registrado exitosamente."
        + (" Se ha enviado un código de verificación a tu correo." if datos.email else "")
    }


@router.post("/login", dependencies=[Depends(limitar(10, 60, "login"))])
def login(datos: LoginData, request: Request):
    with get_db() as session:
        usuario = session.query(Usuario).filter(
            Usuario.usuario == datos.usuario
        ).first()

        # Se compara contra un hash ficticio cuando el usuario no existe,
        # para igualar el tiempo de respuesta.
        hash_a_comparar = usuario.password if (usuario and usuario.password) else _HASH_DUMMY
        credenciales_ok = verify_password(datos.password, hash_a_comparar)

        if not usuario or not credenciales_ok:
            logger.info("Login fallido para %r desde %s", datos.usuario, ip_cliente(request))
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

        rate_limiter.limpiar("login", ip_cliente(request))
        return usuario_a_respuesta(usuario, session)


@router.post("/oauth/google", dependencies=[Depends(limitar(10, 60, "oauth"))])
def login_google(datos: GoogleOAuthData):
    if not GOOGLE_CLIENT_ID:
        # Sin audience configurado no se puede confiar en ningún token de Google.
        raise HTTPException(status_code=503, detail="El inicio de sesión con Google no está configurado")

    try:
        resp = httpx.get(
            "https://www.googleapis.com/oauth2/v3/tokeninfo",
            params={"id_token": datos.credential},
            timeout=10,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Error al verificar el token con Google")

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    info = resp.json()
    email = info.get("email")
    google_id = info.get("sub")

    if not email or not google_id:
        raise HTTPException(status_code=400, detail="El token de Google no contiene email válido")
    if info.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="El token no pertenece a esta aplicación")
    if info.get("iss") not in GOOGLE_ISSUERS:
        raise HTTPException(status_code=401, detail="Emisor del token no reconocido")
    if not info.get("email_verified", False):
        raise HTTPException(status_code=401, detail="El correo de Google no está verificado")

    email = email.strip().lower()

    with get_db() as session:
        usuario = session.query(Usuario).filter(Usuario.email == email).first()
        if usuario:
            return usuario_a_respuesta(usuario, session)

        base = sanear_texto(email.split("@")[0], 60) or "usuario"
        username = base
        contador = 1
        while session.query(Usuario).filter(Usuario.usuario == username).first():
            username = f"{base}_{contador}"[:64]
            contador += 1

        nombre = sanear_texto(info.get("name", ""), 120)
        usuario = Usuario(
            usuario=username,
            password=None,
            email=email,
            email_verified=True,
            provider="google",
            provider_id=google_id,
            nombre_negocio=nombre or f"Negocio de {base}",
            tasa_cambio=36.0,
            tasa_cambio_configurada=True,
        )
        session.add(usuario)
        session.flush()
        return usuario_a_respuesta(usuario, session)


@router.post("/recuperar", dependencies=[Depends(limitar(5, 900, "recuperar"))])
def recuperar_password(datos: RecuperarPassword, request: Request):
    """Envía un enlace de recuperación. La respuesta nunca revela si existe."""
    identificador = datos.identificador.strip()

    # Trabajo constante aunque la cuenta no exista, para no filtrar por tiempo.
    _hash_token(identificador)

    token = None
    email = None
    negocio = None

    with get_db() as session:
        u = session.query(Usuario).filter(
            or_(
                Usuario.usuario == identificador,
                Usuario.email == identificador.lower(),
            )
        ).first()

        if u and u.email:
            ahora = datetime.now(timezone.utc)
            anterior = u.reset_solicitado_en
            if anterior is not None:
                if anterior.tzinfo is None:
                    anterior = anterior.replace(tzinfo=timezone.utc)
                if (ahora - anterior).total_seconds() < RESET_COOLDOWN_SEGUNDOS:
                    return {"mensaje": MENSAJE_RECUPERACION}

            token = secrets.token_urlsafe(32)
            u.reset_token_hash = _hash_token(token)
            u.reset_expira = ahora + timedelta(minutes=RESET_MINUTOS_VALIDO)
            u.reset_solicitado_en = ahora
            email, negocio = u.email, u.nombre_negocio
            registrar_evento(
                session, u.id, "recuperacion_solicitada", "usuario", u.id,
                "enlace de restablecimiento enviado",
            )

    if token and email:
        _enviar_reset(email, token, negocio)

    return {"mensaje": MENSAJE_RECUPERACION}


@router.post("/reset", dependencies=[Depends(limitar(5, 900, "reset-password"))])
def reset_password(datos: ResetPassword):
    """Cambia la contraseña con un token válido y revoca todas las sesiones."""
    with get_db() as session:
        u = session.query(Usuario).filter(
            Usuario.reset_token_hash == _hash_token(datos.token)
        ).first()

        if not u:
            raise HTTPException(
                status_code=400,
                detail="El enlace es inválido o ya fue utilizado",
            )

        expira = u.reset_expira
        if expira is not None and expira.tzinfo is None:
            expira = expira.replace(tzinfo=timezone.utc)

        if expira is None or expira < datetime.now(timezone.utc):
            # Se invalida al caducar para que no quede reutilizable. Hay que
            # confirmar antes de lanzar: get_db hace rollback en la excepción.
            u.reset_token_hash = None
            u.reset_expira = None
            session.commit()
            raise HTTPException(
                status_code=400,
                detail="El enlace expiró, solicita uno nuevo",
            )

        u.password = hash_password(datos.password_nuevo)
        u.password_cambiada_en = datetime.now(timezone.utc)
        u.token_version = (u.token_version or 0) + 1
        u.reset_token_hash = None
        u.reset_expira = None
        u.reset_solicitado_en = None

        registrar_evento(
            session, u.id, "password_restablecida", "usuario", u.id,
            "recuperación por correo",
        )

    return {
        "mensaje": "Contraseña actualizada. Inicia sesión con la nueva contraseña."
    }


@router.get("/perfil")
def obtener_perfil(sesion: SesionActual = Depends(sesion_actual)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == sesion.usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        negocio = session.query(Usuario).filter(Usuario.id == sesion.negocio_id).first() or u
        return {
            "usuario": u.usuario,
            "nombre": u.nombre or u.usuario,
            "rol": u.rol or "admin",
            "modulos": sorted(modulos_de(u)),
            "negocio_id": sesion.negocio_id,
            "nombre_negocio": negocio.nombre_negocio,
            "email": u.email,
            "email_verified": u.email_verified,
            "provider": u.provider,
            "logo_path": negocio.logo_path,
            "color_acento": negocio.color_acento,
            "modo_factura": negocio.modo_factura,
            "tasa_cambio": negocio.tasa_cambio,
            "tasa_cambio_configurada": negocio.tasa_cambio_configurada,
            "zona_horaria": negocio.zona_horaria,
        }


@router.put(
    "/perfil",
    dependencies=[Depends(limitar(30, 60, "perfil")), Depends(requiere_admin)],
)
def actualizar_perfil(datos: PerfilData, sesion: SesionActual = Depends(sesion_actual)):
    email_nuevo = datos.email or None
    usuario_id = sesion.usuario_id

    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        updates = {
            Usuario.nombre_negocio: datos.nombre_negocio,
            Usuario.color_acento: datos.color_acento,
            Usuario.tasa_cambio: tasa_decimal(datos.tasa_cambio),
            Usuario.tasa_cambio_configurada: True,
            Usuario.zona_horaria: datos.zona_horaria,
        }

        email_cambio = bool(email_nuevo) and email_nuevo != u.email

        if email_nuevo:
            if session.query(Usuario).filter(
                Usuario.email == email_nuevo, Usuario.id != usuario_id
            ).first():
                raise HTTPException(status_code=400, detail="El correo ya está registrado por otro usuario")
            updates[Usuario.email] = email_nuevo
        else:
            updates[Usuario.email] = None

        if email_cambio:
            updates[Usuario.email_verified] = False

        session.query(Usuario).filter(Usuario.id == usuario_id).update(updates)

        codigo = None
        if email_cambio:
            renovado = session.query(Usuario).filter(Usuario.id == usuario_id).first()
            codigo = _emitir_codigo(renovado)
            session.flush()

    if codigo:
        _enviar_codigo(email_nuevo, codigo, datos.nombre_negocio)

    return {"mensaje": "Perfil actualizado correctamente"}


@router.put("/password", dependencies=[Depends(limitar(5, 900, "password"))])
def cambiar_password(datos: CambioPasswordData, sesion: SesionActual = Depends(sesion_actual)):
    usuario_id = sesion.usuario_id
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if u.password is None:
            raise HTTPException(status_code=400, detail="No puedes cambiar la contraseña de una cuenta de Google")
        if not verify_password(datos.password_actual, u.password):
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
        if datos.password_nuevo == datos.password_actual:
            raise HTTPException(status_code=400, detail="La nueva contraseña debe ser distinta a la actual")

        u.password = hash_password(datos.password_nuevo)
        # Invalida todos los tokens emitidos antes de este momento.
        u.password_cambiada_en = datetime.now(timezone.utc)
        u.token_version = (u.token_version or 0) + 1
        return {"mensaje": "Contraseña actualizada correctamente"}


@router.post("/enviar-verificacion", dependencies=[Depends(limitar(5, 900, "verificacion-envio"))])
def enviar_verificacion_endpoint(sesion: SesionActual = Depends(sesion_actual)):
    usuario_id = sesion.usuario_id
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if not u.email:
            raise HTTPException(status_code=400, detail="No tienes un correo configurado")
        if u.email_verified:
            raise HTTPException(status_code=400, detail="El correo ya está verificado")

        codigo = _emitir_codigo(u)
        session.flush()
        email, negocio = u.email, u.nombre_negocio

    _enviar_codigo(email, codigo, negocio)
    return {"mensaje": "Código de verificación enviado a tu correo"}


@router.post("/verificar-codigo", dependencies=[Depends(limitar(10, 900, "verificacion-codigo"))])
def verificar_codigo(datos: VerificarCodigoData, sesion: SesionActual = Depends(sesion_actual)):
    usuario_id = sesion.usuario_id
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if not u.verificacion_token:
            raise HTTPException(status_code=400, detail="No hay un código pendiente de verificación")

        expira = u.verificacion_expira
        if expira is not None:
            if expira.tzinfo is None:
                expira = expira.replace(tzinfo=timezone.utc)
            if expira < datetime.now(timezone.utc):
                u.verificacion_token = None
                session.commit()
                raise HTTPException(status_code=400, detail="El código ha expirado, solicita uno nuevo")

        if (u.verificacion_intentos or 0) >= MAX_INTENTOS_CODIGO:
            u.verificacion_token = None
            u.verificacion_intentos = 0
            session.commit()
            raise HTTPException(
                status_code=400,
                detail="Demasiados intentos fallidos, solicita un código nuevo",
            )

        if not comparar_seguro(u.verificacion_token, datos.codigo):
            u.verificacion_intentos = (u.verificacion_intentos or 0) + 1
            restantes = MAX_INTENTOS_CODIGO - u.verificacion_intentos
            raise HTTPException(
                status_code=400,
                detail=f"Código incorrecto. Te quedan {max(restantes, 0)} intento(s).",
            )

        u.email_verified = True
        u.verificacion_token = None
        u.verificacion_intentos = 0
        u.verificacion_expira = None
        return {"mensaje": "Correo verificado exitosamente"}


@router.delete(
    "/cuenta",
    dependencies=[Depends(limitar(3, 3600, "eliminar-cuenta")), Depends(requiere_admin)],
)
def eliminar_cuenta(datos: EliminarCuentaData, sesion: SesionActual = Depends(sesion_actual)):
    usuario_id = sesion.negocio_id
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if u.password is not None and not verify_password(datos.password, u.password):
            raise HTTPException(status_code=400, detail="Contraseña incorrecta")

        archivos = [ruta for ruta in (u.logo_path, u.plantilla_pdf_path) if ruta]

        # Las cuentas de vendedores no tienen datos propios: se borran con el
        # negocio, o la cuenta del admin quedaría sin forma de eliminarse.
        hijos = [
            fila.id
            for fila in session.query(Usuario.id).filter(
                Usuario.dueno_id == usuario_id
            ).all()
        ]
        if hijos:
            session.query(ChatMensaje).filter(
                ChatMensaje.usuario_id.in_(hijos)
            ).delete(synchronize_session=False)
            session.query(Evento).filter(
                Evento.usuario_id.in_(hijos)
            ).delete(synchronize_session=False)
            session.query(Usuario).filter(Usuario.id.in_(hijos)).delete(
                synchronize_session=False
            )

        session.query(ChatMensaje).filter(ChatMensaje.usuario_id == usuario_id).delete()
        session.query(Evento).filter(Evento.usuario_id == usuario_id).delete()
        session.query(Gasto).filter(Gasto.usuario_id == usuario_id).delete()
        session.query(EnlaceFactura).filter(EnlaceFactura.usuario_id == usuario_id).delete()
        session.query(CompraItem).filter(
            CompraItem.compra_id.in_(
                session.query(Compra.id).filter(Compra.usuario_id == usuario_id)
            )
        ).delete(synchronize_session=False)
        session.query(Compra).filter(Compra.usuario_id == usuario_id).delete()
        session.query(Proveedor).filter(Proveedor.usuario_id == usuario_id).delete()
        session.query(Empleado).filter(Empleado.usuario_id == usuario_id).delete()
        session.query(VentaItem).filter(
            VentaItem.venta_id.in_(
                session.query(Venta.id).filter(Venta.usuario_id == usuario_id)
            )
        ).delete(synchronize_session=False)
        session.query(Venta).filter(Venta.usuario_id == usuario_id).delete()
        session.query(Movimiento).filter(
            Movimiento.producto_id.in_(
                session.query(Producto.id).filter(Producto.usuario_id == usuario_id)
            )
        ).delete(synchronize_session=False)
        session.query(Producto).filter(Producto.usuario_id == usuario_id).delete()
        session.query(Cliente).filter(Cliente.usuario_id == usuario_id).delete()
        session.query(Promocion).filter(Promocion.usuario_id == usuario_id).delete()
        session.delete(u)

    for ruta in archivos:
        try:
            if os.path.isfile(ruta):
                os.remove(ruta)
        except OSError:
            logger.warning("No se pudo borrar el archivo %s", ruta)

    return {"mensaje": "Cuenta y todos sus datos eliminados correctamente"}


@router.post(
    "/perfil/logo",
    dependencies=[Depends(limitar(10, 300, "subida-logo")), Depends(requiere_admin)],
)
async def subir_logo(
    archivo: UploadFile = File(...),
    sesion: SesionActual = Depends(sesion_actual),
):
    usuario_id = sesion.negocio_id
    contenido = await leer_subida_segura(archivo, {"png", "jpg"}, MAX_LOGO_BYTES, "logo")
    extension = "png" if contenido.startswith(b"\x89PNG") else "jpg"

    os.makedirs(LOGOS_DIR, exist_ok=True)
    path = os.path.join(LOGOS_DIR, nombre_archivo_seguro("logo", usuario_id, extension))
    with open(path, "wb") as buffer:
        buffer.write(contenido)

    with get_db() as session:
        session.query(Usuario).filter(Usuario.id == usuario_id).update({Usuario.logo_path: path})

    return {"mensaje": "Logo subido con éxito", "logo_path": path}


@router.post(
    "/perfil/plantilla",
    dependencies=[Depends(limitar(10, 300, "subida-plantilla")), Depends(requiere_admin)],
)
async def subir_plantilla(
    archivo: UploadFile = File(...),
    sesion: SesionActual = Depends(sesion_actual),
):
    usuario_id = sesion.negocio_id
    contenido = await leer_subida_segura(archivo, {"pdf"}, MAX_PLANTILLA_BYTES, "archivo")

    os.makedirs(PLANTILLAS_DIR, exist_ok=True)
    path = os.path.join(PLANTILLAS_DIR, nombre_archivo_seguro("plantilla", usuario_id, "pdf"))
    with open(path, "wb") as buffer:
        buffer.write(contenido)

    with get_db() as session:
        session.query(Usuario).filter(Usuario.id == usuario_id).update({
            Usuario.plantilla_pdf_path: path,
            Usuario.modo_factura: "personalizada",
        })

    return {"mensaje": "Plantilla subida con éxito", "modo_factura": "personalizada"}


@router.get("/tasa-cambio")
def obtener_tasa_cambio(sesion: SesionActual = Depends(sesion_actual)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == sesion.negocio_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {"tasa_cambio": u.tasa_cambio}


@router.put(
    "/tasa-cambio",
    dependencies=[Depends(limitar(30, 60, "tasa-cambio")), Depends(requiere_admin)],
)
def actualizar_tasa_cambio(data: TasaCambioData, sesion: SesionActual = Depends(sesion_actual)):
    if data.tasa_cambio <= 0:
        raise HTTPException(status_code=400, detail="La tasa debe ser mayor a cero")
    with get_db() as session:
        session.query(Usuario).filter(Usuario.id == sesion.negocio_id).update({
            Usuario.tasa_cambio: tasa_decimal(data.tasa_cambio)
        })
        return {
            "mensaje": "Tasa de cambio actualizada",
            "tasa_cambio": a_float(data.tasa_cambio),
        }
