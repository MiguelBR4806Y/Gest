"""Permisos por módulo: cada cuenta solo entra a lo que tiene asignado."""

from Backend.db.database import SessionLocal
from Backend.db.models import Usuario


def _cuenta(client, headers, nombre, modulos, usuario=None):
    """Crea una cuenta hija con módulos concretos y devuelve sus cabeceras."""
    cuerpo = {"nombre": nombre, "modulos": modulos}
    if usuario:
        cuerpo["usuario"] = usuario
    r = client.post("/vendedores/", json=cuerpo, headers=headers)
    assert r.status_code == 201, r.text
    creado = r.json()

    login = client.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    )
    assert login.status_code == 200, login.text
    sesion = login.json()
    return creado, {"Authorization": f"Bearer {sesion['token']}"}, sesion


def test_login_devuelve_los_modulos(cliente_api, auth_admin):
    _, _, sesion = _cuenta(
        cliente_api, auth_admin.headers, "Conta", ["contabilidad"]
    )
    assert sesion["modulos"] == ["contabilidad"]
    assert sesion["rol"] == "vendedor"


def test_el_admin_tiene_todos_los_modulos(cliente_api, auth_admin):
    perfil = cliente_api.get("/auth/perfil", headers=auth_admin.headers).json()
    assert perfil["modulos"] == ["contabilidad", "rrhh", "ventas"]


def test_cuenta_de_contabilidad_entra_a_su_modulo(cliente_api, auth_admin):
    _, headers, _ = _cuenta(cliente_api, auth_admin.headers, "Conta", ["contabilidad"])

    assert cliente_api.get("/gastos/", headers=headers).status_code == 200
    assert cliente_api.get("/compras/", headers=headers).status_code == 200
    assert cliente_api.get("/proveedores/", headers=headers).status_code == 200
    assert cliente_api.get("/contabilidad/resumen", headers=headers).status_code == 200
    assert cliente_api.get("/reportes/margenes", headers=headers).status_code == 200


def test_cuenta_de_contabilidad_no_entra_a_ventas_ni_rrhh(cliente_api, auth_admin):
    _, headers, _ = _cuenta(cliente_api, auth_admin.headers, "Conta", ["contabilidad"])

    assert cliente_api.get("/ventas/", headers=headers).status_code == 403
    assert cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": 1, "cantidad": 1}]},
        headers=headers,
    ).status_code == 403
    assert cliente_api.get("/empleados/", headers=headers).status_code == 403


def test_cuenta_de_rrhh_entra_solo_a_rrhh(cliente_api, auth_admin):
    _, headers, _ = _cuenta(cliente_api, auth_admin.headers, "Rrhh", ["rrhh"])

    assert cliente_api.get("/empleados/", headers=headers).status_code == 200
    assert cliente_api.get("/empleados/nomina/tabla", headers=headers).status_code == 200
    assert cliente_api.get("/gastos/", headers=headers).status_code == 403
    assert cliente_api.get("/ventas/", headers=headers).status_code == 403


def test_cuenta_sin_modulos_queda_solo_en_ventas(cliente_api, auth_admin):
    """El fallback cubre las cuentas creadas antes de los módulos."""
    r = cliente_api.post(
        "/vendedores/",
        json={"nombre": "Viejo", "modulos": []},
        headers=auth_admin.headers,
    )
    assert r.status_code == 201, r.text
    creado = r.json()

    with SessionLocal() as session:
        v = session.query(Usuario).filter(Usuario.id == creado["id"]).first()
        v.modulos = None  # simula una fila anterior a la migración
        session.commit()

    login = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    assert login["modulos"] == ["ventas"]
    headers = {"Authorization": f"Bearer {login['token']}"}

    assert cliente_api.get("/ventas/", headers=headers).status_code == 200
    assert cliente_api.get("/gastos/", headers=headers).status_code == 403


def test_modulo_retirado_surte_efecto_sin_re_login(cliente_api, auth_admin):
    creado, headers, _ = _cuenta(
        cliente_api, auth_admin.headers, "Mixta", ["ventas", "contabilidad"]
    )
    assert cliente_api.get("/gastos/", headers=headers).status_code == 200

    # Se le quita contabilidad: el token sigue siendo válido, pero ya no pasa.
    r = cliente_api.put(
        f"/vendedores/{creado['id']}",
        json={"modulos": ["ventas"]},
        headers=auth_admin.headers,
    )
    assert r.status_code == 200, r.text

    assert cliente_api.get("/gastos/", headers=headers).status_code == 403
    assert cliente_api.get("/ventas/", headers=headers).status_code == 200


def test_modulo_invalido_es_rechazado(cliente_api, auth_admin):
    r = cliente_api.post(
        "/vendedores/",
        json={"nombre": "Malo", "modulos": ["inventado"]},
        headers=auth_admin.headers,
    )
    assert r.status_code == 422


def test_admin_sigue_siendo_el_unico_que_gestiona_cuentas(cliente_api, auth_admin):
    _, headers, _ = _cuenta(
        cliente_api, auth_admin.headers, "Conta", ["contabilidad", "rrhh", "ventas"]
    )
    assert cliente_api.get("/vendedores/", headers=headers).status_code == 403


def test_contabilidad_no_puede_anular_ventas(cliente_api, auth_admin):
    _, headers, _ = _cuenta(cliente_api, auth_admin.headers, "Conta", ["contabilidad"])
    # La ruta exige el módulo de ventas antes incluso de llegar al admin.
    assert cliente_api.delete("/ventas/1", headers=headers).status_code == 403


def test_inventario_se_ve_desde_contabilidad_y_ventas(cliente_api, auth_admin):
    producto = cliente_api.post(
        "/productos/", json={"nombre": "X", "precio": "10"}, headers=auth_admin.headers
    ).json()

    _, contable, _ = _cuenta(cliente_api, auth_admin.headers, "C", ["contabilidad"])
    _, vendedor, _ = _cuenta(cliente_api, auth_admin.headers, "V", ["ventas"])

    assert cliente_api.get("/productos/", headers=contable).status_code == 200
    assert cliente_api.get("/productos/", headers=vendedor).status_code == 200
    # Pero escribir el catálogo sigue siendo del dueño.
    assert cliente_api.put(
        f"/productos/{producto['id']}",
        json={"nombre": "Y", "precio": "10"},
        headers=contable,
    ).status_code == 403


def test_rrhh_no_puede_crear_una_cuenta_con_contabilidad(cliente_api, auth_admin):
    """Evita la escalada: RRHH solo concede los módulos que tiene."""
    _, headers, _ = _cuenta(cliente_api, auth_admin.headers, "SoloRrhh", ["rrhh"])

    r = cliente_api.post(
        "/empleados/",
        json={
            "nombre": "Intruso",
            "puesto": "Contador",
            "dar_acceso": True,
            "modulos": ["contabilidad"],
        },
        headers=headers,
    )
    assert r.status_code == 403
    assert "no tienes" in r.json()["detail"].lower()


def test_rrhh_si_puede_conceder_rrhh(cliente_api, auth_admin):
    _, headers, _ = _cuenta(cliente_api, auth_admin.headers, "SoloRrhh", ["rrhh"])

    r = cliente_api.post(
        "/empleados/",
        json={
            "nombre": "Ayudante",
            "puesto": "Asistente",
            "dar_acceso": True,
            "modulos": ["rrhh"],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["modulos"] == ["rrhh"]
