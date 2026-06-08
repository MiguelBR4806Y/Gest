from fastapi import APIRouter, HTTPException
from Backend.db.database import get_db
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginData(BaseModel):
    usuario: str
    password: str

class RegistroData(BaseModel):
    usuario: str
    password: str
    nombre_negocio: str = "Mi Negocio"

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

        return {"mensaje": "Login exitoso", "usuario": usuario["usuario"]}