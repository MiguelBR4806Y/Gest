import asyncio

import httpx
import pytest

import main
from Backend.tiempo import hoy_local


def crear_producto(client, headers, nombre="Producto", stock=10, precio="10.00", **extra):
    respuesta = client.post(
        "/productos/",
        json={"nombre": nombre, "stock": stock, "precio": precio, **extra},
        headers=headers,
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def crear_cliente(client, headers, nombre="Cliente", limite="0.00"):
    respuesta = client.post(
        "/clientes/",
        json={"nombre": nombre, "credito_limite": limite},
        headers=headers,
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def vender(client, headers, items, metodo="efectivo", cliente_id=None):
    return client.post(
        "/ventas/",
        json={"metodo_pago": metodo, "cliente_id": cliente_id, "items": items},
        headers=headers,
    )


def test_venta_simple_descuenta_stock(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=5, precio="12.50")

    r = vender(cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 2}])
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 25.0

    actual = cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()
    assert actual["stock"] == 3


def test_no_vende_mas_stock_del_disponible(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=1)

    r = vender(cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 2}])
    assert r.status_code == 409
    assert "Stock insuficiente" in r.json()["detail"]

    actual = cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()
    assert actual["stock"] == 1


def test_lineas_repetidas_se_suman_antes_de_validar(cliente_api, auth):
    """Dos líneas del mismo producto no deben poder saltarse el stock."""
    p = crear_producto(cliente_api, auth.headers, stock=3, precio="10.00")

    r = vender(cliente_api, auth.headers, [
        {"producto_id": p["id"], "cantidad": 2},
        {"producto_id": p["id"], "cantidad": 2},
    ])
    assert r.status_code == 409

    actual = cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()
    assert actual["stock"] == 3


def test_precio_del_cliente_se_ignora(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=10, precio="100.00")

    r = vender(cliente_api, auth.headers, [
        {"producto_id": p["id"], "cantidad": 1, "precio_unitario": "0.01"},
    ])
    assert r.status_code == 200
    assert r.json()["total"] == 100.0


def test_promocion_porcentaje_calcula_exacto(cliente_api, auth):
    promo = cliente_api.post(
        "/promociones/",
        json={"nombre": "10 off", "tipo": "porcentaje", "valor": "10.00", "activa": True},
        headers=auth.headers,
    ).json()
    p = crear_producto(
        cliente_api, auth.headers, stock=10, precio="33.33", promocion_id=promo["id"],
    )

    r = vender(cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 3}])
    assert r.status_code == 200, r.text
    # 99.99 - 10% = 89.991 -> 89.99 (half-up), no 89.99000000000001
    assert r.json()["total"] == 89.99


def test_promocion_2x1(cliente_api, auth):
    promo = cliente_api.post(
        "/promociones/",
        json={"nombre": "2x1", "tipo": "2x1", "valor": "0", "activa": True},
        headers=auth.headers,
    ).json()
    p = crear_producto(
        cliente_api, auth.headers, stock=10, precio="50.00", promocion_id=promo["id"],
    )

    r = vender(cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 4}])
    assert r.json()["total"] == 100.0


def test_venta_a_credito_valida_limite(cliente_api, auth):
    c = crear_cliente(cliente_api, auth.headers, limite="100.00")
    p = crear_producto(cliente_api, auth.headers, stock=10, precio="40.00")

    dentro = vender(
        cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 2}],
        metodo="credito", cliente_id=c["id"],
    )
    assert dentro.status_code == 200

    cliente = cliente_api.get(f"/clientes/{c['id']}", headers=auth.headers).json()
    assert cliente["credito_usado"] == 80.0
    assert cliente["credito_disponible"] == 20.0

    excedido = vender(
        cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 1}],
        metodo="credito", cliente_id=c["id"],
    )
    assert excedido.status_code == 400
    assert "Crédito insuficiente" in excedido.json()["detail"]


