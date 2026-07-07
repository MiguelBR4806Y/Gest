from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, CheckConstraint, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    usuario = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    nombre_negocio = Column(String, default="Mi Negocio")
    logo_path = Column(Text, nullable=True)
    color_acento = Column(String, default="#1D9E75")
    plantilla_pdf_path = Column(Text, nullable=True)
    modo_factura = Column(String, default="basica")
    tasa_cambio = Column(Float, default=36.0)
    tasa_cambio_configurada = Column(Boolean, default=False)
    zona_horaria = Column(String, default="America/Managua")
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    productos = relationship("Producto", back_populates="usuario")
    clientes = relationship("Cliente", back_populates="usuario")
    ventas = relationship("Venta", back_populates="usuario")
    promociones = relationship("Promocion", back_populates="usuario")
    chat_mensajes = relationship("ChatMensaje", back_populates="usuario")


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre = Column(String, nullable=False)
    categoria = Column(String, nullable=True)
    stock = Column(Integer, default=0)
    stock_minimo = Column(Integer, default=5)
    precio = Column(Float, default=0.0)
    precio_dolar = Column(Float, default=0.0)
    promocion_id = Column(Integer, ForeignKey("promociones.id"), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="productos")
    movimientos = relationship("Movimiento", back_populates="producto")
    promocion = relationship("Promocion", back_populates="productos")


class Promocion(Base):
    __tablename__ = "promociones"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    valor = Column(Float, default=0.0)
    activa = Column(Boolean, default=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="promociones")
    productos = relationship("Producto", back_populates="promocion")


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    codigo = Column(String(6), unique=True, nullable=False)
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=True)
    credito_limite = Column(Float, default=0.0)
    credito_usado = Column(Float, default=0.0)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="clientes")
    ventas = relationship("Venta", back_populates="cliente")


class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    total = Column(Float, nullable=False)
    metodo_pago = Column(String, default="efectivo")
    fecha_hora = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="ventas")
    cliente = relationship("Cliente", back_populates="ventas")
    items = relationship("VentaItem", back_populates="venta")


class VentaItem(Base):
    __tablename__ = "venta_items"

    id = Column(Integer, primary_key=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Float, nullable=False)

    venta = relationship("Venta", back_populates="items")


class ChatMensaje(Base):
    __tablename__ = "chat_mensajes"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    role = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="chat_mensajes")


class Movimiento(Base):
    __tablename__ = "movimientos"

    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    tipo = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    fecha_hora = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("tipo IN ('entrada', 'salida')", name="check_tipo"),
    )

    producto = relationship("Producto", back_populates="movimientos")
