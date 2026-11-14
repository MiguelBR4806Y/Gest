"""Gestión de vendedores por parte del administrador.

Cada vendedor es una cuenta hija del admin (`rol='vendedor'`, `dueno_id`) que
opera sobre los mismos productos, clientes y ventas. El límite de 10 evita que
un negocio use la aplicación como plataforma multiusuario gratuita.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import Usuario, Venta
from Backend.dinero import a_float, dinero
from Backend.models.schema import Importe
from Backend.routers.auth import MODULOS, SesionActual, hash_password, modulos_de, requiere_admin
from Backend.security import limitar, sanear_texto, validar_password
from Backend.services.credenciales import (
    cifrar_password,
    descifrar_password,
    generar_password,
    generar_usuario,
    usuario_valido,
)

router = APIRouter(prefix="/vendedores", tags=["Vendedores"])

MAX_VENDEDORES = 10


class VendedorCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    puesto: str | None = Field(default=None, max_length=80)
    salario: Importe = Decimal("0.00")
    comision_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    fecha_ingreso: date | None = None
    modulos: list[str] = Field(default_factory=lambda: ["ventas"])
    usuario: str | None = Field(default=None, max_length=64)
    password: str | None = Field(default=None, max_length=128)

    @field_validator("modulos")
    @classmethod
    def _validar_modulos(cls, v: list[str]) -> list[str]:
        desconocidos = [m for m in v if m not in MODULOS]
        if desconocidos:
            raise ValueError(f"Módulo no válido: {desconocidos[0]}")
        return list(dict.fromkeys(v)) or ["ventas"]

    @field_validator("nombre")
    @classmethod
    def _sanear_nombre(cls, v: str) -> str:
        limpio = sanear_texto(v, 120)
        if not limpio:
            raise ValueError("El nombre es obligatorio")
        return limpio

    @field_validator("puesto")
    @classmethod
    def _sanear_puesto(cls, v: str | None) -> str | None:
        return sanear_texto(v, 80) or None

    @field_validator("usuario")
    @classmethod
    def _validar_usuario(cls, v: str | None) -> str | None:
        if not v:
            return None
        limpio = v.strip()
        if not usuario_valido(limpio):
            raise ValueError("El usuario solo admite letras, números, punto, guion y guion bajo")
        return limpio

    @field_validator("password")
    @classmethod
    def _politica(cls, v: str | None) -> str | None:
        if not v:
            return None
        problema = validar_password(v)
        if problema:
            raise ValueError(problema)
        return v


class VendedorEditar(BaseModel):
    nombre: str | None = Field(default=None, max_length=120)
    puesto: str | None = Field(default=None, max_length=80)
    salario: Importe | None = None
    comision_pct: Decimal | None = Field(default=None, ge=0, le=100)
    fecha_ingreso: date | None = None
    modulos: list[str] | None = None
    usuario: str | None = Field(default=None, max_length=64)
    password: str | None = Field(default=None, max_length=128)
    activo: bool | None = None

    @field_validator("modulos")
    @classmethod
    def _validar_modulos(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        desconocidos = [m for m in v if m not in MODULOS]
        if desconocidos:
            raise ValueError(f"Módulo no válido: {desconocidos[0]}")
        return list(dict.fromkeys(v))

    @field_validator("puesto")
    @classmethod
    def _sanear_puesto(cls, v: str | None) -> str | None:
        return sanear_texto(v, 80) or None

    @field_validator("nombre")
    @classmethod
    def _sanear_nombre(cls, v: str | None) -> str | None:
        if v is None:
            return None
        limpio = sanear_texto(v, 120)
        if not limpio:
            raise ValueError("El nombre es obligatorio")
        return limpio

    @field_validator("usuario")
    @classmethod
    def _validar_usuario(cls, v: str | None) -> str | None:
        if not v:
            return None
        limpio = v.strip()
        if not usuario_valido(limpio):
            raise ValueError("El usuario solo admite letras, números, punto, guion y guion bajo")
        return limpio

    @field_validator("password")
    @classmethod
    def _politica(cls, v: str | None) -> str | None:
        if not v:
            return None
        problema = validar_password(v)
        if problema:
            raise ValueError(problema)
        return v


def _serializar(v: Usuario, ventas: int = 0, password: str | None = None) -> dict:
    datos = {
        "id": v.id,
        "usuario": v.usuario,
        "nombre": v.nombre or v.usuario,
        "puesto": v.puesto or "Vendedor",
        "salario": a_float(dinero(v.salario)),
        "comision_pct": float(v.comision_pct or 0),
        "fecha_ingreso": v.fecha_ingreso.isoformat() if v.fecha_ingreso else None,
        "modulos": sorted(modulos_de(v)),
        "activo": bool(v.activo),
        "creado_en": v.creado_en.isoformat() if v.creado_en else None,
        "ventas": ventas,
    }
    if password is not None:
        datos["password"] = password
    return datos


def _buscar(session, vendedor_id: int, admin_id: int) -> Usuario:
    v = session.query(Usuario).filter(
        Usuario.id == vendedor_id,
        Usuario.dueno_id == admin_id,
        Usuario.rol == "vendedor",
    ).with_for_update().first()
    if not v:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")
    return v


def _validar_usuario_libre(session, usuario: str, excluir_id: int | None = None) -> str:
    consulta = session.query(Usuario.id).filter(Usuario.usuario == usuario)
    if excluir_id is not None:
        consulta = consulta.filter(Usuario.id != excluir_id)
    if consulta.first():
        raise HTTPException(status_code=409, detail=f"El usuario {usuario} ya está en uso")
    return usuario


@router.get("/")
def listar_vendedores(sesion: SesionActual = Depends(requiere_admin)):
    with get_db() as session:
        filas = session.query(
            Usuario,
            func.count(Venta.id),
        ).outerjoin(
            Venta, Venta.vendedor_id == Usuario.id
        ).filter(
            Usuario.dueno_id == sesion.negocio_id,
            Usuario.rol == "vendedor",
        ).group_by(Usuario.id).order_by(Usuario.creado_en).all()

        return {
            "items": [_serializar(v, ventas) for v, ventas in filas],
            "total": len(filas),
            "limite": MAX_VENDEDORES,
        }


@router.post(
    "/",
    status_code=201,
    dependencies=[Depends(limitar(30, 300, "crear-vendedor"))],
)
def crear_vendedor(
    datos: VendedorCrear,
    sesion: SesionActual = Depends(requiere_admin),
):
    admin_id = sesion.negocio_id

    with get_db() as session:
        # Bloquear al admin serializa las creaciones simultáneas: sin esto,
        # dos peticiones podían pasar el conteo y crear el vendedor 11.
        session.query(Usuario).filter(Usuario.id == admin_id).with_for_update().first()

        actuales = session.query(func.count(Usuario.id)).filter(
            Usuario.dueno_id == admin_id,
            Usuario.rol == "vendedor",
        ).scalar() or 0
        if actuales >= MAX_VENDEDORES:
            raise HTTPException(
                status_code=409,
                detail=f"Límite alcanzado: {MAX_VENDEDORES} vendedores por negocio",
            )

        usuario = datos.usuario or generar_usuario(datos.nombre, session)
        _validar_usuario_libre(session, usuario)
        password = datos.password or generar_password()

        v = Usuario(
            usuario=usuario,
            password=hash_password(password),
            password_cifrada=cifrar_password(password),
            nombre=datos.nombre,
            puesto=datos.puesto or "Vendedor",
            salario=dinero(datos.salario),
            comision_pct=datos.comision_pct,
            fecha_ingreso=datos.fecha_ingreso,
            modulos=",".join(datos.modulos),
            rol="vendedor",
            dueno_id=admin_id,
            activo=True,
            email=None,
        )
        session.add(v)
        session.flush()

        registrar_evento(
            session, admin_id, "vendedor_creado", "usuario", v.id, v.usuario
        )
        return _serializar(v, password=password)


@router.get(
    "/{vendedor_id}/credenciales",
    dependencies=[Depends(limitar(20, 300, "credenciales-vendedor"))],
)
def ver_credenciales(
    vendedor_id: int,
    sesion: SesionActual = Depends(requiere_admin),
):
    """El admin puede consultar la contraseña de sus vendedores en cualquier momento."""
    with get_db() as session:
        v = session.query(Usuario).filter(
            Usuario.id == vendedor_id,
            Usuario.dueno_id == sesion.negocio_id,
            Usuario.rol == "vendedor",
        ).first()
        if not v:
            raise HTTPException(status_code=404, detail="Vendedor no encontrado")

        password = descifrar_password(v.password_cifrada)
        if password is None:
            raise HTTPException(
                status_code=409,
                detail="La contraseña guardada no se puede descifrar; "
                       "asigna una nueva para este vendedor",
            )

        registrar_evento(
            session, sesion.negocio_id, "credenciales_consultadas", "usuario", v.id, v.usuario
        )
        return {"id": v.id, "usuario": v.usuario, "password": password}


@router.put(
    "/{vendedor_id}",
    dependencies=[Depends(limitar(30, 300, "editar-vendedor"))],
)
def editar_vendedor(
    vendedor_id: int,
    datos: VendedorEditar,
    sesion: SesionActual = Depends(requiere_admin),
):
    with get_db() as session:
        v = _buscar(session, vendedor_id, sesion.negocio_id)

        if datos.nombre is not None:
            v.nombre = datos.nombre
        if datos.puesto is not None:
            v.puesto = datos.puesto
        if datos.salario is not None:
            v.salario = dinero(datos.salario)
        if datos.comision_pct is not None:
            v.comision_pct = datos.comision_pct
        if datos.fecha_ingreso is not None:
            v.fecha_ingreso = datos.fecha_ingreso
        if datos.modulos is not None:
            v.modulos = ",".join(datos.modulos)
        if datos.usuario is not None and datos.usuario != v.usuario:
            v.usuario = _validar_usuario_libre(session, datos.usuario, excluir_id=v.id)
            # El JWT lleva el nombre de usuario; rotarlo revoca la sesión.
            v.token_version = (v.token_version or 0) + 1
        if datos.password:
            v.password = hash_password(datos.password)
            v.password_cifrada = cifrar_password(datos.password)
            v.token_version = (v.token_version or 0) + 1
        if datos.activo is not None:
            v.activo = datos.activo
            if not datos.activo:
                v.token_version = (v.token_version or 0) + 1

        session.flush()
        registrar_evento(
            session, sesion.negocio_id, "vendedor_editado", "usuario", v.id,
            f"activo={bool(v.activo)}",
        )
        password = descifrar_password(v.password_cifrada)
        return _serializar(v, password=password)


@router.delete("/{vendedor_id}")
def eliminar_vendedor(
    vendedor_id: int,
    sesion: SesionActual = Depends(requiere_admin),
):
    """Borra la cuenta si no vendió nada; si vendió, la desactiva para no
    reescribir el histórico de ventas ni los reportes."""
    with get_db() as session:
        v = _buscar(session, vendedor_id, sesion.negocio_id)

        tiene_ventas = session.query(Venta.id).filter(
            Venta.vendedor_id == v.id
        ).first()

        if tiene_ventas:
            v.activo = False
            v.token_version = (v.token_version or 0) + 1
            registrar_evento(
                session, sesion.negocio_id, "vendedor_desactivado", "usuario", v.id, v.usuario
            )
            return {
                "mensaje": "El vendedor tiene ventas registradas: se desactivó en vez de borrarse",
                "desactivado": True,
            }

        nombre = v.usuario
        session.delete(v)
        registrar_evento(
            session, sesion.negocio_id, "vendedor_eliminado", "usuario", vendedor_id, nombre
        )
        return {"mensaje": "Vendedor eliminado", "desactivado": False}


@router.get("/{vendedor_id}/ventas", dependencies=[Depends(limitar(30, 300, "ventas-vendedor"))])
def ventas_del_vendedor(
    vendedor_id: int,
    sesion: SesionActual = Depends(requiere_admin),
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
):
    from sqlalchemy import text

    from Backend.tiempo import fecha_de, rango_dia

    with get_db() as session:
        v = _buscar(session, vendedor_id, sesion.negocio_id)
        zona = session.query(Usuario.zona_horaria).filter(
            Usuario.id == sesion.negocio_id
        ).scalar() or "America/Managua"

        condiciones = ["vendedor_id = :vendedor", "usuario_id = :uid", "estado = 'completada'"]
        params = {"vendedor": v.id, "uid": sesion.negocio_id}
        try:
            if desde:
                params["desde"] = rango_dia(fecha_de(desde, zona), zona)[0]
                condiciones.append("fecha_hora >= :desde")
            if hasta:
                params["hasta"] = rango_dia(fecha_de(hasta, zona), zona)[1]
                condiciones.append("fecha_hora < :hasta")
        except ValueError:
            raise HTTPException(status_code=400, detail="Fechas inválidas, use YYYY-MM-DD")

        where = " AND ".join(condiciones)
        resumen = session.execute(
            text(f"""
                SELECT COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total
                FROM ventas WHERE {where}
            """),
            params,
        ).mappings().first()

        return {
            "vendedor": {"id": v.id, "usuario": v.usuario, "nombre": v.nombre or v.usuario},
            "cantidad": resumen["cantidad"],
            "total": a_float(resumen["total"]),
        }
