import logging
import os
import secrets
import string
from contextlib import contextmanager

import bcrypt
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from Backend.db.models import Base, Cliente, Usuario

load_dotenv()

logger = logging.getLogger("app")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/nicagest"
)

# pool_pre_ping evita usar conexiones muertas; recycle corta conexiones que
# llevan demasiado tiempo abiertas (cortafuegos y proxies las cierran solos).
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _es_postgres() -> bool:
    return engine.dialect.name == "postgresql"


# Columnas agregadas después del esquema inicial. En una base nueva las crea
# Base.metadata.create_all; esto solo actualiza instalaciones existentes.
COLUMNAS_NUEVAS = [
    "ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_dolar NUMERIC(12,2) DEFAULT 0",
    "ALTER TABLE productos ADD COLUMN IF NOT EXISTS promocion_id INTEGER REFERENCES promociones(id)",
    "ALTER TABLE productos ADD COLUMN IF NOT EXISTS codigo_barras VARCHAR(64)",
    "ALTER TABLE productos ADD COLUMN IF NOT EXISTS costo NUMERIC(12,2) DEFAULT 0",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tasa_cambio NUMERIC(12,4) DEFAULT 36.0",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tasa_cambio_configurada BOOLEAN DEFAULT FALSE",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS zona_horaria VARCHAR DEFAULT 'America/Managua'",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email VARCHAR",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS verificacion_token VARCHAR",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS verificacion_expira TIMESTAMPTZ",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS verificacion_intentos INTEGER DEFAULT 0",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_cambiada_en TIMESTAMPTZ",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 0",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS reset_token_hash VARCHAR(64)",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS reset_expira TIMESTAMPTZ",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS reset_solicitado_en TIMESTAMPTZ",
    "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS codigo VARCHAR(6) UNIQUE",
    "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS estado VARCHAR(16) DEFAULT 'completada'",
    "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS anulada_en TIMESTAMPTZ",
    "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS anulada_por VARCHAR(64)",
    "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS motivo_anulacion VARCHAR(300)",
    "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64)",
    "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS efectivo_recibido NUMERIC(12,2)",
    "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS vuelto NUMERIC(12,2)",
    "ALTER TABLE venta_items ADD COLUMN IF NOT EXISTS costo_unitario NUMERIC(12,2) DEFAULT 0",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol VARCHAR(16) DEFAULT 'admin'",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS dueno_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nombre VARCHAR(120)",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_cifrada TEXT",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS puesto VARCHAR(80)",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS salario NUMERIC(12,2) DEFAULT 0",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS modulos VARCHAR(64)",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS comision_pct NUMERIC(5,2) DEFAULT 0",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_ingreso DATE",
    "ALTER TABLE empleados ADD COLUMN IF NOT EXISTS salario NUMERIC(12,2) DEFAULT 0",
    "ALTER TABLE empleados ADD COLUMN IF NOT EXISTS comision_pct NUMERIC(5,2) DEFAULT 0",
    "ALTER TABLE empleados ADD COLUMN IF NOT EXISTS fecha_ingreso DATE",
    "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS vendedor_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL",
    "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS email VARCHAR(254)",
]

# Float -> NUMERIC. Se redondea al convertir para que los valores viejos no
# arrastren basura binaria (0.1 + 0.2 = 0.30000000000000004). Se comprueba
# columna por columna para no reescribir tablas ya migradas.
CONVERTIR_A_NUMERIC = [
    ("productos", "precio", "NUMERIC(12,2)"),
    ("productos", "precio_dolar", "NUMERIC(12,2)"),
    ("productos", "costo", "NUMERIC(12,2)"),
    ("promociones", "valor", "NUMERIC(12,2)"),
    ("clientes", "credito_limite", "NUMERIC(12,2)"),
    ("clientes", "credito_usado", "NUMERIC(12,2)"),
    ("ventas", "total", "NUMERIC(12,2)"),
    ("venta_items", "precio_unitario", "NUMERIC(12,2)"),
    ("venta_items", "costo_unitario", "NUMERIC(12,2)"),
    ("usuarios", "tasa_cambio", "NUMERIC(12,4)"),
]

