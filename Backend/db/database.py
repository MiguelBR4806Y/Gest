import sqlite3
import os
from contextlib import contextmanager

# Ruta de la base de datos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "../../nicagest.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Devuelve filas como diccionarios
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inicializar_db():
    with get_db() as conn:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())