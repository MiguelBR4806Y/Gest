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

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
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


# Migraciones idempotentes sobre esquemas ya existentes.
COLUMNAS_NUEVAS = [
    "ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_dolar FLOAT DEFAULT 0.0",
    "ALTER TABLE productos ADD COLUMN IF NOT EXISTS promocion_id INTEGER REFERENCES promociones(id)",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tasa_cambio FLOAT DEFAULT 36.0",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tasa_cambio_configurada BOOLEAN DEFAULT FALSE",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS zona_horaria VARCHAR DEFAULT 'America/Managua'",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email VARCHAR",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS verificacion_token VARCHAR",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS verificacion_expira TIMESTAMPTZ",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS verificacion_intentos INTEGER DEFAULT 0",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_cambiada_en TIMESTAMPTZ",
    "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS codigo VARCHAR(6) UNIQUE",
]

ALFANUM = string.ascii_uppercase + string.digits


def _generar_password_aleatoria(longitud: int = 16) -> str:
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(longitud))


def _migrar_columnas(session) -> None:
    for sentencia in COLUMNAS_NUEVAS:
        try:
            session.execute(text(sentencia))
        except Exception:
            # Se registra el fallo concreto en vez de tragárselo en silencio.
            logger.warning(
                "Migración omitida: %s", sentencia.split(" ADD COLUMN IF NOT EXISTS ")[-1]
            )


def _asegurar_root(session) -> None:
    root = session.query(Usuario).filter(Usuario.usuario == "root").first()

    if root is None:
        # Sin credencial por defecto hardcodeada: o viene del entorno, o se
        # genera una aleatoria y se muestra una sola vez en el log.
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
