from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
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
    # Rol del negocio: 'admin' es dueño de los datos y 'vendedor' opera sobre
    # ellos. El vendedor apunta al admin con dueno_id y no es dueño de nada.
    rol = Column(String(16), default="admin", nullable=False, server_default="admin")
    dueno_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    nombre = Column(String(120), nullable=True)
    # Puesto del empleado con cuenta (por defecto "Vendedor"). Lo escribe el
    # admin y se muestra junto al personal sin cuenta en Empleados.
    puesto = Column(String(80), nullable=True)
    # Salario bruto mensual en córdobas. La nómina y los impuestos se calculan
    # a partir de él (Backend/nomina.py).
    salario = Column(DINERO, default=0, nullable=False, server_default="0")
    # Módulos habilitados para una cuenta subordinada, separados por comas
    # ("ventas,contabilidad"). El admin los tiene todos implícitamente.
    modulos = Column(String(64), nullable=True)
    # Comisión sobre las ventas propias (%) y antigüedad para las vacaciones.
    comision_pct = Column(Numeric(5, 2), default=0, nullable=False, server_default="0")
    fecha_ingreso = Column(Date, nullable=True)
    activo = Column(Boolean, default=True, nullable=False, server_default="true")
    # Copia reversible de la contraseña del vendedor: el admin debe poder
    # consultarla en cualquier momento. El login sigue usando el hash bcrypt.
    password_cifrada = Column(Text, nullable=True)
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
    ventas = relationship(
        "Venta",
        back_populates="usuario",
        foreign_keys="Venta.usuario_id",
    )
    ventas_cobradas = relationship(
        "Venta",
        back_populates="vendedor",
        foreign_keys="Venta.vendedor_id",
    )
    promociones = relationship("Promocion", back_populates="usuario")
    chat_mensajes = relationship("ChatMensaje", back_populates="usuario")

    __table_args__ = (
        CheckConstraint("tasa_cambio > 0", name="ck_usuarios_tasa_positiva"),
        CheckConstraint("rol IN ('admin', 'vendedor')", name="ck_usuarios_rol"),
        Index("ix_usuarios_dueno_rol", "dueno_id", "rol"),
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
    email = Column(String(254), nullable=True)
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
    # Cuenta que cobró: el admin o uno de sus vendedores. Permite cerrar caja
    # y reportes por vendedor sin duplicar la tabla de ventas.
    vendedor_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    total = Column(DINERO, nullable=False)
    metodo_pago = Column(String, default="efectivo", nullable=False)
    # Cobro en efectivo: lo que entregó el cliente y el cambio devuelto.
    # Quedan NULL en los demás métodos de pago.
    efectivo_recibido = Column(DINERO, nullable=True)
    vuelto = Column(DINERO, nullable=True)
    # Una venta anulada no se borra: se marca y se revierte el stock. Borrarla
    # reescribiría facturas ya emitidas y el histórico de reportes.
    estado = Column(String(16), default="completada", nullable=False)
    anulada_en = Column(DateTime(timezone=True), nullable=True)
    anulada_por = Column(String(64), nullable=True)
    motivo_anulacion = Column(String(300), nullable=True)
    # Clave enviada por el cliente para que un reintento no cree otra venta.
    idempotency_key = Column(String(64), nullable=True)
    fecha_hora = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="ventas", foreign_keys=[usuario_id])
    vendedor = relationship(
        "Usuario", back_populates="ventas_cobradas", foreign_keys=[vendedor_id]
    )
    cliente = relationship("Cliente", back_populates="ventas")
    items = relationship("VentaItem", back_populates="venta")

    __table_args__ = (
        CheckConstraint("estado IN ('completada', 'anulada')", name="ck_ventas_estado"),
        CheckConstraint("total >= 0", name="ck_ventas_total_no_negativo"),
        CheckConstraint(
            "vuelto IS NULL OR vuelto >= 0", name="ck_ventas_vuelto_no_negativo"
        ),
        CheckConstraint(
            "metodo_pago IN ('efectivo', 'tarjeta', 'transferencia', 'credito')",
            name="ck_ventas_metodo_pago",
        ),
        Index("ix_ventas_usuario_fecha", "usuario_id", "fecha_hora"),
        Index("ix_ventas_usuario_estado_fecha", "usuario_id", "estado", "fecha_hora"),
        Index("ix_ventas_cliente_fecha", "cliente_id", "fecha_hora"),
        Index("ix_ventas_vendedor_fecha", "vendedor_id", "fecha_hora"),
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


class Empleado(Base):
    """Personal del negocio que no necesariamente tiene cuenta de usuario.

    Los vendedores con cuenta viven en `usuarios` (rol='vendedor') y se listan
    junto a estos: aquí solo se guarda quien no inicia sesión en el sistema,
    como limpieza, seguridad o bodega.
    """

    __tablename__ = "empleados"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre = Column(String(120), nullable=False)
    puesto = Column(String(80), nullable=False)
    salario = Column(DINERO, default=0, nullable=False, server_default="0")
    comision_pct = Column(Numeric(5, 2), default=0, nullable=False, server_default="0")
    fecha_ingreso = Column(Date, nullable=True)
    telefono = Column(String(32), nullable=True)
    notas = Column(String(300), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_empleados_usuario_activo", "usuario_id", "activo"),
    )


class Bono(Base):
    """Bono planificado o pagado a alguien de la plantilla.

    `persona_tipo` distingue entre personal sin cuenta (`empleados`) y cuentas
    (`usuarios`), porque la plantilla une ambas fuentes. El bono recurrente no
    se duplica: se reconstruye en cada periodo consultado.
    """

    __tablename__ = "bonos"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    persona_tipo = Column(String(10), nullable=False)
    persona_id = Column(Integer, nullable=False)
    concepto = Column(String(120), nullable=False)
    monto = Column(DINERO, nullable=False)
    fecha = Column(Date, nullable=False)
    recurrente = Column(Boolean, default=False, nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("persona_tipo IN ('empleado', 'cuenta')", name="ck_bonos_persona_tipo"),
        CheckConstraint("monto >= 0", name="ck_bonos_monto_no_negativo"),
        Index("ix_bonos_usuario_fecha", "usuario_id", "fecha"),
        Index("ix_bonos_persona", "usuario_id", "persona_tipo", "persona_id"),
    )


class Vacacion(Base):
    """Días de vacaciones tomados o planificados (art. 76, Ley 185)."""

    __tablename__ = "vacaciones"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    persona_tipo = Column(String(10), nullable=False)
    persona_id = Column(Integer, nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)
    dias = Column(Integer, nullable=False)
    nota = Column(String(300), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("persona_tipo IN ('empleado', 'cuenta')", name="ck_vacaciones_persona_tipo"),
        CheckConstraint("dias > 0", name="ck_vacaciones_dias_positivos"),
        CheckConstraint("fecha_fin >= fecha_inicio", name="ck_vacaciones_rango"),
        Index("ix_vacaciones_persona", "usuario_id", "persona_tipo", "persona_id"),
    )


class Proveedor(Base):
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre = Column(String, nullable=False)
    contacto = Column(String, nullable=True)
    email = Column(String(254), nullable=True)
    telefono = Column(String, nullable=True)
    notas = Column(String(300), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_proveedores_usuario_nombre", "usuario_id", "nombre"),
    )


class Compra(Base):
    """Compra a proveedor: sube stock y recalcula el costo promedio."""

    __tablename__ = "compras"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=True)
    numero = Column(String(20), nullable=True)
    total = Column(DINERO, nullable=False)
    estado = Column(String(16), default="completada", nullable=False)
    nota = Column(String(300), nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now())
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("CompraItem", back_populates="compra")

    __table_args__ = (
        CheckConstraint("estado IN ('completada', 'anulada')", name="ck_compras_estado"),
        CheckConstraint("total >= 0", name="ck_compras_total_no_negativo"),
        Index("ix_compras_usuario_fecha", "usuario_id", "fecha"),
    )


