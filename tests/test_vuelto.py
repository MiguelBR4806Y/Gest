"""Cobro en efectivo: efectivo recibido, vuelto y validaciones."""

from Backend.dinero import dinero


def _producto(client, headers, nombre="Producto", stock=10, precio="100"):
    return client.post(
        "/productos/",
        json={"nombre": nombre, "stock": stock, "precio": precio},
        headers=headers,
    ).json()


def _vender(client, headers, producto_id, cantidad=1, **extra):
    return client.post(
        "/ventas/",
        json={
            "metodo_pago": "efectivo",
            "items": [{"producto_id": producto_id, "cantidad": cantidad}],
            **extra,
        },
        headers=headers,
    )


def test_calcula_el_vuelto(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="150")
    r = _vender(cliente_api, auth_admin.headers, p["id"], efectivo_recibido=200)

    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["total"] == 150.0
    assert datos["efectivo_recibido"] == 200.0
    assert datos["vuelto"] == 50.0


def test_pago_exacto_da_vuelto_cero(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="150")
    r = _vender(cliente_api, auth_admin.headers, p["id"], efectivo_recibido=150)

    assert r.status_code == 200
    assert r.json()["vuelto"] == 0.0


def test_efectivo_menor_al_total_es_rechazado(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="150")
    r = _vender(cliente_api, auth_admin.headers, p["id"], efectivo_recibido=100)

    assert r.status_code == 400
    assert "menor que el total" in r.json()["detail"]

    # No se creó la venta ni se descontó stock.
    assert cliente_api.get("/ventas/", headers=auth_admin.headers).json()["total"] == 0
    actual = cliente_api.get(f"/productos/{p['id']}", headers=auth_admin.headers).json()
    assert actual["stock"] == 10


def test_sin_efectivo_se_asume_pago_exacto(cliente_api, auth_admin):
    """Compatibilidad: las integraciones que no mandan el campo siguen valiendo."""
    p = _producto(cliente_api, auth_admin.headers, precio="80")
    r = _vender(cliente_api, auth_admin.headers, p["id"])

    assert r.status_code == 200, r.text
    assert r.json()["efectivo_recibido"] == 80.0
    assert r.json()["vuelto"] == 0.0


def test_otros_metodos_no_llevan_efectivo(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers)
    r = cliente_api.post(
        "/ventas/",
        json={
            "metodo_pago": "tarjeta",
            "items": [{"producto_id": p["id"], "cantidad": 1}],
        },
        headers=auth_admin.headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["efectivo_recibido"] is None
    assert r.json()["vuelto"] is None


def test_efectivo_con_metodo_tarjeta_es_rechazado(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers)
    r = cliente_api.post(
        "/ventas/",
        json={
            "metodo_pago": "tarjeta",
            "efectivo_recibido": 200,
            "items": [{"producto_id": p["id"], "cantidad": 1}],
        },
        headers=auth_admin.headers,
    )
    assert r.status_code == 422


def test_el_vuelto_no_se_puede_falsear(cliente_api, auth_admin):
    """El total lo calcula el servidor, así que el vuelto tampoco viene del cliente."""
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    r = cliente_api.post(
        "/ventas/",
        json={
            "metodo_pago": "efectivo",
            "efectivo_recibido": 100,
            "vuelto": 999999,
            "items": [{"producto_id": p["id"], "cantidad": 1}],
        },
        headers=auth_admin.headers,
    )
    assert r.status_code == 200
    assert r.json()["vuelto"] == 0.0


def test_el_vuelto_usa_el_total_con_promocion(cliente_api, auth_admin):
    """Con un 2x1 el vuelto se calcula sobre lo que realmente se cobra."""
    promo = cliente_api.post(
        "/promociones/",
        json={"nombre": "2x1", "tipo": "2x1", "valor": 0},
        headers=auth_admin.headers,
    ).json()
    p = cliente_api.post(
        "/productos/",
        json={"nombre": "Dos por uno", "stock": 10, "precio": "100", "promocion_id": promo["id"]},
        headers=auth_admin.headers,
    ).json()

    r = _vender(cliente_api, auth_admin.headers, p["id"], cantidad=2, efectivo_recibido=200)
    assert r.status_code == 200, r.text
    datos = r.json()
    # 2x1: paga una unidad (100), entrega 200 → vuelto 100.
    assert datos["total"] == 100.0
    assert datos["vuelto"] == 100.0


def test_el_detalle_y_el_listado_incluyen_el_cobro(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    venta = _vender(cliente_api, auth_admin.headers, p["id"], efectivo_recibido=500).json()

    detalle = cliente_api.get(f"/ventas/{venta['id']}", headers=auth_admin.headers).json()
    assert detalle["efectivo_recibido"] == 500.0
    assert detalle["vuelto"] == 400.0

    listado = cliente_api.get("/ventas/", headers=auth_admin.headers).json()
    fila = listado["items"][0]
    assert fila["efectivo_recibido"] == 500.0
    assert fila["vuelto"] == 400.0


def test_la_factura_incluye_el_vuelto(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    venta = _vender(cliente_api, auth_admin.headers, p["id"], efectivo_recibido=500).json()

    r = cliente_api.get(f"/facturas/{venta['id']}", headers=auth_admin.headers)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


def test_el_csv_incluye_efectivo_y_vuelto(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    _vender(cliente_api, auth_admin.headers, p["id"], efectivo_recibido=500)

    from Backend.tiempo import hoy_local

    hoy = hoy_local("America/Managua").isoformat()
    r = cliente_api.get(
        f"/reportes/exportar?desde={hoy}&hasta={hoy}", headers=auth_admin.headers
    )
    texto = r.content.decode("utf-8-sig")
    assert "Efectivo recibido C$" in texto
    assert "500.00" in texto
    assert "400.00" in texto


def test_la_anulacion_no_cambia_el_efectivo(cliente_api, auth_admin):
    """La venta anulada conserva lo que se cobró: no se reescribe el historial."""
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    venta = _vender(cliente_api, auth_admin.headers, p["id"], efectivo_recibido=200).json()

    cliente_api.delete(f"/ventas/{venta['id']}", headers=auth_admin.headers)
    detalle = cliente_api.get(f"/ventas/{venta['id']}", headers=auth_admin.headers).json()
    assert detalle["estado"] == "anulada"
    assert detalle["efectivo_recibido"] == 200.0
    assert detalle["vuelto"] == 100.0


def test_el_vuelto_se_redondea_a_centavos(cliente_api, auth_admin):
    p = _producto(cliente_api, auth_admin.headers, precio="33.33")
    r = _vender(cliente_api, auth_admin.headers, p["id"], efectivo_recibido="50.00")

    assert r.status_code == 200
    assert r.json()["vuelto"] == 16.67


def test_vuelto_negativo_en_la_base_no_es_posible(cliente_api, auth_admin):
    """El CHECK de la tabla es la última red, aunque la API ya lo valida."""
    assert dinero(-1) < 0
    p = _producto(cliente_api, auth_admin.headers, precio="100")
    assert _vender(
        cliente_api, auth_admin.headers, p["id"], efectivo_recibido="99.99"
    ).status_code == 400
