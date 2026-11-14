import csv
import io
import re
import unicodedata

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, or_, update
from sqlalchemy.orm import joinedload

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import Movimiento, Producto, Promocion, Usuario, VentaItem
from Backend.dinero import a_float, dinero
from Backend.models.schema import MovimientoCrear, ProductoCrear, RecargaInventario
from Backend.routers.auth import requiere_admin, requiere_modulo, verificar_token
from Backend.security import limitar

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


_LECTURA = [Depends(requiere_modulo("ventas", "contabilidad"))]


@router.get("/", dependencies=_LECTURA)
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


@router.get("/stock-bajo", dependencies=_LECTURA)
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


@router.get("/categorias", dependencies=_LECTURA)
def listar_categorias(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        filas = session.query(Producto.categoria, func.count(Producto.id)).filter(
            Producto.usuario_id == usuario_id,
            Producto.categoria.isnot(None),
            Producto.categoria != "",
        ).group_by(Producto.categoria).order_by(Producto.categoria).all()
        return [{"nombre": nombre, "cantidad": cantidad} for nombre, cantidad in filas]


# ── Importación de catálogo CSV ──

MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_FILAS_IMPORT = 5000
MAX_ERRORES_REPORTADOS = 100

# Marca de "ya existirá" para la simulación: no es un Producto real.
_MARCADOR_SIMULADO = object()

COLUMNAS_CSV = [
    ("nombre", {"nombre", "producto", "descripcion", "articulo"}),
    ("categoria", {"categoria", "rubro", "linea"}),
    ("codigo_barras", {"codigobarras", "codigo", "codigodebarras", "sku", "barra"}),
    ("stock", {"stock", "existencia", "cantidad", "inventario"}),
    ("stock_minimo", {"stockminimo", "minimo", "stockmin"}),
    ("precio", {"precio", "precioventa", "preciocordobas", "precioc"}),
    ("precio_dolar", {"preciodolar", "preciousd", "preciodolares"}),
    ("costo", {"costo", "costocompra", "costounitario"}),
]

PLANTILLA_CSV = """nombre;categoria;codigo_barras;stock;stock_minimo;precio;precio_dolar;costo
Café molido 500g;Abarrotes;7501001234567;25;5;95.00;2.64;70.00
Pan de molde integral;Panadería;;12;3;55.00;1.53;40.00
"""


def _normalizar_cabecera(texto: str) -> str:
    """Sin acentos, sin espacios ni signos: `Precio C$` → `precioc`."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z0-9]", "", sin_acentos.lower())


def _mapear_columnas(cabeceras: list[str]) -> dict[str, str]:
    """Devuelve {campo_interno: cabecera_real}. Falla si falta el nombre."""
    normalizadas = {_normalizar_cabecera(c): c for c in cabeceras if c}
    mapa: dict[str, str] = {}
    for campo, alias in COLUMNAS_CSV:
        for nombre in alias:
            if nombre in normalizadas:
                mapa[campo] = normalizadas[nombre]
                break
    if "nombre" not in mapa:
        raise HTTPException(
            status_code=400,
            detail="El CSV debe tener una columna 'nombre' (o 'producto')",
        )
    return mapa


def _decodificar_csv(contenido: bytes) -> str:
    if b"\x00" in contenido[:2048]:
        raise HTTPException(status_code=400, detail="El archivo no parece un CSV de texto")
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="No se pudo leer el archivo como texto")


def _detectar_delimitador(texto: str) -> str:
    encabezado = texto.splitlines()[0] if texto.strip() else ""
    return ";" if encabezado.count(";") >= encabezado.count(",") else ","


def _texto_celda(fila: dict, mapa: dict, campo: str) -> str | None:
    cabecera = mapa.get(campo)
    if not cabecera:
        return None
    valor = (fila.get(cabecera) or "").strip()
    return valor or None


def _importar_filas(session, usuario_id: int, filas, mapa, modo, simular) -> dict:
    creados = actualizados = ignorados = 0
    errores: list[dict] = []
    vista_previa: list[dict] = []
    # La sesión no hace autoflush: sin esta caché, dos filas del mismo CSV con
    # el mismo código de barras no se verían entre sí y se insertarían ambas.
    creados_por_codigo: dict[str, object] = {}
    tasa = _tasa(session, usuario_id)

    for indice, fila in enumerate(filas, start=2):
        if indice - 1 > MAX_FILAS_IMPORT:
            errores.append({
                "fila": indice,
                "motivo": f"Se superó el máximo de {MAX_FILAS_IMPORT} filas",
            })
            break

        try:
            datos = {
                "nombre": _texto_celda(fila, mapa, "nombre"),
                "categoria": _texto_celda(fila, mapa, "categoria"),
                "codigo_barras": _texto_celda(fila, mapa, "codigo_barras"),
                "stock": _texto_celda(fila, mapa, "stock") or 0,
                "stock_minimo": _texto_celda(fila, mapa, "stock_minimo") or 5,
                "precio": _texto_celda(fila, mapa, "precio") or 0,
                "precio_dolar": _texto_celda(fila, mapa, "precio_dolar"),
                "costo": _texto_celda(fila, mapa, "costo") or 0,
            }
            producto = ProductoCrear(**datos)
        except Exception as error:  # noqa: BLE001 - se reporta la fila y se sigue
            motivo = str(getattr(error, "errors", lambda: [])() or error)
            errores.append({"fila": indice, "motivo": motivo[:200]})
            continue

        existente = None
        if producto.codigo_barras:
            existente = creados_por_codigo.get(producto.codigo_barras)
            if existente is None:
                existente = session.query(Producto).filter(
                    Producto.usuario_id == usuario_id,
                    Producto.codigo_barras == producto.codigo_barras,
                ).first()

        if existente and modo == "crear":
            ignorados += 1
            continue
        if not existente and modo == "actualizar":
            ignorados += 1
            continue

        if len(vista_previa) < 20:
            vista_previa.append({
                "fila": indice,
                "nombre": producto.nombre,
                "codigo_barras": producto.codigo_barras,
                "stock": producto.stock,
                "precio": float(producto.precio),
                "accion": "actualizar" if existente else "crear",
            })

        if simular:
            if existente:
                actualizados += 1
            else:
                creados += 1
                if producto.codigo_barras:
                    # Simula el alta para que una fila repetida se marque como
                    # actualización, igual que haría la importación real.
                    creados_por_codigo[producto.codigo_barras] = _MARCADOR_SIMULADO
            continue

        try:
            if existente:
                existente.nombre = producto.nombre
                existente.categoria = producto.categoria
                existente.stock = producto.stock
                existente.stock_minimo = producto.stock_minimo
                existente.precio = dinero(producto.precio)
                existente.costo = dinero(producto.costo)
                if producto.precio_dolar is not None:
                    existente.precio_dolar = dinero(producto.precio_dolar)
                actualizados += 1
            else:
                precio = dinero(producto.precio)
                if producto.precio_dolar is not None:
                    pd = dinero(producto.precio_dolar)
                else:
                    pd = dinero(precio / dinero(tasa)) if tasa else dinero(0)
                nuevo = Producto(
                    usuario_id=usuario_id,
                    nombre=producto.nombre,
                    categoria=producto.categoria,
                    codigo_barras=producto.codigo_barras,
                    stock=producto.stock,
                    stock_minimo=producto.stock_minimo,
                    precio=precio,
                    precio_dolar=pd,
                    costo=dinero(producto.costo),
                )
                session.add(nuevo)
                if producto.codigo_barras:
                    creados_por_codigo[producto.codigo_barras] = nuevo
                creados += 1
        except Exception as error:  # noqa: BLE001
            errores.append({"fila": indice, "motivo": str(error)[:200]})

    return {
        "creados": creados,
        "actualizados": actualizados,
        "ignorados": ignorados,
        "errores": errores[:MAX_ERRORES_REPORTADOS],
        "total_errores": len(errores),
        "vista_previa": vista_previa,
        "simulado": simular,
    }


@router.get("/plantilla-csv")
def descargar_plantilla(_: int = Depends(requiere_admin)):
    return Response(
        content="\ufeff" + PLANTILLA_CSV,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="catalogo_ejemplo.csv"'},
    )


@router.post(
    "/importar",
    dependencies=[Depends(requiere_admin), Depends(limitar(5, 300, "importar-catalogo"))],
)
async def importar_catalogo(
    archivo: UploadFile = File(...),
    modo: str = Query(default="ambos", pattern="^(crear|actualizar|ambos)$"),
    simular: bool = Query(default=False),
    usuario_id: int = Depends(verificar_token),
):
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo CSV está vacío")
    if len(contenido) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="El CSV supera el límite de 5 MB")

    texto = _decodificar_csv(contenido)
    delimitador = _detectar_delimitador(texto)
    lector = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    mapa = _mapear_columnas(lector.fieldnames or [])

    with get_db() as session:
        informe = _importar_filas(session, usuario_id, lector, mapa, modo, simular)
        if not simular and (informe["creados"] or informe["actualizados"]):
            registrar_evento(
                session, usuario_id, "catalogo_importado", "producto", None,
                f"{informe['creados']} creados, {informe['actualizados']} actualizados",
            )
    return informe


@router.post("/", dependencies=[Depends(requiere_admin)])
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


@router.get("/codigo/{codigo}", dependencies=_LECTURA)
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


@router.get("/{id}", dependencies=_LECTURA)
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


@router.put("/{id}", dependencies=[Depends(requiere_admin)])
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


@router.delete("/{id}", dependencies=[Depends(requiere_admin)])
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


@router.get("/{id}/movimientos", dependencies=_LECTURA)
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


@router.post("/{id}/recargar", dependencies=[Depends(requiere_admin)])
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


@router.post("/{id}/movimiento", dependencies=[Depends(requiere_admin)])
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
