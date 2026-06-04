from fastapi import APIRouter, HTTPException
from Backend.db.database import get_db
from Backend.models.schema import ProductoCrear

router = APIRouter(prefix="/productos", tags=["Productos"])


# Listar todos los productos
@router.get("/")
def listar_productos():
    with get_db() as conn:
        productos = conn.execute("SELECT * FROM productos").fetchall()
        return [dict(p) for p in productos]


# Crear producto
@router.post("/")
def crear_producto(producto: ProductoCrear):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO productos (nombre, categoria, stock, precio) VALUES (?, ?, ?, ?)",
            (producto.nombre, producto.categoria, producto.stock, producto.precio)
        )
        return {"id": cursor.lastrowid, **producto.model_dump()}


# Obtener un producto
@router.get("/{id}")
def obtener_producto(id: int):
    with get_db() as conn:
        p = conn.execute("SELECT * FROM productos WHERE id = ?", (id,)).fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return dict(p)


# Editar producto
@router.put("/{id}")
def editar_producto(id: int, producto: ProductoCrear):
    with get_db() as conn:
        conn.execute(
            "UPDATE productos SET nombre=?, categoria=?, stock=?, precio=? WHERE id=?",
            (producto.nombre, producto.categoria, producto.stock, producto.precio, id)
        )
        return {"id": id, **producto.model_dump()}


# Eliminar producto
@router.delete("/{id}")
def eliminar_producto(id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM productos WHERE id = ?", (id,))
        return {"mensaje": "Producto eliminado"}


# Stock bajo
@router.get("/stock-bajo")
def stock_bajo():
    with get_db() as conn:
        productos = conn.execute(
            "SELECT * FROM productos WHERE stock <= 5"
        ).fetchall()
        return [dict(p) for p in productos]


# Movimiento de inventario
@router.post("/{id}/movimiento")
def registrar_movimiento(id: int, movimiento: dict):
    tipo = movimiento.get("tipo")
    cantidad = movimiento.get("cantidad", 0)

    if tipo not in ("entrada", "salida"):
        raise HTTPException(status_code=400, detail="Tipo inválido")

    with get_db() as conn:
        p = conn.execute("SELECT stock FROM productos WHERE id = ?", (id,)).fetchone()
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