from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from Backend.db.database import get_db
from pydantic import BaseModel
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "clave_secreta_por_defecto")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer()

class LoginData(BaseModel):
    usuario: str
    password: str

class RegistroData(BaseModel):
    usuario: str
    password: str
    nombre_negocio: str = "Mi Negocio"

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