class CompraItem(Base):
    __tablename__ = "compra_items"

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)
    costo_unitario = Column(DINERO, nullable=False)

    compra = relationship("Compra", back_populates="items")

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_compra_items_cantidad_positiva"),
        Index("ix_compra_items_compra", "compra_id"),
        Index("ix_compra_items_producto", "producto_id"),
    )


class Gasto(Base):
    __tablename__ = "gastos"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=True)
    # Una compra genera su gasto automáticamente; ese gasto no se borra a mano.
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=True)
    concepto = Column(String, nullable=False)
    categoria = Column(String(40), nullable=False, default="operativo")
    monto = Column(DINERO, nullable=False)
    fecha = Column(DateTime(timezone=True), server_default=func.now())
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("monto >= 0", name="ck_gastos_monto_no_negativo"),
        Index("ix_gastos_usuario_fecha", "usuario_id", "fecha"),
    )


class EnlaceFactura(Base):
    """Token de un solo uso largo para que el cliente descargue su factura.

    Se guarda el SHA-256, nunca el token: una filtración de la tabla no permite
    reconstruir el enlace.
    """

    __tablename__ = "enlaces_factura"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    expira = Column(DateTime(timezone=True), nullable=False)
    usos = Column(Integer, default=0, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_enlaces_factura_usuario_venta", "usuario_id", "venta_id"),
    )
