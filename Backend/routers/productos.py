from fastapi import APIRouter, HTTPException, Depends
from Backend.db.database import get_db
from Backend.models.schema import ProductoCrear
from Backend.routers.auth import verificar_token

router = APIRouter(prefix="/productos", tags=["Productos"])


@router.get("/")
def listar_productos(usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        productos = conn.execute(
            "SELECT * FROM productos WHERE usuario_id = ?", (usuario_id,)
        ).fetchall()
        return [dict(p) for p in productos]


@router.post("/")
def crear_producto(producto: ProductoCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO productos (usuario_id, nombre, categoria, stock, precio) VALUES (?, ?, ?, ?, ?)",
            (usuario_id, producto.nombre, producto.categoria, producto.stock, producto.precio)
        )
        return {"id": cursor.lastrowid, **producto.model_dump()}


@router.get("/stock-bajo")
def stock_bajo(usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        productos = conn.execute(
            "SELECT * FROM productos WHERE usuario_id = ? AND stock <= 5", (usuario_id,)
        ).fetchall()
        return [dict(p) for p in productos]


@router.get("/{id}")
def obtener_producto(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        p = conn.execute(
            "SELECT * FROM productos WHERE id = ? AND usuario_id = ?", (id, usuario_id)
        ).fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return dict(p)


@router.put("/{id}")
def editar_producto(id: int, producto: ProductoCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        conn.execute(
            "UPDATE productos SET nombre=?, categoria=?, stock=?, precio=? WHERE id=? AND usuario_id=?",
            (producto.nombre, producto.categoria, producto.stock, producto.precio, id, usuario_id)
        )
        return {"id": id, **producto.model_dump()}


@router.delete("/{id}")
def eliminar_producto(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        conn.execute("DELETE FROM venta_items WHERE producto_id = ?", (id,))
        conn.execute("DELETE FROM movimientos WHERE producto_id = ?", (id,))
        conn.execute("DELETE FROM productos WHERE id = ? AND usuario_id = ?", (id, usuario_id))
        return {"mensaje": "Producto eliminado"}


@router.get("/{id}/movimientos")
def listar_movimientos(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as conn:
        movimientos = conn.execute("""
            SELECT tipo, cantidad, fecha_hora
            FROM movimientos
            WHERE producto_id = ?
            ORDER BY fecha_hora DESC
        """, (id,)).fetchall()
        return [dict(m) for m in movimientos]


@router.post("/{id}/movimiento")
def registrar_movimiento(id: int, movimiento: dict, usuario_id: int = Depends(verificar_token)):
    tipo = movimiento.get("tipo")
    cantidad = movimiento.get("cantidad", 0)

    if tipo not in ("entrada", "salida"):
        raise HTTPException(status_code=400, detail="Tipo inválido")

    with get_db() as conn:
        p = conn.execute(
            "SELECT stock FROM productos WHERE id = ? AND usuario_id = ?", (id, usuario_id)
        ).fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        nuevo_stock = p["stock"] + cantidad if tipo == "entrada" else p["stock"] - cantidad

        if nuevo_stock < 0:
            raise HTTPException(status_code=400, detail="Stock insuficiente")

        conn.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, id))
        conn.execute(
            "INSERT INTO movimientos (producto_id, tipo, cantidad) VALUES (?, ?, ?)",
            (id, tipo, cantidad)
        )
        return {"stock_actual": nuevo_stock}