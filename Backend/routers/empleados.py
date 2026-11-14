"""Empleados del negocio.

El listado une dos fuentes:
- Vendedores: cuentas hijas con acceso al sistema (`usuarios.rol='vendedor'`).
  Se incluyen automáticamente; no se crean por aquí.
- Personal sin cuenta: limpieza, seguridad, bodega… Se registra en `empleados`
  y no puede iniciar sesión.

Así el admin ve una sola plantilla, sin duplicar la gestión de credenciales.
"""

import csv
import io
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, text, update

from Backend.auditoria import registrar_evento
from Backend.db.database import get_db
from Backend.db.models import Bono, Empleado, Usuario, Vacacion, Venta
from Backend.dinero import a_float, dinero
from Backend.models.schema import Importe
from Backend.nomina import (
    INSS_LABORAL,
    INSS_PATRONAL_50_O_MAS,
    INSS_PATRONAL_MENOS_50,
    INATEC,
    LIMITE_EMPLEADOR_GRANDE,
    TRAMOS_IR,
    VERSION_TABLA,
    aguinaldo,
    calcular_comision,
    calcular_nomina,
    calcular_vacaciones,
    resumen_planilla,
)
from Backend.routers.auth import (
    MODULOS,
    SesionActual,
    hash_password,
    modulos_de,
    requiere_modulo,
)
from Backend.security import sanear_texto, validar_password
from Backend.services.credenciales import (
    cifrar_password,
    generar_password,
    generar_usuario,
    usuario_valido,
)

router = APIRouter(
    prefix="/empleados",
    tags=["Empleados"],
)

MAX_PUESTO = 80
# El límite es de cuentas con acceso, no de personal registrado.
MAX_CUENTAS = 10


class EmpleadoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    puesto: str = Field(min_length=1, max_length=MAX_PUESTO)
    salario: Importe = Decimal("0.00")
    comision_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    fecha_ingreso: date | None = None
    telefono: str | None = Field(default=None, max_length=32)
    notas: str | None = Field(default=None, max_length=300)
    activo: bool = True

    # Acceso al sistema: si `dar_acceso` es True se crea una cuenta con login.
    dar_acceso: bool = False
    modulos: list[str] = Field(default_factory=list)
    usuario: str | None = Field(default=None, max_length=64)
    password: str | None = Field(default=None, max_length=128)

    @field_validator("modulos")
    @classmethod
    def _validar_modulos(cls, v: list[str]) -> list[str]:
        desconocidos = [m for m in v if m not in MODULOS]
        if desconocidos:
            raise ValueError(f"Módulo no válido: {desconocidos[0]}")
        return list(dict.fromkeys(v))

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

    @field_validator("nombre")
    @classmethod
    def _sanear_nombre(cls, v: str) -> str:
        limpio = sanear_texto(v, 120)
        if not limpio:
            raise ValueError("El nombre es obligatorio")
        return limpio

    @field_validator("puesto")
    @classmethod
    def _sanear_puesto(cls, v: str) -> str:
        limpio = sanear_texto(v, MAX_PUESTO)
        if not limpio:
            raise ValueError("El puesto es obligatorio")
        return limpio

    @field_validator("telefono")
    @classmethod
    def _sanear_telefono(cls, v: str | None) -> str | None:
        limpio = sanear_texto(v, 32)
        if not limpio:
            return None
        if not all(c.isdigit() or c in "+()- ./" for c in limpio):
            raise ValueError("El teléfono contiene caracteres no válidos")
        return limpio

    @field_validator("notas")
    @classmethod
    def _sanear_notas(cls, v: str | None) -> str | None:
        return sanear_texto(v, 300) or None


class BonoCrear(BaseModel):
    persona_tipo: str = Field(pattern="^(empleado|cuenta)$")
    persona_id: int = Field(gt=0)
    concepto: str = Field(min_length=1, max_length=120)
    monto: Importe
    fecha: date
    recurrente: bool = False
    activo: bool = True

    @field_validator("concepto")
    @classmethod
    def _sanear_concepto(cls, v: str) -> str:
        limpio = sanear_texto(v, 120)
        if not limpio:
            raise ValueError("El concepto es obligatorio")
        return limpio


class VacacionCrear(BaseModel):
    persona_tipo: str = Field(pattern="^(empleado|cuenta)$")
    persona_id: int = Field(gt=0)
    fecha_inicio: date
    fecha_fin: date
    dias: int = Field(ge=1, le=365)
    nota: str | None = Field(default=None, max_length=300)

    @field_validator("nota")
    @classmethod
    def _sanear_nota(cls, v: str | None) -> str | None:
        return sanear_texto(v, 300) or None

    @field_validator("fecha_fin")
    @classmethod
    def _rango(cls, v: date, info) -> date:
        inicio = info.data.get("fecha_inicio")
        if inicio and v < inicio:
            raise ValueError("La fecha final no puede ser anterior a la inicial")
        return v


