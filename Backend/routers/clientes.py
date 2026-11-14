import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, update

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import Cliente, Venta
from Backend.dinero import a_float, dinero
from Backend.models.schema import Abono, ClienteCrear
from Backend.routers.auth import verificar_token

router = APIRouter(prefix="/clientes", tags=["Clientes"])

ALFANUM = string.ascii_uppercase + string.digits


def generar_codigo(session) -> str:
    for _ in range(100):
        codigo = "".join(secrets.choice(ALFANUM) for _ in range(6))
        if not session.query(Cliente.id).filter(Cliente.codigo == codigo).first():
            return codigo
    raise HTTPException(status_code=500, detail="No se pudo generar un código único")


def serializar(c, ultima=None) -> dict:
    limite = dinero(c.credito_limite)
    usado = dinero(c.credito_usado)
    return {
        "id": c.id,
        "codigo": c.codigo,
        "nombre": c.nombre,
        "telefono": c.telefono,
        "credito_limite": a_float(limite),
        "credito_usado": a_float(usado),
        "credito_disponible": a_float(limite - usado),
        "creado_en": str(c.creado_en),
        "ultima_compra": str(ultima) if ultima else "Sin compras",
    }


def _serializar_un_cliente(session, c, usuario_id) -> dict:
    ultima = session.query(func.max(Venta.fecha_hora)).filter(
        Venta.cliente_id == c.id,
        Venta.usuario_id == usuario_id,
        Venta.estado == "completada",
    ).scalar()
    return serializar(c, ultima)


@router.get("/")
def listar_clientes(
    usuario_id: int = Depends(verificar_token),
    q: str = Query(default=None, max_length=80),
    solo_con_credito: bool = Query(default=False),
):
    with get_db() as session:
        # Antes se hacía una consulta por cliente (N+1) para la última compra;
        # ahora sale todo en una sola agregación.
        consulta = session.query(Cliente, func.max(Venta.fecha_hora)).outerjoin(
            Venta,
            and_(
                Venta.cliente_id == Cliente.id,
                Venta.usuario_id == usuario_id,
                Venta.estado == "completada",
            ),
        ).filter(Cliente.usuario_id == usuario_id)

        if q:
            patron = f"%{q}%"
            consulta = consulta.filter(
                or_(Cliente.nombre.ilike(patron), Cliente.codigo.ilike(patron))
            )
        if solo_con_credito:
            consulta = consulta.filter(Cliente.credito_usado > 0)

        filas = consulta.group_by(Cliente.id).order_by(Cliente.nombre).all()
        return [serializar(cliente, ultima) for cliente, ultima in filas]


@router.post("/")
def crear_cliente(cliente: ClienteCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        c = Cliente(
            codigo=generar_codigo(session),
            usuario_id=usuario_id,
            nombre=cliente.nombre,
            telefono=cliente.telefono,
            credito_limite=dinero(cliente.credito_limite),
        )
        session.add(c)
        session.flush()
        registrar_evento(session, usuario_id, "cliente_creado", "cliente", c.id, c.nombre)
        return serializar(c)


@router.get("/{id}")
def obtener_cliente(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        c = session.query(Cliente).filter(
            Cliente.id == id,
            Cliente.usuario_id == usuario_id,
        ).first()
        if not c:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        return _serializar_un_cliente(session, c, usuario_id)


@router.put("/{id}")
def editar_cliente(id: int, cliente: ClienteCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        existe = session.query(Cliente).filter(
            Cliente.id == id,
            Cliente.usuario_id == usuario_id,
        ).with_for_update().first()
        if not existe:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        valores = {
            "nombre": cliente.nombre,
            "telefono": cliente.telefono,
            "credito_limite": dinero(cliente.credito_limite),
        }
        if cliente.credito_usado is not None:
            valores["credito_usado"] = dinero(cliente.credito_usado)

        session.execute(
            update(Cliente)
            .where(Cliente.id == id, Cliente.usuario_id == usuario_id)
            .values(**valores)
        )
        registrar_evento(
            session, usuario_id, "cliente_editado", "cliente", id,
            f"limite={valores['credito_limite']}"
            + (f" usado={valores['credito_usado']}" if "credito_usado" in valores else ""),
        )

        c = session.query(Cliente).filter(
            Cliente.id == id,
            Cliente.usuario_id == usuario_id,
        ).first()
        return _serializar_un_cliente(session, c, usuario_id)


@router.post("/{id}/abono")
def registrar_abono(id: int, abono: Abono, usuario_id: int = Depends(verificar_token)):
    """Registra un pago parcial del crédito y deja constancia en auditoría."""
    with get_db() as session:
        c = session.query(Cliente).filter(
            Cliente.id == id,
            Cliente.usuario_id == usuario_id,
        ).with_for_update().first()
        if not c:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        actual = dinero(c.credito_usado)
        if actual <= 0:
            raise HTTPException(status_code=400, detail="El cliente no tiene saldo pendiente")

        monto = dinero(abono.monto)
        if monto > actual:
            raise HTTPException(
                status_code=400,
                detail=f"El abono supera el saldo pendiente ({actual})",
            )

        nuevo_dec = actual - monto
        nuevo = a_float(nuevo_dec)
        session.execute(
            update(Cliente)
            .where(Cliente.id == id, Cliente.usuario_id == usuario_id)
            .values(credito_usado=nuevo_dec)
        )
        registrar_evento(
            session, usuario_id, "abono_credito", "cliente", id,
            f"monto={monto} saldo={nuevo}" + (f" nota={abono.nota}" if abono.nota else ""),
        )
        return {
            "mensaje": "Abono registrado",
            "credito_usado": nuevo,
            "credito_disponible": a_float(dinero(c.credito_limite) - nuevo_dec),
        }


@router.delete("/{id}")
def eliminar_cliente(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        c = session.query(Cliente).filter(
            Cliente.id == id,
            Cliente.usuario_id == usuario_id,
        ).with_for_update().first()
        if not c:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        # Borrar clientes con historial reescribiría ventas y facturas ya
        # emitidas. Se bloquea y se sugiere dejar el nombre como histórico.
        tiene_ventas = session.query(Venta.id).filter(
            Venta.cliente_id == id,
            Venta.usuario_id == usuario_id,
        ).first()
        if tiene_ventas:
            raise HTTPException(
                status_code=409,
                detail="El cliente tiene ventas registradas y no se puede eliminar.",
            )

        session.delete(c)
        registrar_evento(session, usuario_id, "cliente_eliminado", "cliente", id, c.nombre)
        return {"mensaje": "Cliente eliminado"}


@router.get("/{id}/compras")
def historial_compras(
    id: int,
    usuario_id: int = Depends(verificar_token),
    limite: int = Query(default=100, ge=1, le=500),
):
    with get_db() as session:
        compras = session.query(
            Venta.id, Venta.total, Venta.metodo_pago, Venta.fecha_hora, Venta.estado
        ).filter(
            Venta.cliente_id == id,
            Venta.usuario_id == usuario_id,
        ).order_by(Venta.fecha_hora.desc()).limit(limite).all()

        return [{
            "id": c.id,
            "total": a_float(c.total),
            "metodo_pago": c.metodo_pago,
            "estado": c.estado,
            "fecha_hora": c.fecha_hora,
        } for c in compras]
