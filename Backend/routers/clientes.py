from fastapi import APIRouter, HTTPException, Depends
from Backend.db.database import get_db
from Backend.models.schema import ClienteCrear
from Backend.routers.auth import verificar_token

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get("/")
def listar_clientes(usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        query = """
            SELECT c.*, 
                   COALESCE((SELECT MAX(v.fecha_hora) FROM ventas v WHERE v.cliente_id = c.id), 'Sin compras') as ultima_compra
            FROM clientes c
            WHERE c.usuario_id = ?
        """
        clientes = conn.execute(query, (usuario_id,)).fetchall()
        return [dict(c) for c in clientes]


@router.post("/")
def crear_cliente(cliente: ClienteCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO clientes (usuario_id, nombre, telefono, credito_limite) VALUES (?, ?, ?, ?)",
            (usuario_id, cliente.nombre, cliente.telefono, cliente.credito_limite)
        )
        return {"id": cursor.lastrowid, **cliente.model_dump(), "ultima_compra": "Sin compras"}


@router.get("/{id}")
def obtener_cliente(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        query = """
            SELECT c.*, 
                   COALESCE((SELECT MAX(v.fecha_hora) FROM ventas v WHERE v.cliente_id = c.id), 'Sin compras') as ultima_compra
            FROM clientes c
            WHERE c.id = ? AND c.usuario_id = ?
        """
        c = conn.execute(query, (id, usuario_id)).fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        return dict(c)


@router.put("/{id}")
def editar_cliente(id: int, cliente: ClienteCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        existe = conn.execute("SELECT id FROM clientes WHERE id = ? AND usuario_id = ?", (id, usuario_id)).fetchone()
        if not existe:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        if cliente.credito_usado is not None:
            conn.execute(
                "UPDATE clientes SET nombre=?, telefono=?, credito_limite=?, credito_usado=? WHERE id=? AND usuario_id=?",
                (cliente.nombre, cliente.telefono, cliente.credito_limite, cliente.credito_usado, id, usuario_id)
            )
        else:
            conn.execute(
                "UPDATE clientes SET nombre=?, telefono=?, credito_limite=? WHERE id=? AND usuario_id=?",
                (cliente.nombre, cliente.telefono, cliente.credito_limite, id, usuario_id)
            )
            
        # Retornamos el registro real guardado con su estado de compras dinámico
        query = """
            SELECT c.*, 
                   COALESCE((SELECT MAX(v.fecha_hora) FROM ventas v WHERE v.cliente_id = c.id), 'Sin compras') as ultima_compra
            FROM clientes c
            WHERE c.id = ?
        """
        c_actualizado = conn.execute(query, (id,)).fetchone()
        return dict(c_actualizado)


@router.delete("/{id}")
def eliminar_cliente(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        conn.execute("""
            DELETE FROM venta_items WHERE venta_id IN (
                SELECT id FROM ventas WHERE cliente_id = ? AND usuario_id = ?
            )
        """, (id, usuario_id))
        conn.execute(
            "DELETE FROM ventas WHERE cliente_id = ? AND usuario_id = ?", (id, usuario_id)
        )
        conn.execute(
            "DELETE FROM clientes WHERE id = ? AND usuario_id = ?", (id, usuario_id)
        )
        return {"mensaje": "Cliente eliminado"}


@router.get("/{id}/compras")
def historial_compras(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        compras = conn.execute("""
            SELECT id, total, metodo_pago, fecha_hora
            FROM ventas
            WHERE cliente_id = ? AND usuario_id = ?
            ORDER BY fecha_hora DESC
        """, (id, usuario_id)).fetchall()
        return [dict(c) for c in compras]