def _serializar_bono(b: Bono) -> dict:
    return {
        "id": b.id,
        "persona_tipo": b.persona_tipo,
        "persona_id": b.persona_id,
        "concepto": b.concepto,
        "monto": a_float(b.monto),
        "fecha": b.fecha.isoformat(),
        "recurrente": bool(b.recurrente),
        "activo": bool(b.activo),
    }


def _serializar_vacacion(v: Vacacion) -> dict:
    return {
        "id": v.id,
        "persona_tipo": v.persona_tipo,
        "persona_id": v.persona_id,
        "fecha_inicio": v.fecha_inicio.isoformat(),
        "fecha_fin": v.fecha_fin.isoformat(),
        "dias": v.dias,
        "nota": v.nota,
    }


def _persona_existe(session, persona_tipo: str, persona_id: int, negocio_id: int) -> None:
    """Comprueba que la persona pertenezca al negocio; si no, 404."""
    if persona_tipo == "empleado":
        existe = session.query(Empleado.id).filter(
            Empleado.id == persona_id,
            Empleado.usuario_id == negocio_id,
        ).first()
    else:
        existe = session.query(Usuario.id).filter(
            Usuario.id == persona_id,
            Usuario.dueno_id == negocio_id,
            Usuario.rol == "vendedor",
        ).first()
    if not existe:
        raise HTTPException(status_code=404, detail="Persona no encontrada")


def _datos_persona(session, persona_tipo: str, persona_id: int, negocio_id: int):
    """Devuelve (salario, comision_pct, fecha_ingreso, creado_en) de la persona."""
    if persona_tipo == "empleado":
        e = session.query(Empleado).filter(
            Empleado.id == persona_id, Empleado.usuario_id == negocio_id
        ).first()
        if not e:
            return None
        return dinero(e.salario), e.comision_pct, e.fecha_ingreso, e.creado_en
    u = session.query(Usuario).filter(
        Usuario.id == persona_id, Usuario.dueno_id == negocio_id
    ).first()
    if not u:
        return None
    return dinero(u.salario), u.comision_pct, u.fecha_ingreso, u.creado_en


def _rangos_periodo(desde: str | None, hasta: str | None, zona: str):
    from Backend.tiempo import fecha_de, hoy_local, rango_dia

    try:
        if desde or hasta:
            dia_desde = fecha_de(desde, zona) if desde else fecha_de(hasta, zona)
            dia_hasta = fecha_de(hasta, zona) if hasta else dia_desde
        else:
            hoy = hoy_local(zona)
            dia_desde = hoy.replace(day=1)
            dia_hasta = hoy
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas, use YYYY-MM-DD")
    if dia_hasta < dia_desde:
        raise HTTPException(status_code=400, detail="La fecha final es anterior a la inicial")

    inicio, fin = rango_dia(dia_desde, zona)[0], rango_dia(dia_hasta, zona)[1]
    return dia_desde, dia_hasta, inicio, fin


def _zona(session, negocio_id: int) -> str:
    from Backend.tiempo import ZONA_POR_DEFECTO

    return session.query(Usuario.zona_horaria).filter(
        Usuario.id == negocio_id
    ).scalar() or ZONA_POR_DEFECTO


def _bonos_del_periodo(session, negocio_id, persona_tipo, persona_id, dia_desde, dia_hasta):
    """Bonos que se pagan en el periodo; los recurrentes cuentan cada mes."""
    consulta = session.query(Bono).filter(
        Bono.usuario_id == negocio_id,
        Bono.persona_tipo == persona_tipo,
        Bono.persona_id == persona_id,
        Bono.activo.is_(True),
        Bono.fecha <= dia_hasta,
        (Bono.recurrente.is_(True)) | (Bono.fecha >= dia_desde),
    )
    bonos = consulta.order_by(Bono.fecha).all()

    total = dinero(0)
    detalle = []
    for b in bonos:
        total += dinero(b.monto)
        detalle.append({
            "id": b.id,
            "concepto": b.concepto,
            "monto": a_float(b.monto),
            "fecha": b.fecha.isoformat(),
            "recurrente": bool(b.recurrente),
        })
    return total, detalle


def _comision_del_periodo(session, negocio_id, persona_tipo, persona_id, inicio, fin):
    """Comisión solo para cuentas: se calcula sobre sus ventas completadas."""
    if persona_tipo != "cuenta":
        return calcular_comision(0, 0)

    fila = session.execute(
        text("""
            SELECT COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total
            FROM ventas
            WHERE usuario_id = :uid
              AND vendedor_id = :vid
              AND estado = 'completada'
              AND fecha_hora >= :inicio AND fecha_hora < :fin
        """),
        {"uid": negocio_id, "vid": persona_id, "inicio": inicio, "fin": fin},
    ).mappings().first()

    pct = session.query(Usuario.comision_pct).filter(
        Usuario.id == persona_id
    ).scalar() or 0

    resultado = calcular_comision(fila["total"], pct)
    resultado["ventas_cantidad"] = fila["cantidad"]
    return resultado


