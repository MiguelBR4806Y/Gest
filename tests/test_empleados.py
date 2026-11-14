"""Empleados: vendedores automáticos + personal sin cuenta."""


def _crear(client, headers, nombre="María López", puesto="Limpiador", **extra):
    return client.post(
        "/empleados/",
        json={"nombre": nombre, "puesto": puesto, **extra},
        headers=headers,
    )


def test_listado_vacio(cliente_api, auth_admin):
    r = cliente_api.get("/empleados/", headers=auth_admin.headers)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["items"] == []
    assert datos["total"] == 0
    assert datos["con_acceso"] == 0
    assert datos["sin_acceso"] == 0
    assert datos["resumen"]["cantidad"] == 0
    assert datos["resumen"]["costo_empresa"] == 0.0


def test_registra_personal_sin_cuenta(cliente_api, auth_admin):
    r = _crear(cliente_api, auth_admin.headers, telefono="8888-1234", notas="Mañanas")
    assert r.status_code == 201, r.text
    creado = r.json()
    assert creado["puesto"] == "Limpiador"
    assert creado["con_acceso"] is False
    assert creado["tipo"] == "personal"
    assert creado["activo"] is True


def test_los_vendedores_aparecen_automaticamente(cliente_api, auth_admin):
    creado = cliente_api.post(
        "/vendedores/",
        json={"nombre": "Ana Pérez", "puesto": "Cajera"},
        headers=auth_admin.headers,
    ).json()

    datos = cliente_api.get("/empleados/", headers=auth_admin.headers).json()
    assert datos["total"] == 1
    assert datos["con_acceso"] == 1
    assert datos["sin_acceso"] == 0

    vendedor = datos["items"][0]
    assert vendedor["tipo"] == "vendedor"
    assert vendedor["con_acceso"] is True
    assert vendedor["usuario"] == creado["usuario"]
    assert vendedor["puesto"] == "Cajera"


def test_vendedor_sin_puesto_usa_el_valor_por_defecto(cliente_api, auth_admin):
    cliente_api.post(
        "/vendedores/", json={"nombre": "Beto Ruiz"}, headers=auth_admin.headers
    )
    datos = cliente_api.get("/empleados/", headers=auth_admin.headers).json()
    assert datos["items"][0]["puesto"] == "Vendedor"


def test_listado_combina_ambos_y_cuenta(cliente_api, auth_admin):
    cliente_api.post(
        "/vendedores/", json={"nombre": "Vendedor Uno"}, headers=auth_admin.headers
    )
    _crear(cliente_api, auth_admin.headers, nombre="Guarda", puesto="Seguridad")

    datos = cliente_api.get("/empleados/", headers=auth_admin.headers).json()
    assert datos["total"] == 2
    assert datos["con_acceso"] == 1
    assert datos["sin_acceso"] == 1
    assert {i["tipo"] for i in datos["items"]} == {"vendedor", "personal"}


def test_editar_y_eliminar_personal(cliente_api, auth_admin):
    creado = _crear(cliente_api, auth_admin.headers).json()

    r = cliente_api.put(
        f"/empleados/{creado['id']}",
        json={"nombre": "María L.", "puesto": "Limpieza", "activo": False},
        headers=auth_admin.headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "María L."
    assert r.json()["puesto"] == "Limpieza"
    assert r.json()["activo"] is False

    assert cliente_api.delete(
        f"/empleados/{creado['id']}", headers=auth_admin.headers
    ).status_code == 200
    assert cliente_api.get("/empleados/", headers=auth_admin.headers).json()["total"] == 0


def test_no_edita_un_vendedor_desde_empleados(cliente_api, auth_admin):
    creado = cliente_api.post(
        "/vendedores/", json={"nombre": "Carla"}, headers=auth_admin.headers
    ).json()

    r = cliente_api.put(
        f"/empleados/{creado['id']}",
        json={"nombre": "Otro", "puesto": "Otro"},
        headers=auth_admin.headers,
    )
    assert r.status_code == 404


def test_puesto_obligatorio(cliente_api, auth_admin):
    r = cliente_api.post(
        "/empleados/", json={"nombre": "Sin puesto"}, headers=auth_admin.headers
    )
    assert r.status_code == 422


def test_telefono_invalido_es_rechazado(cliente_api, auth_admin):
    r = _crear(cliente_api, auth_admin.headers, telefono="abc-def")
    assert r.status_code == 422


def test_aislamiento_entre_negocios(cliente_api, auth_admin, crear_usuario):
    creado = _crear(cliente_api, auth_admin.headers).json()

    otro = crear_usuario(usuario="ajeno", rol="admin")
    headers = {"Authorization": f"Bearer {otro['token']}"}

    assert cliente_api.get("/empleados/", headers=headers).json()["total"] == 0
    assert cliente_api.delete(
        f"/empleados/{creado['id']}", headers=headers
    ).status_code == 404


def test_vendedor_no_accede_a_empleados(cliente_api, auth_admin):
    creado = cliente_api.post(
        "/vendedores/", json={"nombre": "Vendedor Empleado"}, headers=auth_admin.headers
    ).json()
    login = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}

    assert cliente_api.get("/empleados/", headers=headers).status_code == 403
    assert _crear(cliente_api, headers).status_code == 403


