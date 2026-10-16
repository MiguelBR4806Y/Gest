from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from Backend.security import sanear_texto

# Límites compartidos para evitar valores absurdos que revienten cálculos o PDFs.
MAX_TEXTO = 120
MAX_PRECIO = 10_000_000
MAX_CANTIDAD = 1_000_000


def _texto_obligatorio(v: str, maximo: int = MAX_TEXTO) -> str:
    limpio = sanear_texto(v, maximo)
    if not limpio:
        raise ValueError("El nombre es obligatorio")
    return limpio


# ── Productos ──
class ProductoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=MAX_TEXTO)
    categoria: Optional[str] = Field(default=None, max_length=80)
    stock: int = Field(default=0, ge=0, le=MAX_CANTIDAD)
    stock_minimo: int = Field(default=5, ge=0, le=MAX_CANTIDAD)
    precio: float = Field(default=0.0, ge=0, le=MAX_PRECIO)
    precio_dolar: Optional[float] = Field(default=None, ge=0, le=MAX_PRECIO)
    promocion_id: Optional[int] = Field(default=None, gt=0)

    @field_validator("nombre")
    @classmethod
    def _sanear_nombre(cls, v: str) -> str:
        return _texto_obligatorio(v)

    @field_validator("categoria")
    @classmethod
    def _sanear_categoria(cls, v: Optional[str]) -> Optional[str]:
        return sanear_texto(v, 80) or None


class Producto(ProductoCrear):
    id: int
    creado_en: datetime

    class Config:
        from_attributes = True


# ── Promociones ──
TipoPromocion = Literal["porcentaje", "2x1", "monto_fijo"]


class PromocionCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=MAX_TEXTO)
    tipo: TipoPromocion
    valor: float = Field(default=0.0, ge=0, le=MAX_PRECIO)
    activa: bool = True

    @field_validator("nombre")
    @classmethod
    def _sanear_nombre(cls, v: str) -> str:
        return _texto_obligatorio(v)

    @field_validator("valor")
    @classmethod
    def _rango_por_tipo(cls, v: float, info) -> float:
        tipo = info.data.get("tipo")
        if tipo == "porcentaje" and v > 100:
            raise ValueError("El porcentaje de descuento no puede superar 100")
        return v


class Promocion(PromocionCrear):
    id: int
    usuario_id: int
    creado_en: datetime

    class Config:
        from_attributes = True


# ── Clientes ──
class ClienteCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=MAX_TEXTO)
    telefono: Optional[str] = Field(default=None, max_length=32)
    credito_limite: float = Field(default=0.0, ge=0, le=MAX_PRECIO)
    credito_usado: Optional[float] = Field(default=None, ge=0, le=MAX_PRECIO)

    @field_validator("nombre")
    @classmethod
    def _sanear_nombre(cls, v: str) -> str:
        return _texto_obligatorio(v)

    @field_validator("telefono")
    @classmethod
    def _sanear_telefono(cls, v: Optional[str]) -> Optional[str]:
        limpio = sanear_texto(v, 32)
        if not limpio:
            return None
        if not all(c.isdigit() or c in "+()- ./" for c in limpio):
            raise ValueError("El teléfono contiene caracteres no válidos")
        return limpio


class Cliente(ClienteCrear):
    id: int
    codigo: str
    creado_en: datetime

    class Config:
        from_attributes = True


# ── Ventas ──
MetodoPago = Literal["efectivo", "tarjeta", "transferencia", "credito"]


class VentaItem(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(ge=1, le=MAX_CANTIDAD)
    # El precio lo fija siempre el servidor a partir del producto en BD;
    # este campo se acepta por compatibilidad pero no se usa para facturar.
    precio_unitario: Optional[float] = Field(default=None, ge=0, le=MAX_PRECIO)


class VentaCrear(BaseModel):
    cliente_id: Optional[int] = Field(default=None, gt=0)
    metodo_pago: MetodoPago = "efectivo"
    items: list[VentaItem] = Field(min_length=1, max_length=200)


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
    tipo: Literal["entrada", "salida"]
    cantidad: int = Field(ge=1, le=MAX_CANTIDAD)


# ── Recarga de Inventario ──
class RecargaInventario(BaseModel):
    cantidad: int = Field(ge=1, le=MAX_CANTIDAD)


# ── Tasa de Cambio ──
class TasaCambioData(BaseModel):
    tasa_cambio: float = Field(gt=0, le=1_000_000)


# ── Auth / OAuth ──
class GoogleOAuthData(BaseModel):
    credential: str = Field(min_length=20, max_length=8192)
