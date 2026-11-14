from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import Compra, Gasto, Proveedor
from Backend.models.schema import ProveedorCrear
from Backend.routers.auth import requiere_modulo, verificar_token

router = APIRouter(
    prefix="/proveedores",
    tags=["Proveedores"],
    dependencies=[Depends(requiere_modulo("contabilidad"))],
)


def _serializar(p: Proveedor) -> dict:
    return {
        "id": p.id,
        "nombre": p.nombre,
        "contacto": p.contacto,
        "email": p.email,
        "telefono": p.telefono,
        "notas": p.notas,
        "activo": bool(p.activo),
        "creado_en": p.creado_en.isoformat() if p.creado_en else None,
    }


@router.get("/")
def listar_proveedores(
    usuario_id: int = Depends(verificar_token),
    solo_activos: bool = False,
):
    with get_db() as session:
        consulta = session.query(Proveedor).filter(Proveedor.usuario_id == usuario_id)
        if solo_activos:
            consulta = consulta.filter(Proveedor.activo.is_(True))
        return [_serializar(p) for p in consulta.order_by(Proveedor.nombre).all()]


@router.post("/", status_code=201)
def crear_proveedor(datos: ProveedorCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        p = Proveedor(usuario_id=usuario_id, **datos.model_dump())
        session.add(p)
        session.flush()
        registrar_evento(
            session, usuario_id, "proveedor_creado", "proveedor", p.id, p.nombre
        )
        return _serializar(p)


@router.put("/{id}")
def editar_proveedor(
    id: int,
    datos: ProveedorCrear,
    usuario_id: int = Depends(verificar_token),
):
    with get_db() as session:
        p = session.query(Proveedor).filter(
            Proveedor.id == id,
            Proveedor.usuario_id == usuario_id,
        ).with_for_update().first()
        if not p:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")

        session.execute(
            update(Proveedor)
            .where(Proveedor.id == id, Proveedor.usuario_id == usuario_id)
            .values(**datos.model_dump())
        )
        registrar_evento(session, usuario_id, "proveedor_editado", "proveedor", id, p.nombre)
        session.refresh(p)
        return _serializar(p)


@router.delete("/{id}")
def eliminar_proveedor(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        p = session.query(Proveedor).filter(
            Proveedor.id == id,
            Proveedor.usuario_id == usuario_id,
        ).with_for_update().first()
        if not p:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")

        # Borrarlo dejaría compras y gastos sin origen contable.
        tiene_compras = session.query(Compra.id).filter(
            Compra.proveedor_id == id,
            Compra.usuario_id == usuario_id,
        ).first()
        tiene_gastos = session.query(Gasto.id).filter(
            Gasto.proveedor_id == id,
            Gasto.usuario_id == usuario_id,
        ).first()
        if tiene_compras or tiene_gastos:
            raise HTTPException(
                status_code=409,
                detail="El proveedor tiene compras o gastos registrados; "
                       "desactívalo en vez de borrarlo",
            )

        session.delete(p)
        registrar_evento(session, usuario_id, "proveedor_eliminado", "proveedor", id, p.nombre)
        return {"mensaje": "Proveedor eliminado"}
