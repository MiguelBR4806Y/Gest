from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── Productos ──
class ProductoCrear(BaseModel):
    nombre: str
    categoria: Optional[str] = None
    stock: int = 0
    stock_minimo: int = 5
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
    credito_usado: Optional[float] = None

class Cliente(ClienteCrear):
    id: int
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
    metodo_pago: str = "efectivo"
    items: list[VentaItem]

class Venta(BaseModel):
    id: int
    cliente_id: Optional[int]
    total: float
    metodo_pago: str
    fecha_hora: datetime

    class Config:
        from_attributes = True


# ── Movimientos ──
class MovimientoCrear(BaseModel):
    tipo: str
    cantidad: int