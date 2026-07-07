from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from Backend.db.database import get_db
from Backend.db.models import Usuario, Producto, Cliente, Venta, VentaItem, Movimiento, Promocion, ChatMensaje
from Backend.models.schema import TasaCambioData, GoogleOAuthData
from Backend.services.email_service import enviar_verificacion, generar_codigo
from pydantic import BaseModel
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import secrets
import httpx
import os
import shutil

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "clave_secreta_por_defecto")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

LOGOS_DIR = "logos"
PLANTILLAS_DIR = "plantillas"

security = HTTPBearer()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")


class LoginData(BaseModel):
    usuario: str
    password: str


class RegistroData(BaseModel):
    usuario: str
    password: str
    email: Optional[str] = None
    nombre_negocio: str = "Mi Negocio"
    tasa_cambio: float = 36.0


class PerfilData(BaseModel):
    nombre_negocio: str
    email: Optional[str] = None
    color_acento: str = "#1D9E75"
    tasa_cambio: float = 36.0
    zona_horaria: str = "America/Managua"


class CambioPasswordData(BaseModel):
    password_actual: str
    password_nuevo: str


class EliminarCuentaData(BaseModel):
    password: str


def crear_token(usuario_id: int, usuario: str) -> str:
    expira = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(usuario_id), "usuario": usuario, "exp": expira},
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = int(payload.get("sub"))
        return usuario_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")


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


@router.post("/registro")
def registro(datos: RegistroData):
    with get_db() as session:
        existente = session.query(Usuario).filter(
            Usuario.usuario == datos.usuario
        ).first()

        if existente:
            raise HTTPException(status_code=400, detail="El usuario ya existe")

        if datos.email:
            email_existente = session.query(Usuario).filter(
                Usuario.email == datos.email
            ).first()
            if email_existente:
                raise HTTPException(status_code=400, detail="El email ya está registrado")

        codigo = generar_codigo() if datos.email else None
        usuario = Usuario(
            usuario=datos.usuario,
            password=datos.password,
            email=datos.email,
            nombre_negocio=datos.nombre_negocio,
            tasa_cambio=datos.tasa_cambio,
            tasa_cambio_configurada=True,
            verificacion_token=codigo,
        )
        session.add(usuario)
        session.flush()
        if datos.email and codigo:
            enviado = enviar_verificacion(datos.email, codigo, datos.nombre_negocio)
            if not enviado:
                print(f"[DEV] Código de verificación para {datos.email}: {codigo}")
        return {"mensaje": "Usuario registrado exitosamente. Se ha enviado un código de verificación a tu correo."}


@router.post("/login")
def login(datos: LoginData):
    with get_db() as session:
        usuario = session.query(Usuario).filter(
            Usuario.usuario == datos.usuario,
            Usuario.password == datos.password
        ).first()

        if not usuario:
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

        return usuario_a_respuesta(usuario)


@router.post("/oauth/google")
def login_google(datos: GoogleOAuthData):
    try:
        resp = httpx.get("https://www.googleapis.com/oauth2/v3/tokeninfo", params={"id_token": datos.credential})
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Token de Google inválido")

        info = resp.json()
        email = info.get("email")
        google_id = info.get("sub")
        name = info.get("name", "")

        if not email or not google_id:
            raise HTTPException(status_code=400, detail="El token de Google no contiene email válido")

        if GOOGLE_CLIENT_ID and info.get("aud") != GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=401, detail="El token no pertenece a esta aplicación")

        with get_db() as session:
            usuario = session.query(Usuario).filter(
                Usuario.email == email
            ).first()

            if usuario:
                return usuario_a_respuesta(usuario)

            username = email.split("@")[0]
            base = username
            contador = 1
            while session.query(Usuario).filter(Usuario.usuario == username).first():
                username = f"{base}_{contador}"
                contador += 1

            nombre_negocio = name if name else f"Negocio de {email.split('@')[0]}"

            usuario = Usuario(
                usuario=username,
                password=None,
                email=email,
                provider="google",
                provider_id=google_id,
                nombre_negocio=nombre_negocio,
                tasa_cambio=36.0,
                tasa_cambio_configurada=True,
            )
            session.add(usuario)
            session.flush()

            return usuario_a_respuesta(usuario)

    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Error al verificar el token con Google")


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


