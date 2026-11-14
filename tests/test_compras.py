"""Compras a proveedor: stock, costo promedio y gasto vinculado."""


def _producto(client, headers, nombre="Harina", stock=0, precio="20", costo="0"):
    r = client.post(
        "/productos/",
        json={"nombre": nombre, "stock": stock, "precio": precio, "costo": costo},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _proveedor(client, headers, nombre="Distribuidora La Unión"):
    r = client.post("/proveedores/", json={"nombre": nombre}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_compra_sube_stock_y_calcula_costo_promedio(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, stock=0, costo="10")
    proveedor = _proveedor(cliente_api, auth_admin.headers)

    r = cliente_api.post(
        "/compras/",
        json={
            "proveedor_id": proveedor["id"],
            "items": [{"producto_id": p["id"], "cantidad": 10, "costo_unitario": "5"}],
        },
        headers=auth_admin.headers,
    )
    assert r.status_code == 201, r.text
    compra = r.json()
    assert compra["total"] == 50.0
    assert compra["numero"] == f"C-{compra['id']:06d}"
    assert compra["items"][0]["subtotal"] == 50.0

    actual = cliente_api.get(f"/productos/{p['id']}", headers=auth_admin.headers).json()
    assert actual["stock"] == 10
    # (10 * 0 + 5 * 10) / 10 = 5
    assert actual["costo"] == 5.0


def test_segunda_compra_pondera_el_costo(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, stock=10, costo="5")

    r = cliente_api.post(
        "/compras/",
        json={"items": [{"producto_id": p["id"], "cantidad": 10, "costo_unitario": "15"}]},
        headers=auth_admin.headers,
    )
    assert r.status_code == 201, r.text

    actual = cliente_api.get(f"/productos/{p['id']}", headers=auth_admin.headers).json()
    assert actual["stock"] == 20
    # (5 * 10 + 15 * 10) / 20 = 10
    assert actual["costo"] == 10.0


def test_lineas_repetidas_se_agrupan_antes_de_ponderar(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, stock=0, costo="0")

    r = cliente_api.post(
        "/compras/",
        json={
            "items": [
                {"producto_id": p["id"], "cantidad": 5, "costo_unitario": "10"},
                {"producto_id": p["id"], "cantidad": 5, "costo_unitario": "20"},
            ]
        },
        headers=auth_admin.headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["total"] == 150.0

    actual = cliente_api.get(f"/productos/{p['id']}", headers=auth_admin.headers).json()
    assert actual["stock"] == 10
    assert actual["costo"] == 15.0


def test_la_compra_genera_un_gasto_vinculado(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers)
    proveedor = _proveedor(cliente_api, auth_admin.headers)

    compra = cliente_api.post(
        "/compras/",
        json={
            "proveedor_id": proveedor["id"],
            "items": [{"producto_id": p["id"], "cantidad": 4, "costo_unitario": "25"}],
        },
        headers=auth_admin.headers,
    ).json()

    gastos = cliente_api.get("/gastos/", headers=auth_admin.headers).json()
    assert gastos["total"] == 100.0
    assert len(gastos["items"]) == 1
    gasto = gastos["items"][0]
    assert gasto["compra_id"] == compra["id"]
    assert gasto["categoria"] == "compra"
    assert gasto["proveedor_nombre"] == proveedor["nombre"]


def test_el_gasto_de_una_compra_no_se_edita_a_mano(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers)
    cliente_api.post(
        "/compras/",
        json={"items": [{"producto_id": p["id"], "cantidad": 1, "costo_unitario": "10"}]},
        headers=auth_admin.headers,
    )
    gasto = cliente_api.get("/gastos/", headers=auth_admin.headers).json()["items"][0]

    assert cliente_api.put(
        f"/gastos/{gasto['id']}", json={"concepto": "X", "monto": "1"},
        headers=auth_admin.headers,
    ).status_code == 409
    assert cliente_api.delete(
        f"/gastos/{gasto['id']}", headers=auth_admin.headers
    ).status_code == 409


def test_anular_compra_revierte_el_stock(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, stock=2, costo="10")
    compra = cliente_api.post(
        "/compras/",
        json={"items": [{"producto_id": p["id"], "cantidad": 5, "costo_unitario": "10"}]},
        headers=auth_admin.headers,
    ).json()

    r = cliente_api.post(f"/compras/{compra['id']}/anular", headers=auth_admin.headers)
    assert r.status_code == 200, r.text

    actual = cliente_api.get(f"/productos/{p['id']}", headers=auth_admin.headers).json()
    assert actual["stock"] == 2

    # El gasto de esa compra desaparece con ella.
    assert cliente_api.get("/gastos/", headers=auth_admin.headers).json()["total"] == 0.0

    assert cliente_api.post(
        f"/compras/{compra['id']}/anular", headers=auth_admin.headers
    ).status_code == 409


def test_no_anula_compra_si_ya_se_vendio_la_mercancia(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, stock=0, costo="0")
    compra = cliente_api.post(
        "/compras/",
        json={"items": [{"producto_id": p["id"], "cantidad": 3, "costo_unitario": "10"}]},
        headers=auth_admin.headers,
    ).json()

    cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": p["id"], "cantidad": 2}]},
        headers=auth_admin.headers,
    )

    r = cliente_api.post(f"/compras/{compra['id']}/anular", headers=auth_admin.headers)
    assert r.status_code == 409
    assert "ya se vendió" in r.json()["detail"]


def test_compra_con_producto_ajeno_es_rechazada(cliente_api, auth_admin, crear_usuario):
    otro = crear_usuario(usuario="ajeno", rol="admin")
    ajeno = _producto(cliente_api, {"Authorization": f"Bearer {otro['token']}"}, nombre="Ajeno")

    r = cliente_api.post(
        "/compras/",
        json={"items": [{"producto_id": ajeno["id"], "cantidad": 1, "costo_unitario": "5"}]},
        headers=auth_admin.headers,
    )
    assert r.status_code == 404


def test_total_lo_calcula_el_servidor(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers)
    r = cliente_api.post(
        "/compras/",
        json={
            "total": "1.00",
            "items": [{"producto_id": p["id"], "cantidad": 2, "costo_unitario": "30"}],
        },
        headers=auth_admin.headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["total"] == 60.0


def test_resumen_por_proveedor(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers)
    proveedor = _proveedor(cliente_api, auth_admin.headers)
    cliente_api.post(
        "/compras/",
        json={
            "proveedor_id": proveedor["id"],
            "items": [{"producto_id": p["id"], "cantidad": 2, "costo_unitario": "40"}],
        },
        headers=auth_admin.headers,
    )

    resumen = cliente_api.get("/compras/resumen/por-proveedor", headers=auth_admin.headers).json()
    assert len(resumen) == 1
    assert resumen[0]["compras"] == 1
    assert resumen[0]["total"] == 80.0


def test_no_borra_proveedor_con_compras(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers)
    proveedor = _proveedor(cliente_api, auth_admin.headers)
    cliente_api.post(
        "/compras/",
        json={
            "proveedor_id": proveedor["id"],
            "items": [{"producto_id": p["id"], "cantidad": 1, "costo_unitario": "10"}],
        },
        headers=auth_admin.headers,
    )

    r = cliente_api.delete(f"/proveedores/{proveedor['id']}", headers=auth_admin.headers)
    assert r.status_code == 409
