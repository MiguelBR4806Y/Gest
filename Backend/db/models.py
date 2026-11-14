from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func

# Todos los importes usan NUMERIC(12, 2): nunca float. Un céntimo perdido en
# una suma rompe el cuadre de caja y la confianza en el sistema.
DINERO = Numeric(12, 2)


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    usuario = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=True)
    email = Column(String, nullable=True, unique=True)
    provider = Column(String, nullable=True)
    provider_id = Column(String, nullable=True)
    nombre_negocio = Column(String, default="Mi Negocio")
    logo_path = Column(Text, nullable=True)
    color_acento = Column(String, default="#1D9E75")
    plantilla_pdf_path = Column(Text, nullable=True)
    modo_factura = Column(String, default="basica")
    tasa_cambio = Column(Numeric(12, 4), default=36.0)
    tasa_cambio_configurada = Column(Boolean, default=False)
    zona_horaria = Column(String, default="America/Managua")
    email_verified = Column(Boolean, default=False)
    verificacion_token = Column(String, nullable=True)
    verificacion_expira = Column(DateTime(timezone=True), nullable=True)
    verificacion_intentos = Column(Integer, default=0)
    password_cambiada_en = Column(DateTime(timezone=True), nullable=True)
    # Se incrementa al cambiar la contraseña: invalida todos los JWT previos
    # sin depender de comparar marcas de tiempo con precisión de segundos.
    token_version = Column(Integer, default=0, nullable=False, server_default="0")
    # Recuperación de contraseña: se guarda solo el SHA-256 del token, nunca
    # el valor en claro, y caduca a los 30 minutos.
    reset_token_hash = Column(String(64), nullable=True, unique=True)
    reset_expira = Column(DateTime(timezone=True), nullable=True)
    reset_solicitado_en = Column(DateTime(timezone=True), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    productos = relationship("Producto", back_populates="usuario")
    clientes = relationship("Cliente", back_populates="usuario")
    ventas = relationship("Venta", back_populates="usuario")
    promociones = relationship("Promocion", back_populates="usuario")
    chat_mensajes = relationship("ChatMensaje", back_populates="usuario")

    __table_args__ = (
        CheckConstraint("tasa_cambio > 0", name="ck_usuarios_tasa_positiva"),
    )


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre = Column(String, nullable=False)
    categoria = Column(String, nullable=True)
    # Código de barras / SKU para el escáner del punto de venta. Único por
    # negocio, no global: dos negocios pueden usar el mismo EAN.
    codigo_barras = Column(String(64), nullable=True)
    stock = Column(Integer, default=0, nullable=False)
    stock_minimo = Column(Integer, default=5, nullable=False)
    precio = Column(DINERO, default=0, nullable=False)
    precio_dolar = Column(DINERO, default=0, nullable=False)
    # Costo de adquisición: sin esto no se puede calcular el margen real.
    costo = Column(DINERO, default=0, nullable=False)
    promocion_id = Column(Integer, ForeignKey("promociones.id"), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="productos")
    movimientos = relationship("Movimiento", back_populates="producto")
    promocion = relationship("Promocion", back_populates="productos")

    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_productos_stock_no_negativo"),
        CheckConstraint("precio >= 0", name="ck_productos_precio_no_negativo"),
        Index("ix_productos_usuario_nombre", "usuario_id", "nombre"),
        Index("ix_productos_usuario_stock", "usuario_id", "stock"),
        Index("ix_productos_usuario_codigo", "usuario_id", "codigo_barras", unique=True),
    )