def test_borrar_la_cuenta_borra_el_personal(cliente_api, crear_usuario):
    admin = crear_usuario(usuario="dueno_emp", password="Segura123", rol="admin")
    headers = {"Authorization": f"Bearer {admin['token']}"}

    _crear(cliente_api, headers)
    assert cliente_api.get("/empleados/", headers=headers).json()["total"] == 1

    r = cliente_api.request(
        "DELETE", "/auth/cuenta", json={"password": "Segura123"}, headers=headers
    )
    assert r.status_code == 200, r.text


# ── Empleado con acceso al sistema ──


def _con_acceso(client, headers, nombre="Ana", puesto="Contador", modulos=None, **extra):
    if modulos is None:
        modulos = ["contabilidad"]
    return client.post(
        "/empleados/",
        json={
            "nombre": nombre,
            "puesto": puesto,
            "dar_acceso": True,
            "modulos": modulos,
            **extra,
        },
        headers=headers,
    )


def test_empleado_con_acceso_crea_cuenta_y_credenciales(cliente_api, auth_admin):
    r = _con_acceso(cliente_api, auth_admin.headers, modulos=["contabilidad"])
    assert r.status_code == 201, r.text
    datos = r.json()

    assert datos["con_acceso"] is True
    assert datos["tipo"] == "vendedor"
    assert datos["modulos"] == ["contabilidad"]
    assert datos["credenciales"]["usuario"]
    assert datos["credenciales"]["password"]

    login = cliente_api.post(
        "/auth/login",
        json={
            "usuario": datos["credenciales"]["usuario"],
            "password": datos["credenciales"]["password"],
        },
    )
    assert login.status_code == 200, login.text
    assert login.json()["modulos"] == ["contabilidad"]


def test_empleado_sin_acceso_no_crea_usuario(cliente_api, auth_admin):
    r = _crear(cliente_api, auth_admin.headers)
    assert r.status_code == 201
    datos = r.json()
    assert datos["con_acceso"] is False
    assert "credenciales" not in datos

    assert cliente_api.get("/empleados/", headers=auth_admin.headers).json()["con_acceso"] == 0


def test_dar_acceso_sin_modulos_es_400(cliente_api, auth_admin):
    r = _con_acceso(cliente_api, auth_admin.headers, modulos=[])
    assert r.status_code == 400
    assert "módulo" in r.json()["detail"]


def test_acceso_con_modulo_invalido_es_rechazado(cliente_api, auth_admin):
    r = _con_acceso(cliente_api, auth_admin.headers, modulos=["inventado"])
    assert r.status_code == 422


def test_empleado_con_acceso_cuenta_para_el_limite(cliente_api, auth_admin):
    from Backend.routers.empleados import MAX_CUENTAS

    for i in range(MAX_CUENTAS):
        r = _con_acceso(
            cliente_api, auth_admin.headers, nombre=f"Persona {i}", modulos=["ventas"]
        )
        assert r.status_code == 201, r.text

    r = _con_acceso(cliente_api, auth_admin.headers, nombre="Sobrante", modulos=["ventas"])
    assert r.status_code == 409
    assert "Límite" in r.json()["detail"]


def test_limite_se_comparte_entre_vendedores_y_empleados(cliente_api, auth_admin):
    from Backend.routers.empleados import MAX_CUENTAS

    for i in range(MAX_CUENTAS - 1):
        cliente_api.post(
            "/vendedores/", json={"nombre": f"V{i}"}, headers=auth_admin.headers
        )

    assert _con_acceso(
        cliente_api, auth_admin.headers, nombre="Ultima", modulos=["ventas"]
    ).status_code == 201

    assert cliente_api.post(
        "/vendedores/", json={"nombre": "Extra"}, headers=auth_admin.headers
    ).status_code == 409


def test_el_personal_sin_acceso_no_cuenta_para_el_limite(cliente_api, auth_admin):
    from Backend.routers.empleados import MAX_CUENTAS

    for i in range(MAX_CUENTAS + 2):
        assert _crear(cliente_api, auth_admin.headers, nombre=f"Limpieza {i}").status_code == 201

    assert _con_acceso(
        cliente_api, auth_admin.headers, nombre="Primera cuenta", modulos=["ventas"]
    ).status_code == 201


def test_exportar_planilla(cliente_api, auth_admin):
    _crear(cliente_api, auth_admin.headers, nombre="Limpieza", salario=12000)
    cliente_api.post(
        "/vendedores/",
        json={"nombre": "Vendedor", "salario": 35000},
        headers=auth_admin.headers,
    )

    r = cliente_api.get("/empleados/exportar", headers=auth_admin.headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]

    texto = r.content.decode("utf-8-sig")
    assert texto.startswith("Nombre;Puesto;Salario base C$")
    assert "Comisión %" in texto and "Vacaciones días" in texto
    assert "Limpieza" in texto and "Vendedor" in texto
    assert "TOTAL" in texto
    assert "2 personas" in texto


def test_rrhh_no_gestiona_las_credenciales(cliente_api, auth_admin):
    """Crear cuentas queda en Vendedores; RRHH solo registra y concede su alcance."""
    _, headers, _ = _crear_cuenta_rrhh(cliente_api, auth_admin.headers)
    assert cliente_api.get("/vendedores/", headers=headers).status_code == 403


def _crear_cuenta_rrhh(client, admin_headers):
    r = client.post(
        "/vendedores/",
        json={"nombre": "SoloRrhh", "modulos": ["rrhh"]},
        headers=admin_headers,
    )
    creado = r.json()
    login = client.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    return creado, {"Authorization": f"Bearer {login['token']}"}, login