def _dias_tomados(session, negocio_id, persona_tipo, persona_id) -> int:
    total = session.query(func.coalesce(func.sum(Vacacion.dias), 0)).filter(
        Vacacion.usuario_id == negocio_id,
        Vacacion.persona_tipo == persona_tipo,
        Vacacion.persona_id == persona_id,
    ).scalar()
    return int(total or 0)


def _serializar(e: Empleado) -> dict:
    salario = dinero(e.salario)
    return {
        "id": e.id,
        "nombre": e.nombre,
        "puesto": e.puesto,
        "salario": float(salario),
        "telefono": e.telefono,
        "notas": e.notas,
        "activo": bool(e.activo),
        "tipo": "personal",
        "con_acceso": False,
        "usuario": None,
        "modulos": [],
        "comision_pct": float(e.comision_pct or 0),
        "fecha_ingreso": e.fecha_ingreso.isoformat() if e.fecha_ingreso else None,
        "nomina": calcular_nomina(salario, 1) if salario > 0 else None,
        "creado_en": e.creado_en.isoformat() if e.creado_en else None,
    }


def _serializar_vendedor(v: Usuario, ventas: int = 0) -> dict:
    salario = dinero(v.salario)
    return {
        "id": v.id,
        "nombre": v.nombre or v.usuario,
        "puesto": v.puesto or "Vendedor",
        "salario": float(salario),
        "telefono": None,
        "notas": None,
        "activo": bool(v.activo),
        "tipo": "vendedor",
        "con_acceso": True,
        "usuario": v.usuario,
        "modulos": sorted(modulos_de(v)),
        "ventas": ventas,
        "comision_pct": float(v.comision_pct or 0),
        "fecha_ingreso": v.fecha_ingreso.isoformat() if v.fecha_ingreso else None,
        "nomina": calcular_nomina(salario, 1) if salario > 0 else None,
        "creado_en": v.creado_en.isoformat() if v.creado_en else None,
    }


@router.get("/", dependencies=[Depends(requiere_modulo("rrhh"))])
def listar_empleados(sesion: SesionActual = Depends(requiere_modulo("rrhh"))):
    with get_db() as session:
        vendedores = session.query(
            Usuario, func.count(Venta.id)
        ).outerjoin(
            Venta, Venta.vendedor_id == Usuario.id
        ).filter(
            Usuario.dueno_id == sesion.negocio_id,
            Usuario.rol == "vendedor",
        ).group_by(Usuario.id).all()

        personal = session.query(Empleado).filter(
            Empleado.usuario_id == sesion.negocio_id
        ).order_by(Empleado.nombre).all()

        items = [_serializar_vendedor(v, ventas) for v, ventas in vendedores]
        items += [_serializar(e) for e in personal]
        items.sort(key=lambda i: (not i["activo"], i["puesto"].lower(), i["nombre"].lower()))

        # La tasa patronal depende de la plantilla total. Además, cada persona
        # recibe su comisión del mes y los bonos que caen en él.
        plantilla = len(items)
        zona = _zona(session, sesion.negocio_id)
        dia_desde, dia_hasta, inicio, fin = _rangos_periodo(None, None, zona)

        filas_resumen = []
        for item in items:
            tipo = "cuenta" if item["tipo"] == "vendedor" else "empleado"

            comision = _comision_del_periodo(
                session, sesion.negocio_id, tipo, item["id"], inicio, fin
            )
            bonos, detalle_bonos = _bonos_del_periodo(
                session, sesion.negocio_id, tipo, item["id"], dia_desde, dia_hasta
            )
            tomados = _dias_tomados(session, sesion.negocio_id, tipo, item["id"])
            vacaciones = calcular_vacaciones(
                _fecha_efectiva(item), item["salario"], tomados
            )

            extra = dinero(comision["comision"]) + bonos
            item["comision"] = comision if tipo == "cuenta" else calcular_comision(0, 0)
            item["bonos"] = a_float(bonos)
            item["bonos_detalle"] = detalle_bonos
            item["vacaciones"] = vacaciones
            if item["salario"] > 0:
                detalle_extra = []
                if comision["comision"] > 0:
                    detalle_extra.append({
                        "tipo": "comision",
                        "concepto": f"Comisión {comision['comision_pct']:.2f}%",
                        "monto": comision["comision"],
                    })
                for b in detalle_bonos:
                    detalle_extra.append({
                        "tipo": "bono",
                        "concepto": b["concepto"],
                        "monto": b["monto"],
                        "recurrente": b["recurrente"],
                    })
                item["nomina"] = calcular_nomina(
                    item["salario"], plantilla, extra, detalle_extra
                )

            if item["activo"] and item["salario"] > 0:
                filas_resumen.append({"salario": item["salario"], "extra": float(extra)})

        resumen = resumen_planilla(filas_resumen)
        resumen["con_salario"] = len(filas_resumen)
        resumen["sin_salario"] = sum(
            1 for i in items if i["activo"] and i["salario"] <= 0
        )

        return {
            "items": items,
            "total": len(items),
            "con_acceso": len(vendedores),
            "sin_acceso": len(personal),
            "resumen": resumen,
        }