class Promocion(Base):
    __tablename__ = "promociones"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    valor = Column(DINERO, default=0, nullable=False)
    activa = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="promociones")
    productos = relationship("Producto", back_populates="promocion")

    __table_args__ = (
        CheckConstraint("tipo IN ('porcentaje', '2x1', 'monto_fijo')", name="ck_promociones_tipo"),
        Index("ix_promociones_usuario_activa", "usuario_id", "activa"),
    )


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    codigo = Column(String(6), unique=True, nullable=False)
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=True)
    credito_limite = Column(DINERO, default=0, nullable=False)
    credito_usado = Column(DINERO, default=0, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="clientes")
    ventas = relationship("Venta", back_populates="cliente")

    __table_args__ = (
        CheckConstraint("credito_usado >= 0", name="ck_clientes_credito_no_negativo"),
        Index("ix_clientes_usuario_nombre", "usuario_id", "nombre"),
    )


class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    total = Column(DINERO, nullable=False)
    metodo_pago = Column(String, default="efectivo", nullable=False)
    # Una venta anulada no se borra: se marca y se revierte el stock. Borrarla
    # reescribiría facturas ya emitidas y el histórico de reportes.
    estado = Column(String(16), default="completada", nullable=False)
    anulada_en = Column(DateTime(timezone=True), nullable=True)
    anulada_por = Column(String(64), nullable=True)
    motivo_anulacion = Column(String(300), nullable=True)
    # Clave enviada por el cliente para que un reintento no cree otra venta.
    idempotency_key = Column(String(64), nullable=True)
    fecha_hora = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="ventas")
    cliente = relationship("Cliente", back_populates="ventas")
    items = relationship("VentaItem", back_populates="venta")

    __table_args__ = (
        CheckConstraint("estado IN ('completada', 'anulada')", name="ck_ventas_estado"),
        CheckConstraint("total >= 0", name="ck_ventas_total_no_negativo"),
        CheckConstraint(
            "metodo_pago IN ('efectivo', 'tarjeta', 'transferencia', 'credito')",
            name="ck_ventas_metodo_pago",
        ),
        Index("ix_ventas_usuario_fecha", "usuario_id", "fecha_hora"),
        Index("ix_ventas_usuario_estado_fecha", "usuario_id", "estado", "fecha_hora"),
        Index("ix_ventas_cliente_fecha", "cliente_id", "fecha_hora"),
        Index(
            "ix_ventas_idempotencia",
            "usuario_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )


class VentaItem(Base):
    __tablename__ = "venta_items"

    id = Column(Integer, primary_key=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(DINERO, nullable=False)
    # Costo del producto en el momento de la venta. Se congela para que un
    # cambio posterior de costo no reescriba el margen histórico.
    costo_unitario = Column(DINERO, default=0, nullable=False)

    venta = relationship("Venta", back_populates="items")

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_venta_items_cantidad_positiva"),
        Index("ix_venta_items_venta", "venta_id"),
        Index("ix_venta_items_producto", "producto_id"),
    )


class ChatMensaje(Base):
    __tablename__ = "chat_mensajes"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    role = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="chat_mensajes")

    __table_args__ = (
        Index("ix_chat_mensajes_usuario_fecha", "usuario_id", "creado_en"),
    )


class Movimiento(Base):
    __tablename__ = "movimientos"

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    tipo = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    fecha_hora = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("tipo IN ('entrada', 'salida')", name="check_tipo"),
        CheckConstraint("cantidad > 0", name="ck_movimientos_cantidad_positiva"),
        Index("ix_movimientos_producto_fecha", "producto_id", "fecha_hora"),
    )

    producto = relationship("Producto", back_populates="movimientos")


class Evento(Base):
    """Bitácora de auditoría: quién hizo qué y cuándo.

    Se escribe en la misma transacción que la operación que describe, así que
    si la venta se revierte, el evento tampoco queda.
    """

    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    tipo = Column(String(40), nullable=False)
    entidad = Column(String(40), nullable=False)
    entidad_id = Column(Integer, nullable=True)
    detalle = Column(String(500), nullable=True)
    fecha_hora = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_eventos_usuario_fecha", "usuario_id", "fecha_hora"),
        Index("ix_eventos_entidad", "entidad", "entidad_id"),
    )
