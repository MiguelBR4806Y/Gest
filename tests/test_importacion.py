"""Importación de catálogo por CSV."""

import io


def _subir(client, headers, texto, modo="ambos", simular=False, nombre="catalogo.csv"):
    return client.post(
        "/productos/importar",
        params={"modo": modo, "simular": str(simular).lower()},
        files={"archivo": (nombre, io.BytesIO(texto.encode("utf-8")), "text/csv")},
        headers=headers,
    )


def test_importa_csv_punto_y_coma(cliente_api, auth_admin):
    csv = (
        "nombre;categoria;codigo_barras;stock;stock_minimo;precio;costo\n"
        "Café;Abarrotes;111;10;2;95.00;70.00\n"
        "Pan;Panadería;222;5;1;55.00;40.00\n"
    )
    r = _subir(cliente_api, auth_admin.headers, csv)
    assert r.status_code == 200, r.text
    informe = r.json()
    assert informe["creados"] == 2
    assert informe["errores"] == []

    productos = cliente_api.get("/productos/", headers=auth_admin.headers).json()
    assert {p["codigo_barras"] for p in productos} == {"111", "222"}
    assert all(p["categoria"] for p in productos)


def test_importa_csv_con_coma_y_bom(cliente_api, auth_admin):
    csv = (
        "\ufeffnombre,precio,stock\n"
        "Arroz,45.50,12\n"
    )
    r = _subir(cliente_api, auth_admin.headers, csv)
    assert r.status_code == 200, r.text
    assert r.json()["creados"] == 1

    producto = cliente_api.get("/productos/", headers=auth_admin.headers).json()[0]
    assert producto["nombre"] == "Arroz"
    assert producto["precio"] == 45.5
    assert producto["stock"] == 12


def test_cabeceras_tolerantes_a_acentos_y_espacios(cliente_api, auth_admin):
    csv = (
        "Producto;Categoría;Código de barras;Precio C$;Costo\n"
        "Jabón;Limpieza;999;30;20\n"
    )
    r = _subir(cliente_api, auth_admin.headers, csv)
    assert r.status_code == 200, r.text
    informe = r.json()
    assert informe["creados"] == 1

    producto = cliente_api.get("/productos/", headers=auth_admin.headers).json()[0]
    assert producto["codigo_barras"] == "999"
    assert producto["precio"] == 30.0
    assert producto["costo"] == 20.0


def test_fila_invalida_no_aborta_la_importacion(cliente_api, auth_admin):
    csv = (
        "nombre;precio\n"
        "Bueno;10\n"
        ";20\n"
        "Otro;10\n"
    )
    r = _subir(cliente_api, auth_admin.headers, csv)
    assert r.status_code == 200, r.text
    informe = r.json()
    assert informe["creados"] == 2
    assert informe["total_errores"] == 1
    assert informe["errores"][0]["fila"] == 3


def test_simular_no_escribe_en_la_base(cliente_api, auth_admin):
    csv = "nombre;precio\nFantasma;10\n"

    r = _subir(cliente_api, auth_admin.headers, csv, simular=True)
    assert r.status_code == 200, r.text
    informe = r.json()
    assert informe["simulado"] is True
    assert informe["creados"] == 1
    assert informe["vista_previa"][0]["accion"] == "crear"

    assert cliente_api.get("/productos/", headers=auth_admin.headers).json() == []


def test_modo_crear_ignora_los_codigos_existentes(cliente_api, auth_admin):
    cliente_api.post(
        "/productos/",
        json={"nombre": "Existente", "codigo_barras": "555", "precio": "10", "stock": 1},
        headers=auth_admin.headers,
    )

    csv = "nombre;codigo_barras;precio;stock\nActualizado;555;99;7\n"
    r = _subir(cliente_api, auth_admin.headers, csv, modo="crear")
    assert r.json()["ignorados"] == 1

    producto = cliente_api.get("/productos/", headers=auth_admin.headers).json()[0]
    assert producto["nombre"] == "Existente"
    assert producto["precio"] == 10.0


def test_modo_actualizar_modifica_por_codigo_de_barras(cliente_api, auth_admin):
    cliente_api.post(
        "/productos/",
        json={"nombre": "Viejo", "codigo_barras": "777", "precio": "10", "stock": 1},
        headers=auth_admin.headers,
    )

    csv = "nombre;codigo_barras;precio;stock;costo\nNuevo;777;50;9;30\n"
    r = _subir(cliente_api, auth_admin.headers, csv, modo="actualizar")
    assert r.status_code == 200, r.text
    assert r.json()["actualizados"] == 1

    productos = cliente_api.get("/productos/", headers=auth_admin.headers).json()
    assert len(productos) == 1
    assert productos[0]["nombre"] == "Nuevo"
    assert productos[0]["precio"] == 50.0
    assert productos[0]["stock"] == 9
    assert productos[0]["costo"] == 30.0


def test_falta_la_columna_nombre(cliente_api, auth_admin):
    r = _subir(cliente_api, auth_admin.headers, "precio;stock\n10;1\n")
    assert r.status_code == 400
    assert "nombre" in r.json()["detail"]


def test_csv_vacio_es_rechazado(cliente_api, auth_admin):
    r = _subir(cliente_api, auth_admin.headers, "")
    assert r.status_code == 400


def test_codigo_repetido_en_el_mismo_csv_no_duplica(cliente_api, auth_admin):
    csv = (
        "nombre;codigo_barras;precio;stock\n"
        "Primera;888;10;1\n"
        "Segunda;888;20;2\n"
    )
    r = _subir(cliente_api, auth_admin.headers, csv)
    assert r.status_code == 200, r.text
    informe = r.json()
    assert informe["creados"] == 1
    assert informe["actualizados"] == 1

    productos = cliente_api.get("/productos/", headers=auth_admin.headers).json()
    assert len(productos) == 1
    assert productos[0]["nombre"] == "Segunda"
    assert productos[0]["stock"] == 2


def test_plantilla_descargable(cliente_api, auth_admin):
    r = cliente_api.get("/productos/plantilla-csv", headers=auth_admin.headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert r.content.decode("utf-8-sig").startswith("nombre;categoria")


def test_vendedor_no_puede_importar(cliente_api, auth_admin):
    creado = cliente_api.post(
        "/vendedores/", json={"nombre": "Vendedor Import"}, headers=auth_admin.headers
    ).json()
    login = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}

    r = _subir(cliente_api, headers, "nombre;precio\nX;1\n")
    assert r.status_code == 403