NORMALIZAR_ESTADO = [
    "UPDATE ventas SET estado = 'completada' WHERE estado IS NULL",
    "ALTER TABLE ventas ALTER COLUMN estado SET DEFAULT 'completada'",
    "ALTER TABLE ventas ALTER COLUMN estado SET NOT NULL",
]

# Columnas de costo agregadas después: se rellenan y se fijan como NOT NULL.
NORMALIZAR_COSTO = [
    "UPDATE productos SET costo = 0 WHERE costo IS NULL",
    "ALTER TABLE productos ALTER COLUMN costo SET DEFAULT 0",
    "ALTER TABLE productos ALTER COLUMN costo SET NOT NULL",
    "UPDATE venta_items SET costo_unitario = 0 WHERE costo_unitario IS NULL",
    "ALTER TABLE venta_items ALTER COLUMN costo_unitario SET DEFAULT 0",
    "ALTER TABLE venta_items ALTER COLUMN costo_unitario SET NOT NULL",
]

# Las cuentas anteriores a los roles son administradores y están activas: sin
# este backfill, el filtro `activo IS FALSE` dejaría pasar NULL, pero el rol
# quedaría vacío en respuestas antiguas y en comparaciones `rol == 'admin'`.
NORMALIZAR_ROLES = [
    "UPDATE usuarios SET rol = 'admin' WHERE rol IS NULL",
    "ALTER TABLE usuarios ALTER COLUMN rol SET DEFAULT 'admin'",
    "ALTER TABLE usuarios ALTER COLUMN rol SET NOT NULL",
    "UPDATE usuarios SET activo = TRUE WHERE activo IS NULL",
    "ALTER TABLE usuarios ALTER COLUMN activo SET DEFAULT TRUE",
    "ALTER TABLE usuarios ALTER COLUMN activo SET NOT NULL",
    # Las cuentas hijas anteriores a los módulos conservan su acceso a ventas.
    "UPDATE usuarios SET modulos = 'ventas' "
    "WHERE rol = 'vendedor' AND (modulos IS NULL OR modulos = '')",
    # Comisión: las filas antiguas la dejan en cero explícito.
    "UPDATE usuarios SET comision_pct = 0 WHERE comision_pct IS NULL",
    "UPDATE empleados SET comision_pct = 0 WHERE comision_pct IS NULL",
]

# Restricciones que Postgres no permite crear con IF NOT EXISTS; se captura
# el error de duplicado.
RESTRICCIONES = [
    ("productos", "ck_productos_stock_no_negativo", "CHECK (stock >= 0)"),
    ("productos", "ck_productos_precio_no_negativo", "CHECK (precio >= 0)"),
    ("clientes", "ck_clientes_credito_no_negativo", "CHECK (credito_usado >= 0)"),
    ("ventas", "ck_ventas_estado", "CHECK (estado IN ('completada','anulada'))"),
    ("ventas", "ck_ventas_total_no_negativo", "CHECK (total >= 0)"),
    ("ventas", "ck_ventas_vuelto_no_negativo", "CHECK (vuelto IS NULL OR vuelto >= 0)"),
    ("ventas", "ck_ventas_metodo_pago",
     "CHECK (metodo_pago IN ('efectivo','tarjeta','transferencia','credito'))"),
    ("venta_items", "ck_venta_items_cantidad_positiva", "CHECK (cantidad > 0)"),
    ("movimientos", "ck_movimientos_cantidad_positiva", "CHECK (cantidad > 0)"),
    ("usuarios", "ck_usuarios_rol", "CHECK (rol IN ('admin','vendedor'))"),
    ("compras", "ck_compras_estado", "CHECK (estado IN ('completada','anulada'))"),
    ("compras", "ck_compras_total_no_negativo", "CHECK (total >= 0)"),
    ("compra_items", "ck_compra_items_cantidad_positiva", "CHECK (cantidad > 0)"),
    ("gastos", "ck_gastos_monto_no_negativo", "CHECK (monto >= 0)"),
    ("bonos", "ck_bonos_persona_tipo", "CHECK (persona_tipo IN ('empleado','cuenta'))"),
    ("bonos", "ck_bonos_monto_no_negativo", "CHECK (monto >= 0)"),
    ("vacaciones", "ck_vacaciones_persona_tipo", "CHECK (persona_tipo IN ('empleado','cuenta'))"),
    ("vacaciones", "ck_vacaciones_dias_positivos", "CHECK (dias > 0)"),
    ("vacaciones", "ck_vacaciones_rango", "CHECK (fecha_fin >= fecha_inicio)"),
]