def _fecha_efectiva(item: dict):
    """Fecha de ingreso; si falta, se usa la de creación de la cuenta."""
    from datetime import datetime as _dt

    if item.get("fecha_ingreso"):
        return date.fromisoformat(item["fecha_ingreso"])
    creado = item.get("creado_en")
    if creado:
        try:
            return _dt.fromisoformat(creado).date()
        except ValueError:
            return None
    return None


# ── Bonos y comisiones ──
# Estas rutas van antes de `/{empleado_id}` por la misma razón que las de
# nómina: si no, FastAPI intentaría convertir "bonos" en un id.


@router.get("/bonos")
def listar_bonos(
    sesion: SesionActual = Depends(requiere_modulo("rrhh")),
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
    persona_tipo: str | None = Query(default=None, pattern="^(empleado|cuenta)$"),
    persona_id: int | None = Query(default=None, gt=0),
):
    """Bonos del negocio. Sin fechas, devuelve los de los próximos 12 meses."""
    with get_db() as session:
        consulta = session.query(Bono).filter(
            Bono.usuario_id == sesion.negocio_id
        )
        if persona_tipo:
            consulta = consulta.filter(Bono.persona_tipo == persona_tipo)
        if persona_id:
            consulta = consulta.filter(Bono.persona_id == persona_id)

        if desde:
            try:
                consulta = consulta.filter(Bono.fecha >= date.fromisoformat(desde))
            except ValueError:
                raise HTTPException(status_code=400, detail="Fecha inválida, use YYYY-MM-DD")
        if hasta:
            try:
                consulta = consulta.filter(Bono.fecha <= date.fromisoformat(hasta))
            except ValueError:
                raise HTTPException(status_code=400, detail="Fecha inválida, use YYYY-MM-DD")

        bonos = consulta.order_by(Bono.fecha, Bono.id).all()
        return {
            "items": [_serializar_bono(b) for b in bonos],
            "total": a_float(sum((dinero(b.monto) for b in bonos), dinero(0))),
        }


@router.post("/bonos", status_code=201)
def crear_bono(datos: BonoCrear, sesion: SesionActual = Depends(requiere_modulo("rrhh"))):
    with get_db() as session:
        _persona_existe(session, datos.persona_tipo, datos.persona_id, sesion.negocio_id)

        bono = Bono(
            usuario_id=sesion.negocio_id,
            persona_tipo=datos.persona_tipo,
            persona_id=datos.persona_id,
            concepto=datos.concepto,
            monto=dinero(datos.monto),
            fecha=datos.fecha,
            recurrente=datos.recurrente,
            activo=datos.activo,
        )
        session.add(bono)
        session.flush()
        registrar_evento(
            session, sesion.negocio_id, "bono_creado", "bono", bono.id,
            f"{bono.concepto} C${bono.monto}",
        )
        return _serializar_bono(bono)


def _buscar_bono(session, bono_id: int, negocio_id: int) -> Bono:
    b = session.query(Bono).filter(
        Bono.id == bono_id,
        Bono.usuario_id == negocio_id,
    ).with_for_update().first()
    if not b:
        raise HTTPException(status_code=404, detail="Bono no encontrado")
    return b


@router.put("/bonos/{bono_id}")
def editar_bono(
    bono_id: int,
    datos: BonoCrear,
    sesion: SesionActual = Depends(requiere_modulo("rrhh")),
):
    with get_db() as session:
        _buscar_bono(session, bono_id, sesion.negocio_id)
        _persona_existe(session, datos.persona_tipo, datos.persona_id, sesion.negocio_id)

        session.execute(
            update(Bono)
            .where(Bono.id == bono_id, Bono.usuario_id == sesion.negocio_id)
            .values(
                persona_tipo=datos.persona_tipo,
                persona_id=datos.persona_id,
                concepto=datos.concepto,
                monto=dinero(datos.monto),
                fecha=datos.fecha,
                recurrente=datos.recurrente,
                activo=datos.activo,
            )
        )
        registrar_evento(
            session, sesion.negocio_id, "bono_editado", "bono", bono_id, datos.concepto
        )
        b = session.query(Bono).filter(Bono.id == bono_id).first()
        return _serializar_bono(b)


