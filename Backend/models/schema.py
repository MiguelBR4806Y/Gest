from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Backend.security import sanear_texto, validar_password

# Límites compartidos para evitar valores absurdos que revienten cálculos o PDFs.
MAX_TEXTO = 120
MAX_PRECIO = 10_000_000
MAX_CANTIDAD = 1_000_000

# Importe con dos decimales. Pydantic convierte el JSON a Decimal antes de
# tocar la base, así que no hay ningún float en el camino del dinero.
Importe = Annotated[Decimal, Field(ge=0, le=MAX_PRECIO)]


def _texto_obligatorio(v: str, maximo: int = MAX_TEXTO) -> str:
    limpio = sanear_texto(v, maximo)
    if not limpio:
        raise ValueError("El nombre es obligatorio")
    return limpio


# ── Productos ──
class ProductoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=MAX_TEXTO)
    categoria: Optional[str] = Field(default=None, max_length=80)
    codigo_barras: Optional[str] = Field(default=None, max_length=64)
    stock: int = Field(default=0, ge=0, le=MAX_CANTIDAD)
    stock_minimo: int = Field(default=5, ge=0, le=MAX_CANTIDAD)
    precio: Importe = Decimal("0.00")
    precio_dolar: Optional[Importe] = None
    costo: Importe = Decimal("0.00")
    promocion_id: Optional[int] = Field(default=None, gt=0)

    @field_validator("nombre")
    @classmethod
    def _sanear_nombre(cls, v: str) -> str:
        return _texto_obligatorio(v)

    @field_validator("categoria")
    @classmethod
    def _sanear_categoria(cls, v: Optional[str]) -> Optional[str]:
        return sanear_texto(v, 80) or None

    @field_validator("codigo_barras")
    @classmethod
    def _sanear_codigo(cls, v: Optional[str]) -> Optional[str]:
        limpio = sanear_texto(v, 64).replace(" ", "")
        if not limpio:
            return None
        if not all(c.isalnum() or c in "-_." for c in limpio):
            raise ValueError("El código de barras solo admite letras, números y - _ .")
        return limpio


class Producto(ProductoCrear):
    id: int
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Promociones ──
TipoPromocion = Literal["porcentaje", "2x1", "monto_fijo"]


class PromocionCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=MAX_TEXTO)
    tipo: TipoPromocion
    valor: Importe = Decimal("0.00")
    activa: bool = True

    @field_validator("nombre")
    @classmethod
    def _sanear_nombre(cls, v: str) -> str:
        return _texto_obligatorio(v)

    @field_validator("valor")
    @classmethod
    def _rango_por_tipo(cls, v: Decimal, info) -> Decimal:
        tipo = info.data.get("tipo")
        if tipo == "porcentaje" and v > 100:
            raise ValueError("El porcentaje de descuento no puede superar 100")
        return v


class Promocion(PromocionCrear):
    id: int
    usuario_id: int
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Clientes ──
class ClienteCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=MAX_TEXTO)
    telefono: Optional[str] = Field(default=None, max_length=32)
    credito_limite: Importe = Decimal("0.00")
    # Solo un administrador debería poder fijar el crédito usado; se mantiene
    # por compatibilidad con el formulario actual.
    credito_usado: Optional[Importe] = None

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

    model_config = ConfigDict(from_attributes=True)


class Abono(BaseModel):
    """Pago parcial de crédito. El monto debe ser mayor que cero."""

    monto: Annotated[Decimal, Field(gt=0, le=MAX_PRECIO)]
    nota: Optional[str] = Field(default=None, max_length=200)

    @field_validator("nota")
    @classmethod
    def _sanear_nota(cls, v: Optional[str]) -> Optional[str]:
        return sanear_texto(v, 200) or None


# ── Ventas ──
MetodoPago = Literal["efectivo", "tarjeta", "transferencia", "credito"]


class VentaItem(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(ge=1, le=MAX_CANTIDAD)
    # El precio lo fija siempre el servidor a partir del producto en BD;
    # este campo se acepta por compatibilidad pero no se usa para facturar.
    precio_unitario: Optional[Importe] = None


class VentaCrear(BaseModel):
    cliente_id: Optional[int] = Field(default=None, gt=0)
    metodo_pago: MetodoPago = "efectivo"
    items: list[VentaItem] = Field(min_length=1, max_length=200)


class AnularVenta(BaseModel):
    motivo: str = Field(default="", max_length=300)

    @field_validator("motivo")
    @classmethod
    def _sanear_motivo(cls, v: str) -> str:
        return sanear_texto(v, 300)


class Venta(BaseModel):
    id: int
    cliente_id: Optional[int]
    total: Decimal
    metodo_pago: str
    estado: str
    fecha_hora: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Movimientos ──
class MovimientoCrear(BaseModel):
    tipo: Literal["entrada", "salida"]
    cantidad: int = Field(ge=1, le=MAX_CANTIDAD)


# ── Recarga de Inventario ──
class RecargaInventario(BaseModel):
    cantidad: int = Field(ge=1, le=MAX_CANTIDAD)


# ── Tasa de Cambio ──
class TasaCambioData(BaseModel):
    tasa_cambio: Decimal = Field(gt=0, le=1_000_000)


# ── Auth / OAuth ──
class GoogleOAuthData(BaseModel):
    credential: str = Field(min_length=20, max_length=8192)


class RecuperarPassword(BaseModel):
    """Identificador = usuario o correo. La respuesta es siempre la misma."""

    identificador: str = Field(min_length=1, max_length=254)

    @field_validator("identificador")
    @classmethod
    def _sanear(cls, v: str) -> str:
        limpio = sanear_texto(v, 254)
        if not limpio:
            raise ValueError("Indica tu usuario o correo")
        return limpio


class ResetPassword(BaseModel):
    token: str = Field(min_length=20, max_length=128)
    password_nuevo: str = Field(min_length=1, max_length=128)

    @field_validator("token")
    @classmethod
    def _token_valido(cls, v: str) -> str:
        limpio = (v or "").strip()
        if not all(c.isalnum() or c in "-_" for c in limpio):
            raise ValueError("El token no es válido")
        return limpio

    @field_validator("password_nuevo")
    @classmethod
    def _politica(cls, v: str) -> str:
        problema = validar_password(v)
        if problema:
            raise ValueError(problema)
        return v