def test_anular_conserva_la_venta_y_restaura_todo(cliente_api, auth):
    c = crear_cliente(cliente_api, auth.headers, limite="500.00")
    p = crear_producto(cliente_api, auth.headers, stock=10, precio="25.00")

    venta = vender(
        cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 4}],
        metodo="credito", cliente_id=c["id"],
    ).json()

    anulada = cliente_api.request(
        "DELETE", f"/ventas/{venta['id']}",
        json={"motivo": "Cliente devolvió el producto"},
        headers=auth.headers,
    )
    assert anulada.status_code == 200, anulada.text
    assert anulada.json()["estado"] == "anulada"

    # La venta sigue existiendo, con su motivo y su estado.
    detalle = cliente_api.get(f"/ventas/{venta['id']}", headers=auth.headers).json()
    assert detalle["estado"] == "anulada"
    assert detalle["motivo_anulacion"] == "Cliente devolvió el producto"
    assert detalle["anulada_por"] == "ana"

    # Stock y crédito vueltos a su sitio.
    producto = cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()
    assert producto["stock"] == 10
    cliente = cliente_api.get(f"/clientes/{c['id']}", headers=auth.headers).json()
    assert cliente["credito_usado"] == 0.0

    # El resumen del día no cuenta la venta anulada.
    resumen = cliente_api.get(
        f"/ventas/resumen-dia?fecha={hoy_local('America/Managua').isoformat()}",
        headers=auth.headers,
    ).json()
    assert resumen["numero_ventas"] == 0
    assert resumen["total_ventas"] == 0.0
    assert resumen["anuladas"]["numero"] == 1
    assert resumen["anuladas"]["total"] == 100.0


def test_no_se_puede_anular_dos_veces(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=5)
    venta = vender(cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 1}]).json()

    primera = cliente_api.request(
        "DELETE", f"/ventas/{venta['id']}", json={"motivo": "error"}, headers=auth.headers
    )
    assert primera.status_code == 200

    segunda = cliente_api.request(
        "DELETE", f"/ventas/{venta['id']}", json={"motivo": "otra vez"}, headers=auth.headers
    )
    assert segunda.status_code == 409

    producto = cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()
    assert producto["stock"] == 5


def test_anular_tambien_sin_cuerpo(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=5)
    venta = vender(cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 1}]).json()

    r = cliente_api.request("DELETE", f"/ventas/{venta['id']}", headers=auth.headers)
    assert r.status_code == 200
    assert r.json()["motivo"] is None


def test_ventas_simultaneas_no_sobrevenden(cliente_api, auth):
    """Dos cajas vendiendo la última unidad a la vez: solo una puede ganar."""
    p = crear_producto(cliente_api, auth.headers, nombre="Última", stock=1, precio="10.00")

    async def intentar():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.post(
                "/ventas/",
                json={"metodo_pago": "efectivo", "items": [{"producto_id": p["id"], "cantidad": 1}]},
                headers=auth.headers,
            )

    async def carrera():
        return await asyncio.gather(intentar(), intentar())

    resultados = asyncio.run(carrera())
    codigos = sorted(r.status_code for r in resultados)
    assert codigos == [200, 409], [r.text for r in resultados]

    producto = cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()
    assert producto["stock"] == 0


@pytest.mark.parametrize("metodo", ["efectivo", "tarjeta", "transferencia", "credito"])
def test_metodos_de_pago_aceptados(cliente_api, auth, metodo):
    c = crear_cliente(cliente_api, auth.headers, limite="1000.00")
    p = crear_producto(cliente_api, auth.headers, stock=10)
    r = vender(
        cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 1}],
        metodo=metodo, cliente_id=c["id"],
    )
    assert r.status_code == 200


def test_metodo_de_pago_invalido_rechazado(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=10)
    r = vender(cliente_api, auth.headers, [{"producto_id": p["id"], "cantidad": 1}], metodo="bitcoin")
    assert r.status_code == 422