@router.delete("/bonos/{bono_id}")
def eliminar_bono(
    bono_id: int,
    sesion: SesionActual = Depends(requiere_modulo("rrhh")),
):
    with get_db() as session:
        b = _buscar_bono(session, bono_id, sesion.negocio_id)
        concepto = b.concepto
        session.delete(b)
        registrar_evento(
            session, sesion.negocio_id, "bono_eliminado", "bono", bono_id, concepto
        )
        return {"mensaje": "Bono eliminado"}


# ── Vacaciones ──


@router.get("/vacaciones")
def listar_vacaciones(
    sesion: SesionActual = Depends(requiere_modulo("rrhh")),
    persona_tipo: str | None = Query(default=None, pattern="^(empleado|cuenta)$"),
    persona_id: int | None = Query(default=None, gt=0),
):
    """Registros de días tomados y el saldo de cada persona filtrada."""
    with get_db() as session:
        consulta = session.query(Vacacion).filter(
            Vacacion.usuario_id == sesion.negocio_id
        )
        if persona_tipo:
            consulta = consulta.filter(Vacacion.persona_tipo == persona_tipo)
        if persona_id:
            consulta = consulta.filter(Vacacion.persona_id == persona_id)

        registros = consulta.order_by(Vacacion.fecha_inicio.desc()).all()

        saldo = None
        if persona_tipo and persona_id:
            _persona_existe(session, persona_tipo, persona_id, sesion.negocio_id)
            datos = _datos_persona(session, persona_tipo, persona_id, sesion.negocio_id)
            salario, _pct, ingreso, creado = datos
            saldo = calcular_vacaciones(
                ingreso or creado, salario, _dias_tomados(
                    session, sesion.negocio_id, persona_tipo, persona_id
                )
            )

        return {
            "items": [_serializar_vacacion(v) for v in registros],
            "total_dias": sum(v.dias for v in registros),
            "saldo": saldo,
        }


@router.post("/vacaciones", status_code=201)
def crear_vacacion(
    datos: VacacionCrear,
    sesion: SesionActual = Depends(requiere_modulo("rrhh")),
):
    with get_db() as session:
        _persona_existe(session, datos.persona_tipo, datos.persona_id, sesion.negocio_id)

        salario, _pct, ingreso, creado = _datos_persona(
            session, datos.persona_tipo, datos.persona_id, sesion.negocio_id
        )
        tomados = _dias_tomados(
            session, sesion.negocio_id, datos.persona_tipo, datos.persona_id
        )
        saldo = calcular_vacaciones(ingreso or creado, salario, tomados)
        if datos.dias > saldo["dias_disponibles"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"El saldo disponible es {saldo['dias_disponibles']:.1f} días; "
                    f"no se pueden registrar {datos.dias}"
                ),
            )

        v = Vacacion(
            usuario_id=sesion.negocio_id,
            persona_tipo=datos.persona_tipo,
            persona_id=datos.persona_id,
            fecha_inicio=datos.fecha_inicio,
            fecha_fin=datos.fecha_fin,
            dias=datos.dias,
            nota=datos.nota,
        )
        session.add(v)
        session.flush()
        registrar_evento(
            session, sesion.negocio_id, "vacaciones_registradas", "vacacion", v.id,
            f"{datos.dias} días desde {datos.fecha_inicio}",
        )

        nuevo_saldo = calcular_vacaciones(
            ingreso or creado, salario, tomados + datos.dias
        )
        return {**_serializar_vacacion(v), "saldo": nuevo_saldo}


@router.delete("/vacaciones/{vacacion_id}")
def eliminar_vacacion(
    vacacion_id: int,
    sesion: SesionActual = Depends(requiere_modulo("rrhh")),
):
    with get_db() as session:
        v = session.query(Vacacion).filter(
            Vacacion.id == vacacion_id,
            Vacacion.usuario_id == sesion.negocio_id,
        ).with_for_update().first()
        if not v:
            raise HTTPException(status_code=404, detail="Registro no encontrado")

        dias = v.dias
        session.delete(v)
        registrar_evento(
            session, sesion.negocio_id, "vacaciones_eliminadas", "vacacion",
            vacacion_id, f"{dias} días",
        )
        return {"mensaje": "Registro de vacaciones eliminado"}


# ── Resumen de pago de una persona en un periodo ──


