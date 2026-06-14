from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from Backend.db.database import get_db
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

class PerfilData(BaseModel):
    nombre_negocio: str
    color_acento: str = "#1D9E75"

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
    with get_db() as conn:
        existente = conn.execute(
            "SELECT id FROM usuarios WHERE usuario = ?",
            (datos.usuario,)
        ).fetchone()

        if existente:
            raise HTTPException(status_code=400, detail="El usuario ya existe")

        conn.execute(
            "INSERT INTO usuarios (usuario, password, nombre_negocio) VALUES (?, ?, ?)",
            (datos.usuario, datos.password, datos.nombre_negocio)
        )
        return {"mensaje": "Usuario registrado exitosamente"}

@router.post("/login")
def login(datos: LoginData):
    with get_db() as conn:
        usuario = conn.execute(
            "SELECT * FROM usuarios WHERE usuario = ? AND password = ?",
            (datos.usuario, datos.password)
        ).fetchone()

        if not usuario:
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

        token = crear_token(usuario["id"], usuario["usuario"])
        return {
            "token": token,
            "usuario": usuario["usuario"],
            "nombre_negocio": usuario["nombre_negocio"]
        }

@router.get("/perfil")
def obtener_perfil(usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        u = conn.execute(
            "SELECT nombre_negocio, logo_path, color_acento, modo_factura FROM usuarios WHERE id = ?",
            (usuario_id,)
        ).fetchone()

        if not u:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return dict(u)

@router.put("/perfil")
def actualizar_perfil(datos: PerfilData, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        conn.execute(
            "UPDATE usuarios SET nombre_negocio = ?, color_acento = ? WHERE id = ?",
            (datos.nombre_negocio, datos.color_acento, usuario_id)
        )
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

    with get_db() as conn:
        conn.execute(
            "UPDATE usuarios SET logo_path = ? WHERE id = ?",
            (path, usuario_id)
        )

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

    with get_db() as conn:
        conn.execute(
            "UPDATE usuarios SET plantilla_pdf_path = ?, modo_factura = 'personalizada' WHERE id = ?",
            (path, usuario_id)
        )

    return {"mensaje": "Plantilla subida con éxito", "modo_factura": "personalizada"}