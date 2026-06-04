from fastapi import APIRouter, HTTPException
from Backend.db.database import get_db
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginData(BaseModel):
    usuario: str
    password: str

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