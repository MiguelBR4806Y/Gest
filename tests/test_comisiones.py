"""Comisiones sobre ventas y registro de vacaciones por API."""

from datetime import date, timedelta

from Backend.tiempo import hoy_local


def _producto(client, headers, precio="100", stock=50):
    return client.post(
        "/productos/",
        json={"nombre": "Producto", "stock": stock, "precio": precio},
        headers=headers,
    ).json()


def _vendedor(client, admin_headers, nombre="Ana", comision=0, **extra):
    r = client.post(
        "/vendedores/",
        json={"nombre": nombre, "comision_pct": comision, **extra},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    creado = r.json()
    login = client.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    return creado, {"Authorization": f"Bearer {login['token']}"}


def _vender(client, headers, producto_id, cantidad=1):
    r = client.post(
        "/ventas/",
        json={
            "metodo_pago": "efectivo",
            "items": [{"producto_id": producto_id, "cantidad": cantidad}],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_comision_es_el_porcentaje_de_las_ventas(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    creado, headers = _vendedor(cliente_api, auth_admin.headers, comision=10)
    _vender(cliente_api, headers, p["id"], cantidad=10)  # 1 000 en ventas

    resumen = cliente_api.get(
        f"/empleados/resumen-pago?persona_tipo=cuenta&persona_id={creado['id']}",
        headers=auth_admin.headers,
    ).json()

    assert resumen["comision"]["ventas"] == 1000.0
    assert resumen["comision"]["comision_pct"] == 10.0
    assert resumen["comision"]["comision"] == 100.0


def test_sin_comision_configurada_no_suma(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    creado, headers = _vendedor(cliente_api, auth_admin.headers)
    _vender(cliente_api, headers, p["id"], cantidad=5)

    resumen = cliente_api.get(
        f"/empleados/resumen-pago?persona_tipo=cuenta&persona_id={creado['id']}",
        headers=auth_admin.headers,
    ).json()
    assert resumen["comision"]["comision"] == 0.0


def test_cambiar_el_porcentaje_recalcula(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    creado, headers = _vendedor(cliente_api, auth_admin.headers, comision=5)
    _vender(cliente_api, headers, p["id"], cantidad=10)

    cliente_api.put(
        f"/vendedores/{creado['id']}",
        json={"comision_pct": 20},
        headers=auth_admin.headers,
    )

    resumen = cliente_api.get(
        f"/empleados/resumen-pago?persona_tipo=cuenta&persona_id={creado['id']}",
        headers=auth_admin.headers,
    ).json()
    assert resumen["comision"]["comision"] == 200.0


def test_las_ventas_anuladas_no_comisionan(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    creado, headers = _vendedor(cliente_api, auth_admin.headers, comision=10)
    venta = _vender(cliente_api, headers, p["id"], cantidad=4)

    cliente_api.delete(f"/ventas/{venta['id']}", headers=auth_admin.headers)

    resumen = cliente_api.get(
        f"/empleados/resumen-pago?persona_tipo=cuenta&persona_id={creado['id']}",
        headers=auth_admin.headers,
    ).json()
    assert resumen["comision"]["ventas"] == 0.0
    assert resumen["comision"]["comision"] == 0.0


def test_solo_cuenta_al_vendedor_de_la_venta(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    _, headers_a = _vendedor(cliente_api, auth_admin.headers, nombre="Ana", comision=10)
    creado_b, _headers_b = _vendedor(cliente_api, auth_admin.headers, nombre="Beto", comision=10)

    _vender(cliente_api, headers_a, p["id"], cantidad=3)

    resumen_b = cliente_api.get(
        f"/empleados/resumen-pago?persona_tipo=cuenta&persona_id={creado_b['id']}",
        headers=auth_admin.headers,
    ).json()
    assert resumen_b["comision"]["ventas"] == 0.0


def test_comision_se_suma_al_bruto_y_paga_inss(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    creado, headers = _vendedor(
        cliente_api, auth_admin.headers, comision=10, salario=12000
    )
    _vender(cliente_api, headers, p["id"], cantidad=10)

    resumen = cliente_api.get(
        f"/empleados/resumen-pago?persona_tipo=cuenta&persona_id={creado['id']}",
        headers=auth_admin.headers,
    ).json()

    assert resumen["nomina"]["salario_base"] == 12000.0
    assert resumen["nomina"]["salario_bruto"] == 12100.0
    assert resumen["nomina"]["inss_laboral"] == 847.0  # 7 % de 12 100
    assert resumen["nomina"]["extra_total"] == 100.0


def test_porcentaje_fuera_de_rango_es_rechazado(cliente_api, auth_admin):
    r = cliente_api.post(
        "/vendedores/",
        json={"nombre": "Malo", "comision_pct": 150},
        headers=auth_admin.headers,
    )
    assert r.status_code == 422


# ── Vacaciones por API ──


def _empleado(client, headers, nombre="Limpieza", salario=12000, ingreso=None):
    return client.post(
        "/empleados/",
        json={
            "nombre": nombre,
            "puesto": "Limpiador",
            "salario": salario,
            "fecha_ingreso": (
                ingreso or (date.today() - timedelta(days=365)).isoformat()
            ),
        },
        headers=headers,
    ).json()


def _registrar(client, headers, persona_id, dias, tipo="empleado", **extra):
    hoy = hoy_local("America/Managua")
    return client.post(
        "/empleados/vacaciones",
        json={
            "persona_tipo": tipo,
            "persona_id": persona_id,
            "fecha_inicio": hoy.isoformat(),
            "fecha_fin": (hoy + timedelta(days=dias - 1)).isoformat(),
            "dias": dias,
            **extra,
        },
        headers=headers,
    )


def test_registrar_vacaciones_descuenta_del_saldo(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)  # 1 año → 30 días

    r = _registrar(cliente_api, auth_admin.headers, e["id"], 5)
    assert r.status_code == 201, r.text
    assert r.json()["saldo"]["dias_disponibles"] == 25.0

    lista = cliente_api.get(
        f"/empleados/vacaciones?persona_tipo=empleado&persona_id={e['id']}",
        headers=auth_admin.headers,
    ).json()
    assert lista["total_dias"] == 5
    assert lista["saldo"]["dias_disponibles"] == 25.0


def test_no_permite_mas_dias_que_el_saldo(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)
    r = _registrar(cliente_api, auth_admin.headers, e["id"], 40)
    assert r.status_code == 409
    assert "saldo" in r.json()["detail"].lower()


def test_fecha_fin_anterior_es_rechazada(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)
    hoy = hoy_local("America/Managua")
    r = cliente_api.post(
        "/empleados/vacaciones",
        json={
            "persona_tipo": "empleado",
            "persona_id": e["id"],
            "fecha_inicio": hoy.isoformat(),
            "fecha_fin": (hoy - timedelta(days=5)).isoformat(),
            "dias": 3,
        },
        headers=auth_admin.headers,
    )
    assert r.status_code == 422


def test_eliminar_registro_devuelve_el_saldo(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)
    registro = _registrar(cliente_api, auth_admin.headers, e["id"], 5).json()

    assert cliente_api.delete(
        f"/empleados/vacaciones/{registro['id']}", headers=auth_admin.headers
    ).status_code == 200

    lista = cliente_api.get(
        f"/empleados/vacaciones?persona_tipo=empleado&persona_id={e['id']}",
        headers=auth_admin.headers,
    ).json()
    assert lista["total_dias"] == 0
    assert lista["saldo"]["dias_disponibles"] == 30.0


def test_vacaciones_de_persona_ajena_es_404(cliente_api, auth_admin, crear_usuario):
    otro = crear_usuario(usuario="ajeno", rol="admin")
    headers_otro = {"Authorization": f"Bearer {otro['token']}"}
    ajeno = _empleado(cliente_api, headers_otro, nombre="Ajeno")

    assert _registrar(
        cliente_api, auth_admin.headers, ajeno["id"], 2
    ).status_code == 404


def test_el_listado_incluye_comision_y_vacaciones(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    creado, headers = _vendedor(
        cliente_api, auth_admin.headers, comision=10, salario=12000
    )
    _vender(cliente_api, headers, p["id"], cantidad=10)

    item = cliente_api.get("/empleados/", headers=auth_admin.headers).json()["items"][0]
    assert item["comision_pct"] == 10.0
    assert item["comision"]["comision"] == 100.0
    assert item["nomina"]["salario_base"] == 12000.0
    assert item["nomina"]["salario_bruto"] == 12100.0
    assert "vacaciones" in item
