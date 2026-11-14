"""Nómina por API: salario en empleados/vendedores, resumen y simulador."""


def _empleado(client, headers, nombre="María", puesto="Limpiador", salario=0, **extra):
    return client.post(
        "/empleados/",
        json={"nombre": nombre, "puesto": puesto, "salario": salario, **extra},
        headers=headers,
    )


def test_guarda_salario_y_devuelve_nomina(cliente_api, auth_admin):
    r = _empleado(cliente_api, auth_admin.headers, salario=15000)
    assert r.status_code == 201, r.text
    datos = r.json()

    assert datos["salario"] == 15000.0
    assert datos["nomina"]["inss_laboral"] == 1050.0
    assert datos["nomina"]["ir_mensual"] == 842.5
    assert datos["nomina"]["salario_neto"] == 13107.5


def test_sin_salario_no_calcula_nomina(cliente_api, auth_admin):
    datos = _empleado(cliente_api, auth_admin.headers).json()
    assert datos["salario"] == 0.0
    assert datos["nomina"] is None


def test_salario_negativo_es_rechazado(cliente_api, auth_admin):
    r = _empleado(cliente_api, auth_admin.headers, salario=-100)
    assert r.status_code == 422


def test_editar_salario_recalcula(cliente_api, auth_admin):
    creado = _empleado(cliente_api, auth_admin.headers, salario=10000).json()

    r = cliente_api.put(
        f"/empleados/{creado['id']}",
        json={"nombre": "María", "puesto": "Limpiador", "salario": 35000},
        headers=auth_admin.headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["salario"] == 35000.0
    assert r.json()["nomina"]["ir_mensual"] == 4595.83


def test_resumen_de_planilla_en_el_listado(cliente_api, auth_admin):
    _empleado(cliente_api, auth_admin.headers, nombre="A", salario=15000)
    _empleado(cliente_api, auth_admin.headers, nombre="B", salario=35000)

    resumen = cliente_api.get("/empleados/", headers=auth_admin.headers).json()["resumen"]
    assert resumen["cantidad"] == 2
    assert resumen["total_bruto"] == 50000.0
    assert resumen["con_salario"] == 2
    assert resumen["sin_salario"] == 0
    assert resumen["total_inss_patronal"] == 10750.0
    assert resumen["total_inatec"] == 1000.0
    assert resumen["costo_empresa"] == 61750.0


def test_los_vendedores_entran_en_la_planilla(cliente_api, auth_admin):
    cliente_api.post(
        "/vendedores/",
        json={"nombre": "Ana", "salario": 15000},
        headers=auth_admin.headers,
    )

    datos = cliente_api.get("/empleados/", headers=auth_admin.headers).json()
    vendedor = next(i for i in datos["items"] if i["tipo"] == "vendedor")
    assert vendedor["salario"] == 15000.0
    assert vendedor["nomina"]["salario_neto"] == 13107.5
    assert datos["resumen"]["total_bruto"] == 15000.0


def test_empleados_inactivos_no_cuentan_en_la_planilla(cliente_api, auth_admin):
    activo = _empleado(cliente_api, auth_admin.headers, nombre="A", salario=10000).json()
    _empleado(cliente_api, auth_admin.headers, nombre="B", salario=20000, activo=False)

    resumen = cliente_api.get("/empleados/", headers=auth_admin.headers).json()["resumen"]
    assert resumen["cantidad"] == 1
    assert resumen["total_bruto"] == 10000.0
    assert activo["activo"] is True


def test_simulador_no_guarda_nada(cliente_api, auth_admin):
    r = cliente_api.post(
        "/empleados/nomina/simular",
        json={"salario": 35000, "empleados_empresa": 60},
        headers=auth_admin.headers,
    )
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["ir_mensual"] == 4595.83
    # 60 trabajadores → tasa patronal del 22.50 %
    assert datos["parametros"]["inss_patronal_pct"] == 22.5
    assert datos["aguinaldo_anual"] == 35000.0

    assert cliente_api.get("/empleados/", headers=auth_admin.headers).json()["total"] == 0


def test_tabla_fiscal_expone_los_parametros(cliente_api, auth_admin):
    r = cliente_api.get("/empleados/nomina/tabla", headers=auth_admin.headers)
    assert r.status_code == 200, r.text
    datos = r.json()

    assert datos["inss_laboral"] == 7.0
    assert datos["inss_patronal"] == 21.5
    assert datos["inss_patronal_grande"] == 22.5
    assert datos["inatec"] == 2.0
    assert len(datos["tramos_ir"]) == 5
    assert datos["tramos_ir"][1]["tasa"] == 15.0
    assert "Ley 822" in datos["version"]


def test_la_ruta_nomina_no_se_confunde_con_un_id(cliente_api, auth_admin):
    """/nomina/tabla debe resolverse antes que /empleados/{id}."""
    assert cliente_api.get(
        "/empleados/nomina/tabla", headers=auth_admin.headers
    ).status_code == 200


def test_vendedor_no_accede_a_la_nomina(cliente_api, auth_admin):
    creado = cliente_api.post(
        "/vendedores/", json={"nombre": "V"}, headers=auth_admin.headers
    ).json()
    login = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}

    assert cliente_api.get("/empleados/nomina/tabla", headers=headers).status_code == 403
    assert cliente_api.post(
        "/empleados/nomina/simular", json={"salario": 1000}, headers=headers
    ).status_code == 403
