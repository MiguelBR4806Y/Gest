import os
import secrets
import string
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from Backend.db.models import Base, Usuario, Cliente

load_dotenv()

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


def inicializar_db():
    Base.metadata.create_all(bind=engine)
    with get_db() as session:
        for alter in [
            "ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_dolar FLOAT DEFAULT 0.0",
            "ALTER TABLE productos ADD COLUMN IF NOT EXISTS promocion_id INTEGER REFERENCES promociones(id)",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tasa_cambio FLOAT DEFAULT 36.0",
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tasa_cambio_configurada BOOLEAN DEFAULT FALSE",
        ]:
            try:
                session.execute(text(alter))
            except:
                pass

        session.execute(text(
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS zona_horaria VARCHAR DEFAULT 'America/Managua'"
        ))
        session.execute(text(
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email VARCHAR"
        ))
        session.execute(text(
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE"
        ))
        session.execute(text(
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS verificacion_token VARCHAR"
        ))

        root = session.query(Usuario).filter(Usuario.usuario == "root").first()
        if not root:
            root = Usuario(usuario="root", password="1234", nombre_negocio="Bravo's Gest")
            session.add(root)

        ALFANUM = string.ascii_uppercase + string.digits

        session.execute(text(
            "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS codigo VARCHAR(6) UNIQUE"
        ))

        clientes_sin_codigo = session.query(Cliente).filter(
            Cliente.codigo.is_(None)
        ).all()
        for c in clientes_sin_codigo:
            for _ in range(100):
                codigo = "".join(secrets.choice(ALFANUM) for _ in range(6))
                existe = session.query(Cliente).filter(
                    Cliente.codigo == codigo
                ).first()
                if not existe:
                    c.codigo = codigo
                    break