INDICES = [
    "CREATE INDEX IF NOT EXISTS ix_productos_usuario_nombre ON productos (usuario_id, nombre)",
    "CREATE INDEX IF NOT EXISTS ix_productos_usuario_stock ON productos (usuario_id, stock)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_productos_usuario_codigo ON productos (usuario_id, codigo_barras)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_reset_hash ON usuarios (reset_token_hash)",
    "CREATE INDEX IF NOT EXISTS ix_clientes_usuario_nombre ON clientes (usuario_id, nombre)",
    "CREATE INDEX IF NOT EXISTS ix_promociones_usuario_activa ON promociones (usuario_id, activa)",
    "CREATE INDEX IF NOT EXISTS ix_ventas_usuario_fecha ON ventas (usuario_id, fecha_hora DESC)",
    "CREATE INDEX IF NOT EXISTS ix_ventas_usuario_estado_fecha ON ventas (usuario_id, estado, fecha_hora DESC)",
    "CREATE INDEX IF NOT EXISTS ix_ventas_cliente_fecha ON ventas (cliente_id, fecha_hora DESC)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_ventas_idempotencia ON ventas (usuario_id, idempotency_key) WHERE idempotency_key IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_venta_items_venta ON venta_items (venta_id)",
    "CREATE INDEX IF NOT EXISTS ix_venta_items_producto ON venta_items (producto_id)",
    "CREATE INDEX IF NOT EXISTS ix_movimientos_producto_fecha ON movimientos (producto_id, fecha_hora DESC)",
    "CREATE INDEX IF NOT EXISTS ix_chat_mensajes_usuario_fecha ON chat_mensajes (usuario_id, creado_en)",
    "CREATE INDEX IF NOT EXISTS ix_eventos_usuario_fecha ON eventos (usuario_id, fecha_hora DESC)",
    "CREATE INDEX IF NOT EXISTS ix_eventos_entidad ON eventos (entidad, entidad_id)",
    "CREATE INDEX IF NOT EXISTS ix_usuarios_dueno_rol ON usuarios (dueno_id, rol)",
    "CREATE INDEX IF NOT EXISTS ix_ventas_vendedor_fecha ON ventas (vendedor_id, fecha_hora DESC)",
    "CREATE INDEX IF NOT EXISTS ix_proveedores_usuario_nombre ON proveedores (usuario_id, nombre)",
    "CREATE INDEX IF NOT EXISTS ix_compras_usuario_fecha ON compras (usuario_id, fecha DESC)",
    "CREATE INDEX IF NOT EXISTS ix_compra_items_compra ON compra_items (compra_id)",
    "CREATE INDEX IF NOT EXISTS ix_compra_items_producto ON compra_items (producto_id)",
    "CREATE INDEX IF NOT EXISTS ix_gastos_usuario_fecha ON gastos (usuario_id, fecha DESC)",
    "CREATE INDEX IF NOT EXISTS ix_enlaces_factura_usuario_venta ON enlaces_factura (usuario_id, venta_id)",
    "CREATE INDEX IF NOT EXISTS ix_empleados_usuario_activo ON empleados (usuario_id, activo)",
    "CREATE INDEX IF NOT EXISTS ix_bonos_usuario_fecha ON bonos (usuario_id, fecha)",
    "CREATE INDEX IF NOT EXISTS ix_bonos_persona ON bonos (usuario_id, persona_tipo, persona_id)",
    "CREATE INDEX IF NOT EXISTS ix_vacaciones_persona ON vacaciones (usuario_id, persona_tipo, persona_id)",
]

