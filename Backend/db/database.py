import os
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from Backend.db.models import Base, Usuario

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
        root = session.query(Usuario).filter(Usuario.usuario == "root").first()
        if not root:
            root = Usuario(usuario="root", password="1234", nombre_negocio="Bravo's Gest")
            session.add(root)
