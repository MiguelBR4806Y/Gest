from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, update
from sqlalchemy.orm import joinedload

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import Movimiento, Producto, Promocion, Usuario, VentaItem
from Backend.dinero import a_float, dinero
from Backend.models.schema import MovimientoCrear, ProductoCrear, RecargaInventario
from Backend.routers.auth import verificar_token

router = APIRouter(prefix="/productos", tags=["Productos"])


def _validar_promocion(session, promocion_id, usuario_id):
    """Evita que un usuario enganche a su producto una promoción de otra cuenta."""
    if promocion_id is None:
        return None
    promo = session.query(Promocion).filter(
        Promocion.id == promocion_id,
        Promocion.usuario_id == usuario_id,
    ).first()
    if not promo:
        raise HTTPException(status_code=400, detail="Promoción no encontrada")
    return promo.id


def _validar_codigo_unico(session, usuario_id, codigo, excluir_id=None):
    """El código de barras es único dentro del negocio, no entre negocios."""
    if not codigo:
        return None
    consulta = session.query(Producto.id).filter(
        Producto.usuario_id == usuario_id,
        Producto.codigo_barras == codigo,
    )
    if excluir_id is not None:
        consulta = consulta.filter(Producto.id != excluir_id)
    if consulta.first():
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un producto con el código {codigo}",
        )
    return codigo


def _serializar(p, tasa=None):
    promo = None
    if p.promocion:
        promo = {
            "id": p.promocion.id,
            "nombre": p.promocion.nombre,
            "tipo": p.promocion.tipo,
            "valor": a_float(p.promocion.valor),
        }

    precio = dinero(p.precio)
    costo = dinero(p.costo)
    margen = precio - costo
    pd = dinero(p.precio_dolar)
    if pd == 0 and precio > 0 and tasa:
        from decimal import Decimal

        pd = dinero(precio / Decimal(str(tasa)))

    return {
        "id": p.id,
        "nombre": p.nombre,
        "categoria": p.categoria,
        "codigo_barras": p.codigo_barras,
        "stock": p.stock,
        "stock_minimo": p.stock_minimo,
        "precio": a_float(precio),
        "precio_dolar": a_float(pd),
        "costo": a_float(costo),
        "margen": a_float(margen),
        "margen_pct": a_float(margen / precio * 100) if precio > 0 else 0.0,
        "promocion_id": p.promocion_id,
        "promocion": promo,
        "creado_en": str(p.creado_en),
    }


def _tasa(session, usuario_id) -> float:
    return session.query(Usuario.tasa_cambio).filter(
        Usuario.id == usuario_id
    ).scalar() or 36.0


@router.get("/")
def listar_productos(
    usuario_id: int = Depends(verificar_token),
    q: str = Query(default=None, max_length=80),
    categoria: str = Query(default=None, max_length=80),
):
    with get_db() as session:
        tasa = _tasa(session, usuario_id)
        consulta = session.query(Producto).options(
            joinedload(Producto.promocion)
        ).filter(Producto.usuario_id == usuario_id)

        if q:
            patron = f"%{q}%"
            consulta = consulta.filter(
                or_(Producto.nombre.ilike(patron), Producto.categoria.ilike(patron))
            )
        if categoria:
            consulta = consulta.filter(Producto.categoria == categoria)

        productos = consulta.order_by(Producto.nombre).all()
        return [_serializar(p, tasa) for p in productos]