ALFANUM = string.ascii_uppercase + string.digits


def _generar_password_aleatoria(longitud: int = 16) -> str:
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(longitud))


def _ejecutar_seguro(session, sentencia: str, etiqueta: str) -> None:
    try:
        session.execute(text(sentencia))
    except Exception as error:  # noqa: BLE001 - se registra y se continúa
        logger.warning("Migración omitida (%s): %s", etiqueta, error)


def _tipo_columna(session, tabla: str, columna: str) -> str | None:
    return session.execute(
        text("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = :tabla AND column_name = :columna
        """),
        {"tabla": tabla, "columna": columna},
    ).scalar()


def _existe_restriccion(session, nombre: str) -> bool:
    return bool(session.execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :nombre"),
        {"nombre": nombre},
    ).scalar())


def _migrar_columnas(session) -> None:
    for sentencia in COLUMNAS_NUEVAS:
        _ejecutar_seguro(session, sentencia, "columna")

    if not _es_postgres():
        # create_all ya generó el esquema definitivo en bases nuevas (SQLite,
        # tests): aquí no hay nada que convertir.
        return

    for tabla, columna, tipo in CONVERTIR_A_NUMERIC:
        actual = _tipo_columna(session, tabla, columna)
        if actual is not None and actual != "numeric":
            _ejecutar_seguro(
                session,
                f"ALTER TABLE {tabla} ALTER COLUMN {columna} TYPE {tipo} "
                f"USING ROUND({columna}::numeric, 2)",
                f"tipo.{tabla}.{columna}",
            )

    for sentencia in NORMALIZAR_ESTADO:
        _ejecutar_seguro(session, sentencia, "estado")

    for sentencia in NORMALIZAR_COSTO:
        _ejecutar_seguro(session, sentencia, "costo")

    for sentencia in NORMALIZAR_ROLES:
        _ejecutar_seguro(session, sentencia, "roles")

    for tabla, nombre, definicion in RESTRICCIONES:
        if not _existe_restriccion(session, nombre):
            _ejecutar_seguro(
                session,
                f"ALTER TABLE {tabla} ADD CONSTRAINT {nombre} {definicion}",
                f"constraint.{nombre}",
            )

    for sentencia in INDICES:
        _ejecutar_seguro(session, sentencia, "indice")


def _asegurar_root(session) -> None:
    root = session.query(Usuario).filter(Usuario.usuario == "root").first()

    if root is None:
        password = os.getenv("ROOT_PASSWORD") or _generar_password_aleatoria()
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()
        session.add(Usuario(usuario="root", password=hashed, nombre_negocio="Bravo's Gest"))
        if not os.getenv("ROOT_PASSWORD"):
            logger.warning(
                "Usuario 'root' creado con la contraseña aleatoria: %s  "
                "(cámbiala al entrar; o define ROOT_PASSWORD antes del primer arranque)",
                password,
            )
        return

    if root.password and bcrypt.checkpw(b"1234", root.password.encode("utf-8")):
        logger.warning(
            "El usuario 'root' sigue usando la contraseña por defecto '1234'. Cámbiala ahora."
        )


def _rellenar_codigos_cliente(session) -> None:
    sin_codigo = session.query(Cliente).filter(Cliente.codigo.is_(None)).all()
    for c in sin_codigo:
        for _ in range(100):
            codigo = "".join(secrets.choice(ALFANUM) for _ in range(6))
            if not session.query(Cliente).filter(Cliente.codigo == codigo).first():
                c.codigo = codigo
                break


def inicializar_db():
    Base.metadata.create_all(bind=engine)
    with get_db() as session:
        _migrar_columnas(session)
        _asegurar_root(session)
        _rellenar_codigos_cliente(session)