@router.get("/resumen-pago")
def resumen_pago(
    sesion: SesionActual = Depends(requiere_modulo("rrhh")),
    persona_tipo: str = Query(pattern="^(empleado|cuenta)$"),
    persona_id: int = Query(gt=0),
    desde: str = Query(default=None, max_length=10),
    hasta: str = Query(default=None, max_length=10),
):
    """Nómina del periodo: base + comisión + bonos, con INSS e IR."""
    with get_db() as session:
        _persona_existe(session, persona_tipo, persona_id, sesion.negocio_id)
        zona = _zona(session, sesion.negocio_id)
        dia_desde, dia_hasta, inicio, fin = _rangos_periodo(desde, hasta, zona)

        salario, pct, ingreso, creado = _datos_persona(
            session, persona_tipo, persona_id, sesion.negocio_id
        )
        comision = _comision_del_periodo(
            session, sesion.negocio_id, persona_tipo, persona_id, inicio, fin
        )
        bonos, detalle_bonos = _bonos_del_periodo(
            session, sesion.negocio_id, persona_tipo, persona_id, dia_desde, dia_hasta
        )
        plantilla = session.query(func.count(Usuario.id)).filter(
            Usuario.dueno_id == sesion.negocio_id, Usuario.rol == "vendedor"
        ).scalar() or 0
        plantilla += session.query(func.count(Empleado.id)).filter(
            Empleado.usuario_id == sesion.negocio_id
        ).scalar() or 0

        detalle_extra = []
        if comision["comision"] > 0:
            detalle_extra.append({
                "tipo": "comision",
                "concepto": f"Comisión {comision['comision_pct']:.2f}% "
                            f"sobre {comision['ventas_cantidad']} ventas",
                "monto": comision["comision"],
            })
        for b in detalle_bonos:
            detalle_extra.append({
                "tipo": "bono",
                "concepto": b["concepto"],
                "monto": b["monto"],
                "fecha": b["fecha"],
                "recurrente": b["recurrente"],
            })

        extra = dinero(comision["comision"]) + bonos
        nomina = calcular_nomina(salario, max(plantilla, 1), extra, detalle_extra)

        tomados = _dias_tomados(session, sesion.negocio_id, persona_tipo, persona_id)
        vacaciones = calcular_vacaciones(ingreso or creado, salario, tomados)

        return {
            "desde": dia_desde.isoformat(),
            "hasta": dia_hasta.isoformat(),
            "salario_base": float(salario),
            "comision": comision,
            "bonos": a_float(bonos),
            "bonos_detalle": detalle_bonos,
            "nomina": nomina,
            "vacaciones": vacaciones,
        }


# ── Ayuda de cálculo de nómina e impuestos ──
# Van antes de `/{empleado_id}`: si no, FastAPI interpretaría "nomina" o
# "exportar" como un id y devolvería 422.


