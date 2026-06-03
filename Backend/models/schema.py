from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── Productos ──
class ProductoCrear(BaseModel):
    nombre: str
    categoria: Optional[str] = None
    stock: int = 0
    precio: float = 0.0

class Producto(ProductoCrear):
    id: int
    creado_en: datetime

    class Config:
        from_attributes = True


# ── Clientes ──
class ClienteCrear(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    credito_limite: float = 0.0

class Cliente(ClienteCrear):
    id: int
    credito_usado: float
    creado_en: datetime

    class Config:
        from_attributes = True


# ── Ventas ──
class VentaItem(BaseModel):
    producto_id: int
    cantidad: int
    precio_unitario: float

class VentaCrear(BaseModel):
    cliente_id: Optional[int] = None
    items: list[VentaItem]

class Venta(BaseModel):
    id: int
    cliente_id: Optional[int]
    total: float
    fecha_hora: datetime

    class Config:
        from_attributes = True


# ── Movimientos ──
class MovimientoCrear(BaseModel):
    tipo: str  # "entrada" o "salida"
    cantidad: int