import sqlite3
import os
from contextlib import contextmanager

# Ruta de la base de datos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "../../nicagest.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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


def _migrar_columnas_usuarios(conn):
    columnas_actuales = [fila["name"] for fila in conn.execute("PRAGMA table_info(usuarios)")]

    columnas_nuevas = {
        "logo_path": "TEXT",
        "color_acento": "TEXT DEFAULT '#1D9E75'",
        "plantilla_pdf_path": "TEXT",
        "modo_factura": "TEXT DEFAULT 'basica'",
    }

    for nombre, tipo in columnas_nuevas.items():
        if nombre not in columnas_actuales:
            conn.execute(f"ALTER TABLE usuarios ADD COLUMN {nombre} {tipo}")


def inicializar_db():
    with get_db() as conn:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())
        _migrar_columnas_usuarios(conn)