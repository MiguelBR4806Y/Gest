import os

# La URL de pruebas se fija antes de importar cualquier módulo del backend:
# el engine se construye al importar Backend.db.database.
os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgresql://postgres:1234@localhost:5432/nicagest_test"),
)
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-con-mas-de-32-caracteres-1234567890")
os.environ.setdefault("ROOT_PASSWORD", "RootPass123")
os.environ.setdefault("NICAGEST_IA_MODO", "ollama")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import main  # noqa: E402
from Backend.db.database import Base, SessionLocal, engine  # noqa: E402
from Backend.db.models import Usuario  # noqa: E402
from Backend.routers.auth import crear_token, hash_password  # noqa: E402
from Backend.security import rate_limiter  # noqa: E402

TABLAS = (
    "enlaces_factura", "gastos", "compra_items", "compras", "proveedores",
    "empleados", "eventos", "chat_mensajes", "movimientos", "venta_items",
    "ventas", "productos", "promociones", "clientes", "usuarios",
)


@pytest.fixture(scope="session", autouse=True)
def esquema():
    if engine.dialect.name != "postgresql":
        pytest.skip("Las pruebas requieren PostgreSQL")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def limpiar():
    # El limitador vive en memoria y se comparte entre pruebas.
    rate_limiter.reiniciar()
    with engine.begin() as conexion:
        conexion.execute(text(f"TRUNCATE TABLE {', '.join(TABLAS)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def cliente_api():
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def crear_usuario():
    def _crear(usuario="ana", password="Segura123", zona="America/Managua",
               tasa="36.0000", email=None, rol="admin", dueno_id=None,
               activo=True, nombre=None):
        with SessionLocal() as session:
            u = Usuario(
                usuario=usuario,
                password=hash_password(password),
                email=email,
                email_verified=bool(email),
                nombre=nombre,
                rol=rol,
                dueno_id=dueno_id,
                activo=activo,
                nombre_negocio=f"Negocio {usuario}",
                zona_horaria=zona,
                tasa_cambio=tasa,
                tasa_cambio_configurada=True,
            )
            session.add(u)
            session.commit()
            session.refresh(u)
            return {
                "id": u.id,
                "usuario": u.usuario,
                "password": password,
                "email": email,
                "token": crear_token(u.id, u.usuario),
            }

    return _crear


@pytest.fixture
def auth(crear_usuario):
    """Usuario con sesión y cabeceras listas."""
    from types import SimpleNamespace

    datos = crear_usuario()
    return SimpleNamespace(
        token=datos["token"],
        usuario_id=datos["id"],
        headers={"Authorization": f"Bearer {datos['token']}"},
        otro=lambda nombre="beto": crear_usuario(nombre),
    )


@pytest.fixture
def auth_admin(crear_usuario):
    """Admin con sesión y cabeceras listas (rol explícito)."""
    from types import SimpleNamespace

    datos = crear_usuario(usuario="jefe", rol="admin")
    return SimpleNamespace(
        token=datos["token"],
        usuario_id=datos["id"],
        headers={"Authorization": f"Bearer {datos['token']}"},
    )


@pytest.fixture
def crear_vendedor(crear_usuario):
    """Crea un vendedor hijo de un admin y devuelve credenciales de ambos."""

    def _crear(admin_usuario="jefe", vendedor="vendedor1"):
        admin = crear_usuario(usuario=admin_usuario, rol="admin")
        hijo = crear_usuario(usuario=vendedor, rol="vendedor", dueno_id=admin["id"])
        return admin, hijo

    return _crear
