from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import Cliente, Movimiento, Producto, Usuario, Venta, VentaItem
from Backend.dinero import a_float, dinero, multiplicar, porcentaje, sumar
from Backend.models.schema import AnularVenta, VentaCrear
from Backend.routers.auth import verificar_token
from Backend.tiempo import ZONA_POR_DEFECTO, fecha_de, rango_dia

router = APIRouter(prefix="/ventas", tags=["Ventas"])

MAX_VENTAS_LISTADAS = 500


def _zona_usuario(session, usuario_id: int) -> str:
    zona = session.query(Usuario.zona_horaria).filter(
        Usuario.id == usuario_id
    ).scalar()
    return zona or ZONA_POR_DEFECTO


def _calcular_precio_final(p: Producto, cantidad: int, precio: Decimal) -> tuple[Decimal, str]:
    """Devuelve (subtotal, nota) aplicando la promoción vigente del producto."""
    bruto = multiplicar(precio, cantidad)
    if not p.promocion or not p.promocion.activa:
        return bruto, ""

    promo = p.promocion
    if promo.tipo == "porcentaje":
        descuento = porcentaje(bruto, promo.valor)
        return dinero(bruto - descuento), f"desc. {promo.valor}%"
    if promo.tipo == "2x1":
        gratis = cantidad // 2
        pagar = cantidad - gratis
        return multiplicar(precio, pagar), "2x1"
    if promo.tipo == "monto_fijo":
        descuento = min(dinero(promo.valor), bruto)
        return dinero(bruto - descuento), f"C${promo.valor:.2f} desc."
    return bruto, ""


def _validar_idempotency_key(clave: str | None) -> str | None:
    if clave is None:
        return None
    limpio = clave.strip()
    if not limpio:
        return None
    if len(limpio) > 64 or not all(c.isalnum() or c in "-_.:" for c in limpio):
        raise HTTPException(
            status_code=400,
            detail="La cabecera Idempotency-Key no es válida",
        )
    return limpio


def _respuesta_venta(v: Venta, repetida: bool = False) -> dict:
    return {
        "id": v.id,
        "total": a_float(v.total),
        "estado": v.estado,
        "promos_aplicadas": [],
        "repetida": repetida,
    }


def _agrupar_items(items) -> dict[int, int]:
    """Fusiona líneas repetidas del mismo producto.

    Sin esto, dos líneas del mismo producto se validaban por separado contra
    el stock y podían pasar juntas aunque la suma excediera lo disponible.
    """
    cantidades: dict[int, int] = {}
    for item in items:
        cantidades[item.producto_id] = cantidades.get(item.producto_id, 0) + item.cantidad
    return cantidades


