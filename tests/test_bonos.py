"""Bonos: CRUD, recurrencia y efecto en la planilla del periodo."""

from datetime import date

from Backend.tiempo import hoy_local


def _empleado(client, headers, nombre="Limpieza", salario=12000, **extra):
    r = client.post(
        "/empleados/",
        json={"nombre": nombre, "puesto": "Limpiador", "salario": salario, **extra},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _bono(client, headers, persona_id, monto="1000", fecha=None, tipo="empleado", **extra):
    return client.post(
        "/empleados/bonos",
        json={
            "persona_tipo": tipo,
            "persona_id": persona_id,
            "concepto": extra.pop("concepto", "Bono de productividad"),
            "monto": monto,
            "fecha": (fecha or hoy_local("America/Managua").isoformat()),
            **extra,
        },
        headers=headers,
    )


def test_crear_y_listar_bono(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)
    r = _bono(cliente_api, auth_admin.headers, e["id"], monto="1500")
    assert r.status_code == 201, r.text
    creado = r.json()
    assert creado["monto"] == 1500.0
    assert creado["recurrente"] is False

    lista = cliente_api.get(
        f"/empleados/bonos?persona_tipo=empleado&persona_id={e['id']}",
        headers=auth_admin.headers,
    ).json()
    assert lista["total"] == 1500.0
    assert len(lista["items"]) == 1


def test_bono_de_persona_ajena_es_404(cliente_api, auth_admin, crear_usuario):
    otro = crear_usuario(usuario="ajeno", rol="admin")
    ajeno = _empleado(
        cliente_api, {"Authorization": f"Bearer {otro['token']}"}, nombre="Ajeno"
    )

    r = _bono(cliente_api, auth_admin.headers, ajeno["id"])
    assert r.status_code == 404


def test_monto_negativo_es_rechazado(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)
    assert _bono(cliente_api, auth_admin.headers, e["id"], monto="-1").status_code == 422


def test_concepto_obligatorio(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)
    r = _bono(cliente_api, auth_admin.headers, e["id"], concepto="")
    assert r.status_code == 422


def test_editar_y_eliminar(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)
    bono = _bono(cliente_api, auth_admin.headers, e["id"], monto="500").json()

    hoy = hoy_local("America/Managua").isoformat()
    r = cliente_api.put(
        f"/empleados/bonos/{bono['id']}",
        json={
            "persona_tipo": "empleado",
            "persona_id": e["id"],
            "concepto": "Bono corregido",
            "monto": 900,
            "fecha": hoy,
            "recurrente": True,
        },
        headers=auth_admin.headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["monto"] == 900.0
    assert r.json()["recurrente"] is True

    assert cliente_api.delete(
        f"/empleados/bonos/{bono['id']}", headers=auth_admin.headers
    ).status_code == 200
    assert cliente_api.get("/empleados/bonos", headers=auth_admin.headers).json()["items"] == []


def test_el_bono_entra_en_la_nomina_del_mes(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers, salario=12000)
    _bono(cliente_api, auth_admin.headers, e["id"], monto="1000")

    resumen = cliente_api.get(
        f"/empleados/resumen-pago?persona_tipo=empleado&persona_id={e['id']}",
        headers=auth_admin.headers,
    ).json()

    assert resumen["bonos"] == 1000.0
    assert resumen["nomina"]["salario_base"] == 12000.0
    assert resumen["nomina"]["salario_bruto"] == 13000.0
    # El INSS sube con el extra: 7 % de 13 000.
    assert resumen["nomina"]["inss_laboral"] == 910.0


def test_bono_recurrente_cuenta_en_meses_posteriores(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)
    _bono(
        cliente_api, auth_admin.headers, e["id"], monto="500",
        fecha="2026-01-15", recurrente=True,
    )

    # Un mes muy posterior sigue recibiendo el bono.
    resumen = cliente_api.get(
        f"/empleados/resumen-pago?persona_tipo=empleado&persona_id={e['id']}"
        "&desde=2026-06-01&hasta=2026-06-30",
        headers=auth_admin.headers,
    ).json()
    assert resumen["bonos"] == 500.0


def test_bono_puntual_no_cuenta_fuera_de_su_mes(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)
    _bono(cliente_api, auth_admin.headers, e["id"], monto="500", fecha="2026-01-15")

    resumen = cliente_api.get(
        f"/empleados/resumen-pago?persona_tipo=empleado&persona_id={e['id']}"
        "&desde=2026-06-01&hasta=2026-06-30",
        headers=auth_admin.headers,
    ).json()
    assert resumen["bonos"] == 0.0


def test_filtro_por_rango_de_fechas(cliente_api, auth_admin):
    e = _empleado(cliente_api, auth_admin.headers)
    _bono(cliente_api, auth_admin.headers, e["id"], monto="100", fecha="2026-02-10")
    _bono(cliente_api, auth_admin.headers, e["id"], monto="200", fecha="2026-05-10")

    lista = cliente_api.get(
        "/empleados/bonos?desde=2026-05-01&hasta=2026-05-31",
        headers=auth_admin.headers,
    ).json()
    assert lista["total"] == 200.0
    assert len(lista["items"]) == 1


def test_aislamiento_entre_negocios(cliente_api, auth_admin, crear_usuario):
    e = _empleado(cliente_api, auth_admin.headers)
    _bono(cliente_api, auth_admin.headers, e["id"])

    otro = crear_usuario(usuario="ajeno", rol="admin")
    headers = {"Authorization": f"Bearer {otro['token']}"}
    assert cliente_api.get("/empleados/bonos", headers=headers).json()["items"] == []


def test_un_vendedor_no_ve_bonos(cliente_api, auth_admin):
    creado = cliente_api.post(
        "/vendedores/", json={"nombre": "V"}, headers=auth_admin.headers
    ).json()
    login = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}

    assert cliente_api.get("/empleados/bonos", headers=headers).status_code == 403


def test_la_fecha_de_ingreso_alimenta_las_vacaciones(cliente_api, auth_admin):
    _empleado(
        cliente_api, auth_admin.headers,
        fecha_ingreso=(date.today().replace(year=date.today().year - 1)).isoformat(),
    )
    item = cliente_api.get("/empleados/", headers=auth_admin.headers).json()["items"][0]
    assert item["vacaciones"]["configurado"] is True
    assert item["vacaciones"]["dias_devengados"] == 30.0
