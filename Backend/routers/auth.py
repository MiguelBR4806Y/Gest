import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator

from Backend.db.database import get_db
from Backend.db.models import (
    ChatMensaje, Cliente, Movimiento, Producto, Promocion, Venta, VentaItem, Usuario,
)
from Backend.models.schema import GoogleOAuthData, TasaCambioData
from Backend.security import (
    MAX_LOGO_BYTES, MAX_PLANTILLA_BYTES, ZONA_POR_DEFECTO,
    comparar_seguro, es_color_hex, es_zona_horaria, ip_cliente, limitar,
    leer_subida_segura, nombre_archivo_seguro, rate_limiter, sanear_texto,
    validar_password,
)
from Backend.services.email_service import (
    CODIGO_MINUTOS_VALIDO, enviar_verificacion, generar_codigo,
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

# Intentos de verificación de código antes de invalidarlo.
MAX_INTENTOS_CODIGO = 5

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


def crear_token(usuario_id: int, usuario: str) -> str:
    ahora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(usuario_id),
            "usuario": usuario,
            "iat": int(ahora.timestamp()),
            "exp": ahora + timedelta(hours=TOKEN_EXPIRE_HOURS),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def verificar_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> int:
    """Valida el JWT y comprueba en BD que la cuenta siga activa y no revocada."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido")

    emitido = payload.get("iat")
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=401, detail="Token inválido")
        # Revocación: todo token emitido antes del último cambio de contraseña deja de valer.
        if u.password_cambiada_en and emitido is not None:
            cambiada = u.password_cambiada_en
            if cambiada.tzinfo is None:
                cambiada = cambiada.replace(tzinfo=timezone.utc)
            if emitido < cambiada.timestamp() - 1:
                raise HTTPException(status_code=401, detail="Sesión expirada, inicia sesión de nuevo")
    return usuario_id


def usuario_a_respuesta(u: Usuario) -> dict:
    return {
        "token": crear_token(u.id, u.usuario),
        "usuario": u.usuario,
        "email": u.email,
        "email_verified": u.email_verified,
        "provider": u.provider,
        "nombre_negocio": u.nombre_negocio,
        "tasa_cambio": u.tasa_cambio,
        "tasa_cambio_configurada": u.tasa_cambio_configurada,
        "zona_horaria": u.zona_horaria,
    }


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
            tasa_cambio=datos.tasa_cambio,
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
        return usuario_a_respuesta(usuario)


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
            return usuario_a_respuesta(usuario)

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
        return usuario_a_respuesta(usuario)


@router.get("/perfil")
def obtener_perfil(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {
            "nombre_negocio": u.nombre_negocio,
            "email": u.email,
            "email_verified": u.email_verified,
            "provider": u.provider,
            "logo_path": u.logo_path,
            "color_acento": u.color_acento,
            "modo_factura": u.modo_factura,
            "tasa_cambio": u.tasa_cambio,
            "tasa_cambio_configurada": u.tasa_cambio_configurada,
            "zona_horaria": u.zona_horaria,
        }


@router.put("/perfil", dependencies=[Depends(limitar(30, 60, "perfil"))])
def actualizar_perfil(datos: PerfilData, usuario_id: int = Depends(verificar_token)):
    email_nuevo = datos.email or None

    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        updates = {
            Usuario.nombre_negocio: datos.nombre_negocio,
            Usuario.color_acento: datos.color_acento,
            Usuario.tasa_cambio: datos.tasa_cambio,
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
def cambiar_password(datos: CambioPasswordData, usuario_id: int = Depends(verificar_token)):
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
        return {"mensaje": "Contraseña actualizada correctamente"}


@router.post("/enviar-verificacion", dependencies=[Depends(limitar(5, 900, "verificacion-envio"))])
def enviar_verificacion_endpoint(usuario_id: int = Depends(verificar_token)):
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
def verificar_codigo(datos: VerificarCodigoData, usuario_id: int = Depends(verificar_token)):
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
                raise HTTPException(status_code=400, detail="El código ha expirado, solicita uno nuevo")

        if (u.verificacion_intentos or 0) >= MAX_INTENTOS_CODIGO:
            u.verificacion_token = None
            u.verificacion_intentos = 0
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


@router.delete("/cuenta", dependencies=[Depends(limitar(3, 3600, "eliminar-cuenta"))])
def eliminar_cuenta(datos: EliminarCuentaData, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if u.password is not None and not verify_password(datos.password, u.password):
            raise HTTPException(status_code=400, detail="Contraseña incorrecta")

        archivos = [ruta for ruta in (u.logo_path, u.plantilla_pdf_path) if ruta]

        session.query(ChatMensaje).filter(ChatMensaje.usuario_id == usuario_id).delete()
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


@router.post("/perfil/logo", dependencies=[Depends(limitar(10, 300, "subida-logo"))])
async def subir_logo(
    archivo: UploadFile = File(...),
    usuario_id: int = Depends(verificar_token),
):
    contenido = await leer_subida_segura(archivo, {"png", "jpg"}, MAX_LOGO_BYTES, "logo")
    extension = "png" if contenido.startswith(b"\x89PNG") else "jpg"

    os.makedirs(LOGOS_DIR, exist_ok=True)
    path = os.path.join(LOGOS_DIR, nombre_archivo_seguro("logo", usuario_id, extension))
    with open(path, "wb") as buffer:
        buffer.write(contenido)

    with get_db() as session:
        session.query(Usuario).filter(Usuario.id == usuario_id).update({Usuario.logo_path: path})

    return {"mensaje": "Logo subido con éxito", "logo_path": path}


@router.post("/perfil/plantilla", dependencies=[Depends(limitar(10, 300, "subida-plantilla"))])
async def subir_plantilla(
    archivo: UploadFile = File(...),
    usuario_id: int = Depends(verificar_token),
):
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
def obtener_tasa_cambio(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {"tasa_cambio": u.tasa_cambio}


@router.put("/tasa-cambio", dependencies=[Depends(limitar(30, 60, "tasa-cambio"))])
def actualizar_tasa_cambio(data: TasaCambioData, usuario_id: int = Depends(verificar_token)):
    if data.tasa_cambio <= 0:
        raise HTTPException(status_code=400, detail="La tasa debe ser mayor a cero")
    with get_db() as session:
        session.query(Usuario).filter(Usuario.id == usuario_id).update({
            Usuario.tasa_cambio: data.tasa_cambio
        })
        return {"mensaje": "Tasa de cambio actualizada", "tasa_cambio": data.tasa_cambio}
