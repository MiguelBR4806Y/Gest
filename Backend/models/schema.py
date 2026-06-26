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
    precio_dolar: Optional[float] = None
    promocion_id: Optional[int] = None

class Producto(ProductoCrear):
    id: int
    creado_en: datetime

    class Config:
        from_attributes = True


# ── Promociones ──
class PromocionCrear(BaseModel):
    nombre: str
    tipo: str  # 'porcentaje', '2x1', 'monto_fijo'
    valor: float = 0.0
    activa: bool = True

class Promocion(PromocionCrear):
    id: int
    usuario_id: int
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

# ── Recarga de Inventario ──
class RecargaInventario(BaseModel):
    cantidad: int


# ── Tasa de Cambio ──
class TasaCambioData(BaseModel):
    tasa_cambio: float