from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import func
from Backend.db.database import get_db
from Backend.db.models import Cliente, Venta
from Backend.models.schema import ClienteCrear
from Backend.routers.auth import verificar_token

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get("/")
def listar_clientes(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        clientes = session.query(Cliente).filter(
            Cliente.usuario_id == usuario_id
        ).all()

        result = []
        for c in clientes:
            ultima = session.query(func.max(Venta.fecha_hora)).filter(
                Venta.cliente_id == c.id
            ).scalar()
            result.append({
                "id": c.id,
                "nombre": c.nombre,
                "telefono": c.telefono,
                "credito_limite": c.credito_limite,
                "credito_usado": c.credito_usado,
                "creado_en": str(c.creado_en),
                "ultima_compra": str(ultima) if ultima else "Sin compras",
            })
        return result


@router.post("/")
def crear_cliente(cliente: ClienteCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        c = Cliente(
            usuario_id=usuario_id,
            nombre=cliente.nombre,
            telefono=cliente.telefono,
            credito_limite=cliente.credito_limite,
        )
        session.add(c)
        session.flush()
        return {"id": c.id, **cliente.model_dump(), "ultima_compra": "Sin compras"}


@router.get("/{id}")
def obtener_cliente(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        c = session.query(Cliente).filter(
            Cliente.id == id,
            Cliente.usuario_id == usuario_id
        ).first()
        if not c:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        ultima = session.query(func.max(Venta.fecha_hora)).filter(
            Venta.cliente_id == c.id
        ).scalar()

        return {
            "id": c.id,
            "nombre": c.nombre,
            "telefono": c.telefono,
            "credito_limite": c.credito_limite,
            "credito_usado": c.credito_usado,
            "creado_en": str(c.creado_en),
            "ultima_compra": str(ultima) if ultima else "Sin compras",
        }


@router.put("/{id}")
def editar_cliente(id: int, cliente: ClienteCrear, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        existe = session.query(Cliente).filter(
            Cliente.id == id,
            Cliente.usuario_id == usuario_id
        ).first()
        if not existe:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        updates = {
            Cliente.nombre: cliente.nombre,
            Cliente.telefono: cliente.telefono,
            Cliente.credito_limite: cliente.credito_limite,
        }
        if cliente.credito_usado is not None:
            updates[Cliente.credito_usado] = cliente.credito_usado

        session.query(Cliente).filter(Cliente.id == id).update(updates)

        c = session.query(Cliente).filter(Cliente.id == id).first()
        ultima = session.query(func.max(Venta.fecha_hora)).filter(
            Venta.cliente_id == id
        ).scalar()

        return {
            "id": c.id,
            "nombre": c.nombre,
            "telefono": c.telefono,
            "credito_limite": c.credito_limite,
            "credito_usado": c.credito_usado,
            "creado_en": str(c.creado_en),
            "ultima_compra": str(ultima) if ultima else "Sin compras",
        }


@router.delete("/{id}")
def eliminar_cliente(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        session.query(Venta).filter(
            Venta.cliente_id == id,
            Venta.usuario_id == usuario_id
        ).delete(synchronize_session=False)
        session.query(Cliente).filter(
            Cliente.id == id,
            Cliente.usuario_id == usuario_id
        ).delete()
        return {"mensaje": "Cliente eliminado"}


@router.get("/{id}/compras")
def historial_compras(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        compras = session.query(
            Venta.id, Venta.total, Venta.metodo_pago, Venta.fecha_hora
        ).filter(
            Venta.cliente_id == id,
            Venta.usuario_id == usuario_id
        ).order_by(Venta.fecha_hora.desc()).all()

        return [{
            "id": c.id,
            "total": c.total,
            "metodo_pago": c.metodo_pago,
            "fecha_hora": str(c.fecha_hora),
        } for c in compras]
