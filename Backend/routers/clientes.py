from fastapi import APIRouter, HTTPException
from Backend.db.database import get_db
from Backend.models.schema import ClienteCrear

router = APIRouter(prefix="/clientes", tags=["Clientes"])


# Listar todos los clientes
@router.get("/")
def listar_clientes():
    with get_db() as conn:
        clientes = conn.execute("SELECT * FROM clientes").fetchall()
        return [dict(c) for c in clientes]


# Crear cliente
@router.post("/")
def crear_cliente(cliente: ClienteCrear):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO clientes (nombre, telefono, credito_limite) VALUES (?, ?, ?)",
            (cliente.nombre, cliente.telefono, cliente.credito_limite)
        )
        return {"id": cursor.lastrowid, **cliente.model_dump()}


# Obtener un cliente
@router.get("/{id}")
def obtener_cliente(id: int):
    with get_db() as conn:
        c = conn.execute("SELECT * FROM clientes WHERE id = ?", (id,)).fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        return dict(c)


# Editar cliente
@router.put("/{id}")
def editar_cliente(id: int, cliente: ClienteCrear):
    with get_db() as conn:
        conn.execute(
            "UPDATE clientes SET nombre=?, telefono=?, credito_limite=? WHERE id=?",
            (cliente.nombre, cliente.telefono, cliente.credito_limite, id)
        )
        return {"id": id, **cliente.model_dump()}


# Eliminar cliente
@router.delete("/{id}")
def eliminar_cliente(id: int):
    with get_db() as conn:
        conn.execute("""
            DELETE FROM venta_items WHERE venta_id IN (
                SELECT id FROM ventas WHERE cliente_id = ?
            )
        """, (id,))
        conn.execute("DELETE FROM ventas WHERE cliente_id = ?", (id,))
        conn.execute("DELETE FROM clientes WHERE id = ?", (id,))
        return {"mensaje": "Cliente eliminado"}