@router.put("/perfil")
def actualizar_perfil(datos: PerfilData, usuario_id: int = Depends(verificar_token)):
    updates = {
        Usuario.nombre_negocio: datos.nombre_negocio,
        Usuario.color_acento: datos.color_acento,
        Usuario.tasa_cambio: datos.tasa_cambio,
        Usuario.tasa_cambio_configurada: True,
        Usuario.zona_horaria: datos.zona_horaria,
    }
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        email_cambio = datos.email and datos.email != u.email

        if datos.email:
            otro = session.query(Usuario).filter(
                Usuario.email == datos.email,
                Usuario.id != usuario_id
            ).first()
            if otro:
                raise HTTPException(status_code=400, detail="El correo ya está registrado por otro usuario")
            updates[Usuario.email] = datos.email
        elif datos.email is not None:
            updates[Usuario.email] = None

        if email_cambio:
            codigo = generar_codigo()
            updates[Usuario.email_verified] = False
            updates[Usuario.verificacion_token] = codigo

        session.query(Usuario).filter(Usuario.id == usuario_id).update(updates)

        if email_cambio:
            enviado = enviar_verificacion(datos.email, codigo, u.nombre_negocio)
            if not enviado:
                print(f"[DEV] Código de verificación para {datos.email}: {codigo}")
        
        return {"mensaje": "Perfil actualizado correctamente"}


@router.put("/password")
def cambiar_password(datos: CambioPasswordData, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if u.password is None:
            raise HTTPException(status_code=400, detail="No puedes cambiar la contraseña de una cuenta de Google")
        if u.password != datos.password_actual:
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
        u.password = datos.password_nuevo
        return {"mensaje": "Contraseña actualizada correctamente"}


@router.post("/enviar-verificacion")
def enviar_verificacion_endpoint(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if not u.email:
            raise HTTPException(status_code=400, detail="No tienes un correo configurado")
        if u.email_verified:
            raise HTTPException(status_code=400, detail="El correo ya está verificado")
        codigo = generar_codigo()
        u.verificacion_token = codigo
        enviado = enviar_verificacion(u.email, codigo, u.nombre_negocio)
        if not enviado:
            print(f"[DEV] Código de verificación para {u.email}: {codigo}")
            return {"mensaje": "Código de verificación generado", "codigo_dev": codigo}
        return {"mensaje": "Código de verificación enviado a tu correo"}


class VerificarCodigoData(BaseModel):
    codigo: str


@router.post("/verificar-codigo")
def verificar_codigo(datos: VerificarCodigoData, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if not u.verificacion_token:
            raise HTTPException(status_code=400, detail="No hay un código pendiente de verificación")
        if u.verificacion_token != datos.codigo:
            raise HTTPException(status_code=400, detail="Código incorrecto")
        u.email_verified = True
        u.verificacion_token = None
        return {"mensaje": "Correo verificado exitosamente"}


@router.delete("/cuenta")
def eliminar_cuenta(datos: EliminarCuentaData, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if u.password is not None and u.password != datos.password:
            raise HTTPException(status_code=400, detail="Contraseña incorrecta")

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
        return {"mensaje": "Cuenta y todos sus datos eliminados correctamente"}


@router.post("/perfil/logo")
async def subir_logo(
    archivo: UploadFile = File(...),
    usuario_id: int = Depends(verificar_token)
):
    extensiones_validas = {"image/png": ".png", "image/jpeg": ".jpg"}
    if archivo.content_type not in extensiones_validas:
        raise HTTPException(status_code=400, detail="El logo debe ser una imagen PNG o JPG")

    os.makedirs(LOGOS_DIR, exist_ok=True)
    extension = extensiones_validas[archivo.content_type]
    path = os.path.join(LOGOS_DIR, f"logo_{usuario_id}{extension}")

    with open(path, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    with get_db() as session:
        session.query(Usuario).filter(Usuario.id == usuario_id).update({
            Usuario.logo_path: path
        })

    return {"mensaje": "Logo subido con éxito", "logo_path": path}


@router.post("/perfil/plantilla")
async def subir_plantilla(
    archivo: UploadFile = File(...),
    usuario_id: int = Depends(verificar_token)
):
    if archivo.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    os.makedirs(PLANTILLAS_DIR, exist_ok=True)
    path = os.path.join(PLANTILLAS_DIR, f"plantilla_{usuario_id}.pdf")

    with open(path, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

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


@router.put("/tasa-cambio")
def actualizar_tasa_cambio(data: TasaCambioData, usuario_id: int = Depends(verificar_token)):
    if data.tasa_cambio <= 0:
        raise HTTPException(status_code=400, detail="La tasa debe ser mayor a cero")
    with get_db() as session:
        session.query(Usuario).filter(Usuario.id == usuario_id).update({
            Usuario.tasa_cambio: data.tasa_cambio
        })
        return {"mensaje": "Tasa de cambio actualizada", "tasa_cambio": data.tasa_cambio}
