from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import joinedload
from Backend.db.database import get_db
from Backend.db.models import Producto, Movimiento, Promocion, Usuario
from Backend.models.schema import ProductoCrear, RecargaInventario
from Backend.routers.auth import verificar_token

router = APIRouter(prefix="/productos", tags=["Productos"])


def _serializar(p, tasa=None):
    promo = None
    if p.promocion:
        promo = {
            "id": p.promocion.id,
            "nombre": p.promocion.nombre,
            "tipo": p.promocion.tipo,
            "valor": p.promocion.valor,
        }
    pd = p.precio_dolar
    if (pd is None or pd == 0) and p.precio > 0 and tasa:
        pd = round(p.precio / tasa, 2)
    return {
        "id": p.id,
        "nombre": p.nombre,
        "categoria": p.categoria,
        "stock": p.stock,
        "stock_minimo": p.stock_minimo,
        "precio": p.precio,
        "precio_dolar": pd,
        "promocion_id": p.promocion_id,
        "promocion": promo,
        "creado_en": str(p.creado_en),
    }


@router.get("/")
def listar_productos(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        tasa = u.tasa_cambio if u else 36.0
        productos = session.query(Producto).options(
            joinedload(Producto.promocion)
        ).filter(Producto.usuario_id == usuario_id).all()
        return [_serializar(p, tasa) for p in productos]


@router.post("/")
def crear_producto(producto: ProductoCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        tasa = u.tasa_cambio if u else 36.0
        pd = producto.precio_dolar if producto.precio_dolar is not None else round(producto.precio / tasa, 2) if tasa else 0
        p = Producto(
            usuario_id=usuario_id,
            nombre=producto.nombre,
            categoria=producto.categoria,
            stock=producto.stock,
            stock_minimo=producto.stock_minimo,
            precio=producto.precio,
            precio_dolar=pd,
            promocion_id=producto.promocion_id,
        )
        session.add(p)
        session.flush()
        return _serializar(p)


@router.get("/stock-bajo")
def stock_bajo(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        tasa = u.tasa_cambio if u else 36.0
        productos = session.query(Producto).options(
            joinedload(Producto.promocion)
        ).filter(
            Producto.usuario_id == usuario_id,
            Producto.stock <= Producto.stock_minimo
        ).all()
        return [_serializar(p, tasa) for p in productos]


@router.get("/{id}")
def obtener_producto(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        tasa = u.tasa_cambio if u else 36.0
        p = session.query(Producto).options(
            joinedload(Producto.promocion)
        ).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id
        ).first()
        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return _serializar(p, tasa)


@router.put("/{id}")
def editar_producto(id: int, producto: ProductoCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        u = session.query(Usuario).filter(Usuario.id == usuario_id).first()
        tasa = u.tasa_cambio if u else 36.0
        pd = producto.precio_dolar if producto.precio_dolar is not None else round(producto.precio / tasa, 2) if tasa else 0
        session.query(Producto).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id
        ).update({
            Producto.nombre: producto.nombre,
            Producto.categoria: producto.categoria,
            Producto.stock: producto.stock,
            Producto.stock_minimo: producto.stock_minimo,
            Producto.precio: producto.precio,
            Producto.precio_dolar: pd,
            Producto.promocion_id: producto.promocion_id,
        })
        return {"id": id, **producto.model_dump()}


@router.delete("/{id}")
def eliminar_producto(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        session.query(Movimiento).filter(Movimiento.producto_id == id).delete()
        session.query(Producto).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id
        ).delete()
        return {"mensaje": "Producto eliminado"}


@router.get("/{id}/movimientos")
def listar_movimientos(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        movimientos = session.query(Movimiento).filter(
            Movimiento.producto_id == id
        ).order_by(Movimiento.fecha_hora.desc()).all()
        return [{
            "tipo": m.tipo,
            "cantidad": m.cantidad,
            "fecha_hora": str(m.fecha_hora),
        } for m in movimientos]


@router.post("/{id}/recargar")
def recargar_inventario(id: int, recarga: RecargaInventario, usuario_id: int = Depends(verificar_token)):
    if recarga.cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad a recargar debe ser mayor a cero")

    with get_db() as session:
        p = session.query(Producto).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id
        ).first()

        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        nuevo_stock = p.stock + recarga.cantidad
        p.stock = nuevo_stock

        m = Movimiento(producto_id=id, tipo="entrada", cantidad=recarga.cantidad)
        session.add(m)
        session.flush()

        return {"mensaje": "Inventario recargado con éxito", "stock_actual": nuevo_stock}


@router.post("/{id}/movimiento")
def registrar_movimiento(id: int, movimiento: dict, usuario_id: int = Depends(verificar_token)):
    tipo = movimiento.get("tipo")
    cantidad = movimiento.get("cantidad", 0)

    if tipo not in ("entrada", "salida"):
        raise HTTPException(status_code=400, detail="Tipo inválido")

    with get_db() as session:
        p = session.query(Producto).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id
        ).first()

        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        nuevo_stock = p.stock + cantidad if tipo == "entrada" else p.stock - cantidad

        if nuevo_stock < 0:
            raise HTTPException(status_code=400, detail="Stock insuficiente")

        p.stock = nuevo_stock
        m = Movimiento(producto_id=id, tipo=tipo, cantidad=cantidad)
        session.add(m)
        session.flush()

        return {"stock_actual": nuevo_stock}