@router.get("/exportar")
def exportar_planilla(sesion: SesionActual = Depends(requiere_modulo("rrhh"))):
    """CSV de la planilla del mes con el desglose de cada persona."""
    with get_db() as session:
        vendedores = session.query(Usuario).filter(
            Usuario.dueno_id == sesion.negocio_id,
            Usuario.rol == "vendedor",
            Usuario.activo.is_(True),
        ).order_by(Usuario.nombre).all()
        personal = session.query(Empleado).filter(
            Empleado.usuario_id == sesion.negocio_id,
            Empleado.activo.is_(True),
        ).order_by(Empleado.nombre).all()

        filas = [
            ("cuenta", v.id, v.nombre or v.usuario, v.puesto or "Vendedor",
             dinero(v.salario), v.comision_pct, v.fecha_ingreso, v.creado_en)
            for v in vendedores
        ] + [
            ("empleado", e.id, e.nombre, e.puesto, dinero(e.salario),
             e.comision_pct, e.fecha_ingreso, e.creado_en)
            for e in personal
        ]

        plantilla = len(filas)
        zona = _zona(session, sesion.negocio_id)
        dia_desde, dia_hasta, inicio, fin = _rangos_periodo(None, None, zona)

        salida = io.StringIO()
        escritor = csv.writer(salida, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        escritor.writerow([
            "Nombre", "Puesto", "Salario base C$", "Comisión %", "Comisión C$",
            "Bonos C$", "INSS laboral C$", "IR mensual C$", "Neto C$",
            "INSS patronal C$", "INATEC C$", "Costo empresa C$",
            "Vacaciones días", "Vacaciones C$",
        ])

        totales = {clave: dinero(0) for clave in (
            "bruto", "comision", "bonos", "inss_laboral", "ir", "neto",
            "inss_patronal", "inatec", "costo", "vacaciones_valor",
        )}
        for tipo, pid, nombre, puesto, salario, pct, ingreso, creado in filas:
            comision = _comision_del_periodo(session, sesion.negocio_id, tipo, pid, inicio, fin)
            bonos, _detalle = _bonos_del_periodo(
                session, sesion.negocio_id, tipo, pid, dia_desde, dia_hasta
            )
            extra = dinero(comision["comision"]) + bonos
            nomina = calcular_nomina(salario, plantilla, extra)

            tomados = _dias_tomados(session, sesion.negocio_id, tipo, pid)
            vacaciones = calcular_vacaciones(ingreso or creado, salario, tomados)

            if tipo == "cuenta":
                totales["comision"] += dinero(comision["comision"])
            totales["bruto"] += salario
            totales["bonos"] += bonos
            totales["inss_laboral"] += dinero(nomina["inss_laboral"])
            totales["ir"] += dinero(nomina["ir_mensual"])
            totales["neto"] += dinero(nomina["salario_neto"])
            totales["inss_patronal"] += dinero(nomina["inss_patronal"])
            totales["inatec"] += dinero(nomina["inatec"])
            totales["costo"] += dinero(nomina["costo_total_empleador"])
            totales["vacaciones_valor"] += dinero(vacaciones["valor_dias"])

            escritor.writerow([
                nombre, puesto,
                f"{salario:.2f}",
                f"{Decimal(str(pct or 0)):.2f}",
                f"{dinero(comision['comision']):.2f}",
                f"{bonos:.2f}",
                f"{dinero(nomina['inss_laboral']):.2f}",
                f"{dinero(nomina['ir_mensual']):.2f}",
                f"{dinero(nomina['salario_neto']):.2f}",
                f"{dinero(nomina['inss_patronal']):.2f}",
                f"{dinero(nomina['inatec']):.2f}",
                f"{dinero(nomina['costo_total_empleador']):.2f}",
                f"{vacaciones['dias_disponibles']:.1f}",
                f"{dinero(vacaciones['valor_dias']):.2f}",
            ])

        escritor.writerow([])
        escritor.writerow([
            "TOTAL", f"{plantilla} personas",
            f"{totales['bruto']:.2f}",
            "",
            f"{totales['comision']:.2f}",
            f"{totales['bonos']:.2f}",
            f"{totales['inss_laboral']:.2f}",
            f"{totales['ir']:.2f}",
            f"{totales['neto']:.2f}",
            f"{totales['inss_patronal']:.2f}",
            f"{totales['inatec']:.2f}",
            f"{totales['costo']:.2f}",
            "",
            f"{totales['vacaciones_valor']:.2f}",
        ])

    return Response(
        content="\ufeff" + salida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="planilla.csv"'},
    )


@router.get("/nomina/tabla")
def tabla_fiscal(_: SesionActual = Depends(requiere_modulo("rrhh"))):
    """Parámetros vigentes, para que la UI explique de dónde sale cada número."""
    return {
        "version": VERSION_TABLA,
        "tramos_ir": [
            {
                "desde": float(desde),
                "hasta": float(hasta) if hasta is not None else None,
                "tasa": float(tasa * 100),
                "impuesto_base": float(base),
                "exceso_sobre": float(exceso),
            }
            for desde, hasta, base, tasa, exceso in TRAMOS_IR
        ],
        "inss_laboral": float(INSS_LABORAL * 100),
        "inss_patronal": float(INSS_PATRONAL_MENOS_50 * 100),
        "inss_patronal_grande": float(INSS_PATRONAL_50_O_MAS * 100),
        "limite_empleador_grande": LIMITE_EMPLEADOR_GRANDE,
        "inatec": float(INATEC * 100),
        "nota": "Ley 822 art. 23 (IR), Decreto 06-2019 art. 11 (INSS) y "
                "Ley 1063 art. 24 (INATEC). Verifica las cifras antes de declarar.",
    }


class SimulacionNomina(BaseModel):
    salario: Importe
    empleados_empresa: int = Field(default=1, ge=1, le=100_000)


@router.post("/nomina/simular")
def simular_nomina(
    datos: SimulacionNomina,
    _: SesionActual = Depends(requiere_modulo("rrhh")),
):
    """Calcula el desglose de un salario sin guardar nada."""
    resultado = calcular_nomina(datos.salario, datos.empleados_empresa)
    resultado.update(aguinaldo(datos.salario))
    return resultado


def _modulos_permitidos(sesion: SesionActual) -> set[str]:
    """Un usuario de RRHH no puede conceder módulos que él no tiene.

    Evita la escalada: alguien con solo RRHH no debe poder crear una cuenta
    con contabilidad.
    """
    return set(MODULOS) if sesion.es_admin else set(sesion.modulos)


@router.post("/", status_code=201)
def crear_empleado(
    datos: EmpleadoCrear,
    sesion: SesionActual = Depends(requiere_modulo("rrhh")),
):
    """Registra personal; si `dar_acceso`, además crea su cuenta de usuario."""
    if datos.dar_acceso:
        if not datos.modulos:
            raise HTTPException(
                status_code=400,
                detail="Indica al menos un módulo para dar acceso al sistema",
            )
        fuera_de_alcance = set(datos.modulos) - _modulos_permitidos(sesion)
        if fuera_de_alcance:
            raise HTTPException(
                status_code=403,
                detail="No puedes conceder un módulo que no tienes",
            )

    with get_db() as session:
        if datos.dar_acceso:
            return _crear_cuenta(session, datos, sesion)

        e = Empleado(
            usuario_id=sesion.negocio_id,
            nombre=datos.nombre,
            puesto=datos.puesto,
            salario=dinero(datos.salario),
            comision_pct=datos.comision_pct,
            fecha_ingreso=datos.fecha_ingreso,
            telefono=datos.telefono,
            notas=datos.notas,
            activo=datos.activo,
        )
        session.add(e)
        session.flush()
        registrar_evento(
            session, sesion.negocio_id, "empleado_creado", "empleado", e.id,
            f"{e.nombre} ({e.puesto})",
        )
        return _serializar(e)


def _crear_cuenta(session, datos: EmpleadoCrear, sesion: SesionActual) -> dict:
    """Crea la cuenta hija. Comparte el límite de 10 con los vendedores."""
    admin_id = sesion.negocio_id

    # Bloquear al admin serializa las creaciones simultáneas: sin esto, dos
    # peticiones podían pasar el conteo y crear la cuenta 11.
    session.query(Usuario).filter(Usuario.id == admin_id).with_for_update().first()
    actuales = session.query(func.count(Usuario.id)).filter(
        Usuario.dueno_id == admin_id,
        Usuario.rol == "vendedor",
    ).scalar() or 0
    if actuales >= MAX_CUENTAS:
        raise HTTPException(
            status_code=409,
            detail=f"Límite alcanzado: {MAX_CUENTAS} cuentas con acceso por negocio",
        )

    usuario = datos.usuario or generar_usuario(datos.nombre, session)
    if session.query(Usuario.id).filter(Usuario.usuario == usuario).first():
        raise HTTPException(status_code=409, detail=f"El usuario {usuario} ya está en uso")
    password = datos.password or generar_password()

    v = Usuario(
        usuario=usuario,
        password=hash_password(password),
        password_cifrada=cifrar_password(password),
        nombre=datos.nombre,
        puesto=datos.puesto,
        salario=dinero(datos.salario),
        comision_pct=datos.comision_pct,
        fecha_ingreso=datos.fecha_ingreso,
        modulos=",".join(datos.modulos),
        rol="vendedor",
        dueno_id=admin_id,
        activo=datos.activo,
        email=None,
    )
    session.add(v)
    session.flush()
    registrar_evento(
        session, admin_id, "empleado_con_acceso_creado", "usuario", v.id,
        f"{v.nombre} ({', '.join(datos.modulos)})",
    )

    resultado = _serializar_vendedor(v)
    resultado["modulos"] = datos.modulos
    resultado["credenciales"] = {"usuario": usuario, "password": password}
    return resultado


def _buscar_personal(session, empleado_id: int, usuario_id: int) -> Empleado:
    e = session.query(Empleado).filter(
        Empleado.id == empleado_id,
        Empleado.usuario_id == usuario_id,
    ).with_for_update().first()
    if not e:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return e


@router.put("/{empleado_id}")
def editar_empleado(
    empleado_id: int,
    datos: EmpleadoCrear,
    sesion: SesionActual = Depends(requiere_modulo("rrhh")),
):
    """Solo aplica al personal sin cuenta; las cuentas se editan en Vendedores."""
    with get_db() as session:
        _buscar_personal(session, empleado_id, sesion.negocio_id)
        session.execute(
            update(Empleado)
            .where(
                Empleado.id == empleado_id,
                Empleado.usuario_id == sesion.negocio_id,
            )
            .values(
                nombre=datos.nombre,
                puesto=datos.puesto,
                salario=dinero(datos.salario),
                comision_pct=datos.comision_pct,
                fecha_ingreso=datos.fecha_ingreso,
                telefono=datos.telefono,
                notas=datos.notas,
                activo=datos.activo,
            )
        )
        registrar_evento(
            session, sesion.negocio_id, "empleado_editado", "empleado", empleado_id,
            f"{datos.nombre} ({datos.puesto})",
        )
        e = session.query(Empleado).filter(Empleado.id == empleado_id).first()
        return _serializar(e)


@router.delete("/{empleado_id}")
def eliminar_empleado(
    empleado_id: int,
    sesion: SesionActual = Depends(requiere_modulo("rrhh")),
):
    with get_db() as session:
        e = _buscar_personal(session, empleado_id, sesion.negocio_id)
        nombre = e.nombre
        session.delete(e)
        registrar_evento(
            session, sesion.negocio_id, "empleado_eliminado", "empleado",
            empleado_id, nombre,
        )
        return {"mensaje": "Empleado eliminado"}