@router.get("/stock-bajo")
def stock_bajo(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        tasa = _tasa(session, usuario_id)
        productos = session.query(Producto).options(
            joinedload(Producto.promocion)
        ).filter(
            Producto.usuario_id == usuario_id,
            Producto.stock <= Producto.stock_minimo,
        ).order_by(Producto.stock).all()
        return [_serializar(p, tasa) for p in productos]


@router.get("/categorias")
def listar_categorias(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        filas = session.query(Producto.categoria, func.count(Producto.id)).filter(
            Producto.usuario_id == usuario_id,
            Producto.categoria.isnot(None),
            Producto.categoria != "",
        ).group_by(Producto.categoria).order_by(Producto.categoria).all()
        return [{"nombre": nombre, "cantidad": cantidad} for nombre, cantidad in filas]


@router.post("/")
def crear_producto(producto: ProductoCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        tasa = _tasa(session, usuario_id)
        precio = dinero(producto.precio)
        if producto.precio_dolar is not None:
            pd = dinero(producto.precio_dolar)
        else:
            pd = dinero(precio / dinero(tasa)) if tasa else dinero(0)

        p = Producto(
            usuario_id=usuario_id,
            nombre=producto.nombre,
            categoria=producto.categoria,
            codigo_barras=_validar_codigo_unico(
                session, usuario_id, producto.codigo_barras
            ),
            stock=producto.stock,
            stock_minimo=producto.stock_minimo,
            precio=precio,
            precio_dolar=pd,
            costo=dinero(producto.costo),
            promocion_id=_validar_promocion(session, producto.promocion_id, usuario_id),
        )
        session.add(p)
        session.flush()
        registrar_evento(session, usuario_id, "producto_creado", "producto", p.id, p.nombre)
        return _serializar(p, tasa)


@router.get("/codigo/{codigo}")
def buscar_por_codigo(codigo: str, usuario_id: int = Depends(verificar_token)):
    """Búsqueda exacta por código de barras, para el escáner del POS."""
    if not codigo or len(codigo) > 64:
        raise HTTPException(status_code=400, detail="Código inválido")
    with get_db() as session:
        p = session.query(Producto).options(
            joinedload(Producto.promocion)
        ).filter(
            Producto.usuario_id == usuario_id,
            Producto.codigo_barras == codigo,
        ).first()
        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return _serializar(p, _tasa(session, usuario_id))


@router.get("/{id}")
def obtener_producto(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        tasa = _tasa(session, usuario_id)
        p = session.query(Producto).options(
            joinedload(Producto.promocion)
        ).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id,
        ).first()
        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return _serializar(p, tasa)


@router.put("/{id}")
def editar_producto(id: int, producto: ProductoCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        existe = session.query(Producto).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id,
        ).with_for_update().first()
        if not existe:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        tasa = _tasa(session, usuario_id)
        precio = dinero(producto.precio)
        if producto.precio_dolar is not None:
            pd = dinero(producto.precio_dolar)
        else:
            pd = dinero(precio / dinero(tasa)) if tasa else dinero(0)
        promocion_id = _validar_promocion(session, producto.promocion_id, usuario_id)
        codigo_barras = _validar_codigo_unico(
            session, usuario_id, producto.codigo_barras, excluir_id=id
        )

        session.execute(
            update(Producto)
            .where(Producto.id == id, Producto.usuario_id == usuario_id)
            .values(
                nombre=producto.nombre,
                categoria=producto.categoria,
                codigo_barras=codigo_barras,
                stock=producto.stock,
                stock_minimo=producto.stock_minimo,
                precio=precio,
                precio_dolar=pd,
                costo=dinero(producto.costo),
                promocion_id=promocion_id,
            )
        )
        registrar_evento(
            session, usuario_id, "producto_editado", "producto", id,
            f"precio={precio} stock={producto.stock}",
        )
        return {"id": id, **producto.model_dump(), "promocion_id": promocion_id}


@router.delete("/{id}")
def eliminar_producto(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        p = session.query(Producto).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id,
        ).with_for_update().first()
        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Un producto ya vendido no se borra: las facturas históricas y los
        # reportes quedarían con líneas huérfanas. Se deja el stock en cero.
        vendido = session.query(VentaItem.id).filter(
            VentaItem.producto_id == p.id
        ).first()
        if vendido:
            raise HTTPException(
                status_code=409,
                detail="El producto tiene ventas registradas y no se puede eliminar. "
                       "Deja el stock en cero si ya no lo vendes.",
            )

        session.query(Movimiento).filter(Movimiento.producto_id == p.id).delete()
        session.delete(p)
        registrar_evento(session, usuario_id, "producto_eliminado", "producto", id, p.nombre)
        return {"mensaje": "Producto eliminado"}


@router.get("/{id}/movimientos")
def listar_movimientos(
    id: int,
    usuario_id: int = Depends(verificar_token),
    limite: int = Query(default=100, ge=1, le=500),
):
    with get_db() as session:
        # Se filtra por dueño: antes cualquier usuario autenticado podía leer
        # los movimientos de un producto ajeno adivinando el id.
        movimientos = session.query(Movimiento).join(
            Producto, Movimiento.producto_id == Producto.id
        ).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id,
        ).order_by(Movimiento.fecha_hora.desc()).limit(limite).all()
        return [{
            "id": m.id,
            "tipo": m.tipo,
            "cantidad": m.cantidad,
            "fecha_hora": m.fecha_hora,
        } for m in movimientos]


def _aplicar_entrada(session, producto: Producto, cantidad: int) -> int:
    # Se calcula antes del UPDATE: SQLAlchemy sincroniza el objeto en sesión,
    # así que leer `producto.stock` después sumaría la cantidad dos veces.
    nuevo_stock = int(producto.stock or 0) + cantidad
    resultado = session.execute(
        update(Producto)
        .where(Producto.id == producto.id, Producto.usuario_id == producto.usuario_id)
        .values(stock=Producto.stock + cantidad)
    )
    if resultado.rowcount != 1:
        raise HTTPException(status_code=409, detail="No se pudo actualizar el stock")
    return nuevo_stock


@router.post("/{id}/recargar")
def recargar_inventario(id: int, recarga: RecargaInventario, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        p = session.query(Producto).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id,
        ).with_for_update().first()
        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        nuevo_stock = _aplicar_entrada(session, p, recarga.cantidad)
        session.add(Movimiento(producto_id=id, tipo="entrada", cantidad=recarga.cantidad))
        registrar_evento(
            session, usuario_id, "inventario_recargado", "producto", id,
            f"+{recarga.cantidad} (stock {nuevo_stock})",
        )
        return {"mensaje": "Inventario recargado con éxito", "stock_actual": nuevo_stock}


@router.post("/{id}/movimiento")
def registrar_movimiento(id: int, movimiento: MovimientoCrear, usuario_id: int = Depends(verificar_token)):
    tipo, cantidad = movimiento.tipo, movimiento.cantidad

    with get_db() as session:
        p = session.query(Producto).filter(
            Producto.id == id,
            Producto.usuario_id == usuario_id,
        ).with_for_update().first()
        if not p:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        if tipo == "entrada":
            nuevo_stock = _aplicar_entrada(session, p, cantidad)
        else:
            if p.stock < cantidad:
                raise HTTPException(status_code=400, detail="Stock insuficiente")
            nuevo_stock = int(p.stock) - cantidad
            # Condicional: si otra transacción consumió el stock, esta no pasa.
            resultado = session.execute(
                update(Producto)
                .where(
                    Producto.id == p.id,
                    Producto.usuario_id == usuario_id,
                    Producto.stock >= cantidad,
                )
                .values(stock=Producto.stock - cantidad)
            )
            if resultado.rowcount != 1:
                raise HTTPException(status_code=409, detail="Stock insuficiente")

        session.add(Movimiento(producto_id=id, tipo=tipo, cantidad=cantidad))
        return {"stock_actual": nuevo_stock}