@router.post("/")
def crear_venta(
    venta: VentaCrear,
    usuario_id: int = Depends(verificar_token),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    clave = _validar_idempotency_key(idempotency_key)

    with get_db() as session:
        # Si el cliente reintenta el cobro con la misma clave, se devuelve la
        # venta original en vez de crear otra.
        if clave:
            existente = session.query(Venta).filter(
                Venta.usuario_id == usuario_id,
                Venta.idempotency_key == clave,
            ).first()
            if existente:
                if existente.estado == "anulada":
                    raise HTTPException(
                        status_code=409,
                        detail="La venta original fue anulada; inicia un cobro nuevo",
                    )
                return _respuesta_venta(existente, repetida=True)

        cantidades = _agrupar_items(venta.items)
        ids = sorted(cantidades)

        # Ordenar por id y bloquear las filas evita interbloqueos y, sobre
        # todo, impide que dos cajas vendan la última unidad a la vez.
        productos = session.query(Producto).options(
            joinedload(Producto.promocion)
        ).filter(
            Producto.id.in_(ids),
            Producto.usuario_id == usuario_id,
        ).order_by(Producto.id).with_for_update(of=Producto).all()
        por_id = {p.id: p for p in productos}

        resueltos = []
        for producto_id in ids:
            p = por_id.get(producto_id)
            if not p:
                raise HTTPException(
                    status_code=404, detail=f"Producto {producto_id} no encontrado"
                )
            cantidad = cantidades[producto_id]
            if p.stock < cantidad:
                raise HTTPException(
                    status_code=409,
                    detail=f"Stock insuficiente para {p.nombre}: quedan {p.stock}",
                )
            precio = dinero(p.precio)
            subtotal, nota = _calcular_precio_final(p, cantidad, precio)
            resueltos.append((p, cantidad, precio, subtotal, nota))

        total = sumar(r[3] for r in resueltos)
        promos_aplicadas = [f"{r[0].nombre}: {r[4]}" for r in resueltos if r[4]]

        cliente = None
        if venta.cliente_id:
            cliente = session.query(Cliente).filter(
                Cliente.id == venta.cliente_id,
                Cliente.usuario_id == usuario_id,
            ).with_for_update().first()
            if not cliente:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")

        if venta.metodo_pago == "credito":
            if not cliente:
                raise HTTPException(
                    status_code=400, detail="Una venta a crédito requiere un cliente"
                )
            disponible = dinero(cliente.credito_limite) - dinero(cliente.credito_usado)
            if total > disponible:
                raise HTTPException(status_code=400, detail="Crédito insuficiente")

        v = Venta(
            usuario_id=usuario_id,
            cliente_id=venta.cliente_id,
            total=total,
            metodo_pago=venta.metodo_pago,
            estado="completada",
            idempotency_key=clave,
        )
        session.add(v)

        try:
            session.flush()
        except IntegrityError:
            # Carrera entre dos peticiones con la misma clave: gana la que
            # insertó primero; esta se descarta y devuelve la ganadora.
            session.rollback()
            if clave:
                existente = session.query(Venta).filter(
                    Venta.usuario_id == usuario_id,
                    Venta.idempotency_key == clave,
                ).first()
                if existente and existente.estado != "anulada":
                    return _respuesta_venta(existente, repetida=True)
            raise HTTPException(
                status_code=409,
                detail="No se pudo registrar la venta; intenta de nuevo",
            )

        venta_id = v.id

        for p, cantidad, precio, _subtotal, _nota in resueltos:
            session.add(VentaItem(
                venta_id=venta_id,
                producto_id=p.id,
                cantidad=cantidad,
                precio_unitario=precio,
                costo_unitario=dinero(p.costo),
            ))
            # Actualización condicional: si otra transacción dejó el stock por
            # debajo de la cantidad, esta fila no se toca y la venta se aborta.
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
                raise HTTPException(
                    status_code=409,
                    detail=f"Stock insuficiente para {p.nombre}, actualiza e intenta de nuevo",
                )
            session.add(Movimiento(producto_id=p.id, tipo="salida", cantidad=cantidad))

        if venta.metodo_pago == "credito":
            session.execute(
                update(Cliente)
                .where(Cliente.id == cliente.id, Cliente.usuario_id == usuario_id)
                .values(credito_usado=Cliente.credito_usado + total)
            )

        registrar_evento(
            session, usuario_id, "venta_creada", "venta", venta_id,
            f"total={total} metodo={venta.metodo_pago}",
        )

        return {
            "id": venta_id,
            "total": a_float(total),
            "estado": "completada",
            "promos_aplicadas": promos_aplicadas,
            "repetida": False,
        }


@router.delete("/{id}")
def anular_venta(
    id: int,
    datos: AnularVenta | None = None,
    usuario_id: int = Depends(verificar_token),
):
    """Anula una venta sin borrarla.

    Devuelve el stock, revierte el crédito y deja registro de quién y por qué.
    La venta sigue existiendo para que las facturas y los reportes históricos
    no cambien por debajo.
    """
    with get_db() as session:
        v = session.query(Venta).filter(
            Venta.id == id,
            Venta.usuario_id == usuario_id,
        ).with_for_update().first()
        if not v:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        if v.estado == "anulada":
            raise HTTPException(status_code=409, detail="La venta ya está anulada")

        items = session.query(VentaItem).filter(VentaItem.venta_id == v.id).all()

        for it in items:
            if it.producto_id is None:
                continue
            resultado = session.execute(
                update(Producto)
                .where(
                    Producto.id == it.producto_id,
                    Producto.usuario_id == usuario_id,
                )
                .values(stock=Producto.stock + it.cantidad)
            )
            if resultado.rowcount == 1:
                session.add(Movimiento(
                    producto_id=it.producto_id, tipo="entrada", cantidad=it.cantidad
                ))

        if v.metodo_pago == "credito" and v.cliente_id:
            session.execute(
                update(Cliente)
                .where(
                    Cliente.id == v.cliente_id,
                    Cliente.usuario_id == usuario_id,
                )
                .values(credito_usado=func.greatest(Cliente.credito_usado - v.total, 0))
            )

        nombre_usuario = session.query(Usuario.usuario).filter(
            Usuario.id == usuario_id
        ).scalar() or str(usuario_id)

        v.estado = "anulada"
        v.anulada_en = datetime.now(timezone.utc)
        v.anulada_por = nombre_usuario[:64]
        motivo = (datos.motivo if datos else "") or ""
        v.motivo_anulacion = motivo[:300] or None

        registrar_evento(
            session, usuario_id, "venta_anulada", "venta", v.id,
            f"total={v.total} motivo={motivo or 'sin motivo'}",
        )

        return {
            "mensaje": "Venta anulada; el stock y el crédito fueron restaurados",
            "id": v.id,
            "estado": v.estado,
            "motivo": v.motivo_anulacion,
            "anulada_en": v.anulada_en.isoformat(),
        }


def _parsear_fecha(fecha: str | None, zona_horaria: str):
    try:
        return fecha_de(fecha, zona_horaria)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido, use YYYY-MM-DD")


@router.get("/resumen-dia")
def resumen_dia(
    usuario_id: int = Depends(verificar_token),
    fecha: str = Query(default=None, max_length=10),
):
    with get_db() as session:
        zona_horaria = _zona_usuario(session, usuario_id)
        dia = _parsear_fecha(fecha, zona_horaria)
        inicio, fin = rango_dia(dia, zona_horaria)

        resumen = session.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (WHERE estado = 'completada') AS numero_ventas,
                    COALESCE(SUM(total) FILTER (WHERE estado = 'completada'), 0) AS total_ventas,
                    COUNT(*) FILTER (WHERE estado = 'anulada') AS numero_anuladas,
                    COALESCE(SUM(total) FILTER (WHERE estado = 'anulada'), 0) AS total_anuladas
                FROM ventas
                WHERE usuario_id = :uid AND fecha_hora >= :inicio AND fecha_hora < :fin
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().first()

        por_metodo = session.execute(
            text("""
                SELECT metodo_pago, COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total
                FROM ventas
                WHERE usuario_id = :uid AND fecha_hora >= :inicio AND fecha_hora < :fin
                  AND estado = 'completada'
                GROUP BY metodo_pago
                ORDER BY total DESC
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().fetchall()

        ganancia = session.execute(
            text("""
                SELECT COALESCE(SUM(v.total), 0) - COALESCE(SUM(
                    (SELECT SUM(vi.costo_unitario * vi.cantidad)
                     FROM venta_items vi WHERE vi.venta_id = v.id)
                ), 0) AS ganancia
                FROM ventas v
                WHERE v.usuario_id = :uid AND v.estado = 'completada'
                  AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).scalar()

        ultimas = session.execute(
            text("""
                SELECT
                    v.id, v.total, v.fecha_hora, v.metodo_pago, v.estado,
                    v.motivo_anulacion,
                    c.nombre AS cliente_nombre,
                    (
                        SELECT STRING_AGG(p.nombre || ' (x' || vi.cantidad || ')', ', ')
                        FROM venta_items vi
                        JOIN productos p ON vi.producto_id = p.id
                        WHERE vi.venta_id = v.id
                    ) AS productos
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.usuario_id = :uid AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin
                ORDER BY v.fecha_hora DESC
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().fetchall()

        numero = resumen["numero_ventas"] or 0
        total = dinero(resumen["total_ventas"])
        ganancia_total = dinero(ganancia)

        return {
            "fecha": dia.isoformat(),
            "numero_ventas": numero,
            "total_ventas": a_float(total),
            "ganancia": a_float(ganancia_total),
            "margen_pct": a_float(ganancia_total / total * 100) if total > 0 else 0.0,
            "ticket_promedio": a_float(total / numero) if numero else 0.0,
            "anuladas": {
                "numero": resumen["numero_anuladas"] or 0,
                "total": a_float(resumen["total_anuladas"]),
            },
            "por_metodo": [
                {
                    "metodo_pago": r["metodo_pago"],
                    "cantidad": r["cantidad"],
                    "total": a_float(r["total"]),
                }
                for r in por_metodo
            ],
            "ultimas_ventas": [dict(u) for u in ultimas],
        }


@router.get("/cierre")
def cierre_caja(
    usuario_id: int = Depends(verificar_token),
    fecha: str = Query(default=None, max_length=10),
):
    """Cierre de caja del día: efectivo esperado, otros medios y anulaciones."""
    with get_db() as session:
        zona_horaria = _zona_usuario(session, usuario_id)
        dia = _parsear_fecha(fecha, zona_horaria)
        inicio, fin = rango_dia(dia, zona_horaria)

        filas = session.execute(
            text("""
                SELECT metodo_pago,
                       COUNT(*) AS cantidad,
                       COALESCE(SUM(total), 0) AS total
                FROM ventas
                WHERE usuario_id = :uid AND fecha_hora >= :inicio AND fecha_hora < :fin
                  AND estado = 'completada'
                GROUP BY metodo_pago
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().fetchall()

        anuladas = session.execute(
            text("""
                SELECT COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total
                FROM ventas
                WHERE usuario_id = :uid AND fecha_hora >= :inicio AND fecha_hora < :fin
                  AND estado = 'anulada'
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().first()

        ganancia = session.execute(
            text("""
                SELECT COALESCE(SUM(v.total), 0) - COALESCE(SUM(
                    (SELECT SUM(vi.costo_unitario * vi.cantidad)
                     FROM venta_items vi WHERE vi.venta_id = v.id)
                ), 0) AS ganancia
                FROM ventas v
                WHERE v.usuario_id = :uid AND v.estado = 'completada'
                  AND v.fecha_hora >= :inicio AND v.fecha_hora < :fin
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).scalar()

        ventana = session.execute(
            text("""
                SELECT MIN(fecha_hora) AS primera, MAX(fecha_hora) AS ultima
                FROM ventas
                WHERE usuario_id = :uid AND fecha_hora >= :inicio AND fecha_hora < :fin
                  AND estado = 'completada'
            """),
            {"uid": usuario_id, "inicio": inicio, "fin": fin},
        ).mappings().first()

        por_metodo = {r["metodo_pago"]: {
            "metodo_pago": r["metodo_pago"],
            "cantidad": r["cantidad"],
            "total": a_float(r["total"]),
        } for r in filas}
        for metodo in ("efectivo", "tarjeta", "transferencia", "credito"):
            por_metodo.setdefault(metodo, {"metodo_pago": metodo, "cantidad": 0, "total": 0.0})

        total = sumar(dinero(m["total"]) for m in por_metodo.values())
        cantidad = sum(m["cantidad"] for m in por_metodo.values())
        ganancia_total = dinero(ganancia)

        return {
            "fecha": dia.isoformat(),
            "zona_horaria": zona_horaria,
            "total": a_float(total),
            "cantidad": cantidad,
            "ticket_promedio": a_float(total / cantidad) if cantidad else 0.0,
            "ganancia": a_float(ganancia_total),
            "margen_pct": a_float(ganancia_total / total * 100) if total > 0 else 0.0,
            "efectivo_esperado": por_metodo["efectivo"]["total"],
            "por_metodo": list(por_metodo.values()),
            "anuladas": {
                "cantidad": anuladas["cantidad"] or 0,
                "total": a_float(anuladas["total"]),
            },
            "primera_venta": ventana["primera"],
            "ultima_venta": ventana["ultima"],
        }


@router.get("/")
def listar_ventas(
    usuario_id: int = Depends(verificar_token),
    limite: int = Query(default=100, ge=1, le=MAX_VENTAS_LISTADAS),
    offset: int = Query(default=0, ge=0),
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
    estado: str = Query(default="todas", pattern="^(todas|completada|anulada)$"),
    busqueda: str = Query(default=None, max_length=80),
):
    with get_db() as session:
        zona_horaria = _zona_usuario(session, usuario_id)

        condiciones = ["v.usuario_id = :uid"]
        params: dict = {"uid": usuario_id, "limite": limite, "offset": offset}

        if desde:
            params["desde"] = rango_dia(
                _parsear_fecha(desde, zona_horaria), zona_horaria
            )[0]
            condiciones.append("v.fecha_hora >= :desde")
        if hasta:
            params["hasta"] = rango_dia(
                _parsear_fecha(hasta, zona_horaria), zona_horaria
            )[1]
            condiciones.append("v.fecha_hora < :hasta")
        if estado != "todas":
            condiciones.append("v.estado = :estado")
            params["estado"] = estado
        if busqueda:
            condiciones.append("""(
                c.nombre ILIKE :q OR EXISTS (
                    SELECT 1 FROM venta_items vi
                    JOIN productos p ON vi.producto_id = p.id
                    WHERE vi.venta_id = v.id AND p.nombre ILIKE :q
                )
            )""")
            params["q"] = f"%{busqueda}%"

        where = " AND ".join(condiciones)

        total = session.execute(
            text(f"""
                SELECT COUNT(*) FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE {where}
            """),
            params,
        ).scalar()

        filas = session.execute(
            text(f"""
                SELECT v.id, v.total, v.fecha_hora, v.metodo_pago, v.estado,
                       c.nombre AS cliente_nombre,
                       (
                           SELECT STRING_AGG(p.nombre || ' (x' || vi.cantidad || ')', ', ')
                           FROM venta_items vi
                           JOIN productos p ON vi.producto_id = p.id
                           WHERE vi.venta_id = v.id
                       ) AS productos
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE {where}
                ORDER BY v.fecha_hora DESC
                LIMIT :limite OFFSET :offset
            """),
            params,
        ).mappings().fetchall()

        return {
            "items": [dict(f) for f in filas],
            "total": total,
            "limite": limite,
            "offset": offset,
        }


@router.get("/{id}")
def obtener_venta(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        v = session.execute(
            text("""
                SELECT v.id, v.total, v.fecha_hora, v.metodo_pago, v.estado,
                       v.motivo_anulacion, v.anulada_en, v.anulada_por,
                       c.nombre AS cliente_nombre
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.id = :vid AND v.usuario_id = :uid
            """),
            {"vid": id, "uid": usuario_id},
        ).mappings().first()

        if not v:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        items = session.execute(
            text("""
                SELECT p.nombre, vi.cantidad, vi.precio_unitario,
                       (vi.cantidad * vi.precio_unitario) AS subtotal
                FROM venta_items vi
                JOIN productos p ON vi.producto_id = p.id
                JOIN ventas v ON vi.venta_id = v.id
                WHERE vi.venta_id = :vid AND v.usuario_id = :uid
            """),
            {"vid": id, "uid": usuario_id},
        ).mappings().fetchall()

        return {**dict(v), "items": [dict(i) for i in items]}
