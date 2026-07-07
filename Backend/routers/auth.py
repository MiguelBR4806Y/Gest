from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from Backend.db.database import get_db
from Backend.db.models import Usuario
from Backend.models.schema import TasaCambioData
from pydantic import BaseModel
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
import shutil

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "clave_secreta_por_defecto")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

LOGOS_DIR = "logos"
PLANTILLAS_DIR = "plantillas"

security = HTTPBearer()


class LoginData(BaseModel):
    usuario: str
    password: str


class RegistroData(BaseModel):
    usuario: str
    password: str
    nombre_negocio: str = "Mi Negocio"
    tasa_cambio: float = 36.0


class PerfilData(BaseModel):
    nombre_negocio: str
    color_acento: str = "#1D9E75"
    tasa_cambio: float = 36.0
    zona_horaria: str = "America/Managua"


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


@router.post("/registro")
def registro(datos: RegistroData):
    with get_db() as session:
        existente = session.query(Usuario).filter(
            Usuario.usuario == datos.usuario
        ).first()

        if existente:
            raise HTTPException(status_code=400, detail="El usuario ya existe")

        usuario = Usuario(
            usuario=datos.usuario,
            password=datos.password,
            nombre_negocio=datos.nombre_negocio,
            tasa_cambio=datos.tasa_cambio,
            tasa_cambio_configurada=True,
        )
        session.add(usuario)
        session.flush()
        return {"mensaje": "Usuario registrado exitosamente"}


@router.post("/login")
def login(datos: LoginData):
    with get_db() as session:
        usuario = session.query(Usuario).filter(
            Usuario.usuario == datos.usuario,
            Usuario.password == datos.password
        ).first()

        if not usuario:
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

        token = crear_token(usuario.id, usuario.usuario)
        return {
            "token": token,
            "usuario": usuario.usuario,
            "nombre_negocio": usuario.nombre_negocio,
            "tasa_cambio": usuario.tasa_cambio,
            "tasa_cambio_configurada": usuario.tasa_cambio_configurada,
            "zona_horaria": usuario.zona_horaria,
        }


@router.get("/perfil")
def obtener_perfil(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {
            "nombre_negocio": u.nombre_negocio,
            "logo_path": u.logo_path,
            "color_acento": u.color_acento,
            "modo_factura": u.modo_factura,
            "tasa_cambio": u.tasa_cambio,
            "tasa_cambio_configurada": u.tasa_cambio_configurada,
            "zona_horaria": u.zona_horaria,
        }


@router.put("/perfil")
def actualizar_perfil(datos: PerfilData, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        session.query(Usuario).filter(Usuario.id == usuario_id).update({
            Usuario.nombre_negocio: datos.nombre_negocio,
            Usuario.color_acento: datos.color_acento,
            Usuario.tasa_cambio: datos.tasa_cambio,
            Usuario.tasa_cambio_configurada: True,
            Usuario.zona_horaria: datos.zona_horaria,
        })
        return {"mensaje": "Perfil actualizado correctamente"}


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
