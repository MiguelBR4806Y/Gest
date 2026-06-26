from fastapi import APIRouter, HTTPException, Depends
from Backend.db.database import get_db
from Backend.db.models import Promocion
from Backend.models.schema import PromocionCrear
from Backend.routers.auth import verificar_token

router = APIRouter(prefix="/promociones", tags=["Promociones"])


@router.get("/")
def listar_promociones(usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        promos = session.query(Promocion).filter(
            Promocion.usuario_id == usuario_id
        ).order_by(Promocion.id.desc()).all()
        return [{
            "id": p.id,
            "nombre": p.nombre,
            "tipo": p.tipo,
            "valor": p.valor,
            "activa": p.activa,
            "creado_en": str(p.creado_en),
        } for p in promos]


@router.post("/")
def crear_promocion(promo: PromocionCrear, usuario_id: int = Depends(verificar_token)):
    if promo.tipo not in ("porcentaje", "2x1", "monto_fijo"):
        raise HTTPException(status_code=400, detail="Tipo inválido: use porcentaje, 2x1 o monto_fijo")
    with get_db() as session:
        p = Promocion(
            usuario_id=usuario_id,
            nombre=promo.nombre,
            tipo=promo.tipo,
            valor=promo.valor,
            activa=promo.activa,
        )
        session.add(p)
        session.flush()
        return {
            "id": p.id,
            "nombre": p.nombre,
            "tipo": p.tipo,
            "valor": p.valor,
            "activa": p.activa,
            "creado_en": str(p.creado_en),
        }


@router.put("/{id}")
def editar_promocion(id: int, promo: PromocionCrear, usuario_id: int = Depends(verificar_token)):
    if promo.tipo not in ("porcentaje", "2x1", "monto_fijo"):
        raise HTTPException(status_code=400, detail="Tipo inválido")
    with get_db() as session:
        existente = session.query(Promocion).filter(
            Promocion.id == id,
            Promocion.usuario_id == usuario_id
        ).first()
        if not existente:
            raise HTTPException(status_code=404, detail="Promoción no encontrada")
        session.query(Promocion).filter(Promocion.id == id).update({
            Promocion.nombre: promo.nombre,
            Promocion.tipo: promo.tipo,
            Promocion.valor: promo.valor,
            Promocion.activa: promo.activa,
        })
        return {"mensaje": "Promoción actualizada"}


@router.delete("/{id}")
def eliminar_promocion(id: int, usuario_id: int = Depends(verificar_token)):
    with get_db() as session:
        p = session.query(Promocion).filter(
            Promocion.id == id,
            Promocion.usuario_id == usuario_id
        ).first()
        if not p:
            raise HTTPException(status_code=404, detail="Promoción no encontrada")
        session.query(Promocion).filter(Promocion.id == id).delete()
        return {"mensaje": "Promoción eliminada"}
