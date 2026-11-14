"""Módulo de contabilidad: resumen, serie y CSV."""

from Backend.tiempo import hoy_local


def _producto(client, headers, nombre="Producto", stock=0, precio="100", costo="40"):
    return client.post(
        "/productos/",
        json={"nombre": nombre, "stock": stock, "precio": precio, "costo": costo},
        headers=headers,
    ).json()


def _vender(client, headers, producto_id, cantidad=1):
    r = client.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": producto_id, "cantidad": cantidad}]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _gasto(client, headers, concepto="Alquiler", monto="500", categoria="alquiler"):
    r = client.post(
        "/gastos/",
        json={"concepto": concepto, "categoria": categoria, "monto": monto},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_resumen_vacio_da_ceros(cliente_api, auth_admin):
    r = cliente_api.get("/contabilidad/resumen", headers=auth_admin.headers)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["ingresos"] == 0.0
    assert datos["costo_ventas"] == 0.0
    assert datos["gastos"] == 0.0
    assert datos["utilidad"] == 0.0
    assert datos["margen_pct"] == 0.0


def test_utilidad_es_ingresos_menos_costo_menos_gastos(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, stock=10, precio="100", costo="40")
    _vender(cliente_api, auth_admin.headers, p["id"], 2)  # 200 ingreso, 80 costo
    _gasto(cliente_api, auth_admin.headers, monto="50")

    hoy = hoy_local("America/Managua").isoformat()
    datos = cliente_api.get(
        f"/contabilidad/resumen?desde={hoy}&hasta={hoy}", headers=auth_admin.headers
    ).json()

    assert datos["ingresos"] == 200.0
    assert datos["costo_ventas"] == 80.0
    assert datos["ganancia_bruta"] == 120.0
    assert datos["gastos"] == 50.0
    assert datos["utilidad"] == 70.0
    assert datos["numero_ventas"] == 1
    assert datos["numero_gastos"] == 1
    assert round(datos["margen_pct"], 2) == 35.0


def test_la_compra_entra_como_gasto_pero_no_duplica(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers)
    r = cliente_api.post(
        "/compras/",
        json={"items": [{"producto_id": p["id"], "cantidad": 2, "costo_unitario": "30"}]},
        headers=auth_admin.headers,
    )
    assert r.status_code == 201, r.text

    hoy = hoy_local("America/Managua").isoformat()
    datos = cliente_api.get(
        f"/contabilidad/resumen?desde={hoy}&hasta={hoy}", headers=auth_admin.headers
    ).json()
    # La compra genera un único gasto de 60.
    assert datos["gastos"] == 60.0
    assert datos["numero_gastos"] == 1


def test_las_ventas_anuladas_no_cuentan(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, stock=5, precio="100", costo="40")
    venta = _vender(cliente_api, auth_admin.headers, p["id"], 1)
    cliente_api.delete(f"/ventas/{venta['id']}", headers=auth_admin.headers)

    hoy = hoy_local("America/Managua").isoformat()
    datos = cliente_api.get(
        f"/contabilidad/resumen?desde={hoy}&hasta={hoy}", headers=auth_admin.headers
    ).json()
    assert datos["ingresos"] == 0.0
    assert datos["costo_ventas"] == 0.0


def test_gastos_por_categoria(cliente_api, auth_admin):
    _gasto(cliente_api, auth_admin.headers, "A", "100", "servicios")
    _gasto(cliente_api, auth_admin.headers, "B", "300", "alquiler")

    hoy = hoy_local("America/Managua").isoformat()
    datos = cliente_api.get(
        f"/contabilidad/resumen?desde={hoy}&hasta={hoy}", headers=auth_admin.headers
    ).json()
    categorias = {c["categoria"]: c["total"] for c in datos["gastos_por_categoria"]}
    assert categorias == {"alquiler": 300.0, "servicios": 100.0}


def test_serie_por_dia(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, stock=5, precio="100", costo="40")
    _vender(cliente_api, auth_admin.headers, p["id"], 1)
    _gasto(cliente_api, auth_admin.headers, monto="25")

    hoy = hoy_local("America/Managua").isoformat()
    datos = cliente_api.get(
        f"/contabilidad/serie?desde={hoy}&hasta={hoy}&agrupacion=dia",
        headers=auth_admin.headers,
    ).json()
    assert datos["agrupacion"] == "dia"
    assert len(datos["puntos"]) == 1
    punto = datos["puntos"][0]
    assert punto["ingresos"] == 100.0
    assert punto["gastos"] == 25.0
    assert punto["utilidad"] == 35.0  # 100 - 40 costo - 25 gasto


def test_fechas_invertidas_son_400(cliente_api, auth_admin):
    r = cliente_api.get(
        "/contabilidad/resumen?desde=2026-05-10&hasta=2026-05-01",
        headers=auth_admin.headers,
    )
    assert r.status_code == 400


def test_exportar_devuelve_csv_con_totales(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, stock=5, precio="100", costo="40")
    _vender(cliente_api, auth_admin.headers, p["id"], 1)
    _gasto(cliente_api, auth_admin.headers, monto="10")

    hoy = hoy_local("America/Managua").isoformat()
    r = cliente_api.get(
        f"/contabilidad/exportar?desde={hoy}&hasta={hoy}", headers=auth_admin.headers
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    texto = r.content.decode("utf-8-sig")
    assert texto.startswith("Tipo;Referencia;Fecha;Detalle")
    assert "Venta" in texto and "Gasto" in texto
    assert "TOTAL" in texto


def test_resumen_aislado_por_negocio(cliente_api, auth_admin, crear_usuario):
    p = _producto(cliente_api, auth_admin.headers, stock=5, precio="100", costo="40")
    _vender(cliente_api, auth_admin.headers, p["id"], 1)

    otro = crear_usuario(usuario="ajeno", rol="admin")
    datos = cliente_api.get(
        "/contabilidad/resumen", headers={"Authorization": f"Bearer {otro['token']}"}
    ).json()
    assert datos["ingresos"] == 0.0


def test_un_vendedor_no_entra_a_contabilidad(cliente_api, auth_admin):
    creado = cliente_api.post(
        "/vendedores/", json={"nombre": "V"}, headers=auth_admin.headers
    ).json()
    login = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}

    assert cliente_api.get("/contabilidad/resumen", headers=headers).status_code == 403
    assert cliente_api.get("/contabilidad/serie", headers=headers).status_code == 403
    assert cliente_api.get("/contabilidad/exportar", headers=headers).status_code == 403
