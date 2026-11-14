"""Cálculo de nómina e IR: valida los ejemplos de la Ley 822 y el INSS.

Los casos están tomados de guías públicas que aplican el artículo 23 de la Ley
822 y el Decreto 06-2019, para comprobar que la aritmética coincide.
"""

from decimal import Decimal

import pytest

from Backend.nomina import (
    aguinaldo,
    calcular_comision,
    calcular_nomina,
    ir_anual,
    resumen_planilla,
    tramo_de,
)


def test_renta_bajo_el_tramo_exento_no_paga():
    assert ir_anual(Decimal("100000")) == Decimal("0.00")
    assert ir_anual(Decimal("50000")) == Decimal("0.00")


def test_tramo_del_15_por_ciento():
    # 167 400 anuales: (167 400 - 100 000) * 15 % = 10 110
    assert ir_anual(Decimal("167400")) == Decimal("10110.00")


def test_tramo_del_20_por_ciento():
    # 250 000: 15 000 + (50 000 * 20 %) = 25 000
    assert ir_anual(Decimal("250000")) == Decimal("25000.00")


def test_tramo_del_25_por_ciento():
    # 390 600: 45 000 + (40 600 * 25 %) = 55 150
    assert ir_anual(Decimal("390600")) == Decimal("55150.00")


def test_tramo_del_30_por_ciento():
    # 600 000: 82 500 + (100 000 * 30 %) = 112 500
    assert ir_anual(Decimal("600000")) == Decimal("112500.00")


def test_salario_15000_coincide_con_la_guia():
    """Ejemplo publicado: bruto 15 000 → INSS 1 050, IR 842.50, neto 13 107.50."""
    r = calcular_nomina(Decimal("15000"))

    assert r["inss_laboral"] == 1050.0
    assert r["base_gravable_mensual"] == 13950.0
    assert r["renta_anual_proyectada"] == 167400.0
    assert r["ir_mensual"] == 842.5
    assert r["salario_neto"] == 13107.5
    assert r["exento_ir"] is False


def test_salario_35000_coincide_con_la_guia():
    """Ejemplo publicado: bruto 35 000 → INSS 2 450, IR 4 595.83, neto 27 954.17."""
    r = calcular_nomina(Decimal("35000"))

    assert r["inss_laboral"] == 2450.0
    assert r["renta_anual_proyectada"] == 390600.0
    assert r["ir_mensual"] == 4595.83
    assert r["salario_neto"] == 27954.17


def test_limite_exento_alrededor_de_8960():
    """El corte práctico de exención mensual ronda C$ 8 960.57 brutos."""
    bajo = calcular_nomina(Decimal("8960"))
    assert bajo["exento_ir"] is True

    arriba = calcular_nomina(Decimal("8970"))
    assert arriba["ir_mensual"] > 0


def test_costo_patronal_pequeno_y_grande():
    pequeno = calcular_nomina(Decimal("10000"), empleados_empresa=10)
    grande = calcular_nomina(Decimal("10000"), empleados_empresa=50)

    assert pequeno["tasa_patronal"] == 21.5
    assert pequeno["inss_patronal"] == 2150.0
    assert pequeno["inatec"] == 200.0
    assert pequeno["costo_total_empleador"] == 12350.0

    assert grande["tasa_patronal"] == 22.5
    assert grande["inss_patronal"] == 2250.0
    assert grande["costo_total_empleador"] == 12450.0


def test_tramo_informativo():
    tramo = tramo_de(Decimal("167400"))
    assert tramo["tasa"] == 15.0
    assert tramo["desde"] == 100000.0
    assert tramo["hasta"] == 200000.0


def test_salario_cero_no_rompe_nada():
    r = calcular_nomina(Decimal("0"))
    assert r["salario_neto"] == 0.0
    assert r["ir_mensual"] == 0.0
    assert r["exento_ir"] is True


def test_salario_negativo_se_trata_como_cero():
    r = calcular_nomina(Decimal("-500"))
    assert r["salario_bruto"] == 0.0
    assert r["salario_neto"] == 0.0


def test_resumen_planilla_suma_los_totales():
    r = resumen_planilla([Decimal("15000"), Decimal("35000")])

    assert r["cantidad"] == 2
    assert r["total_bruto"] == 50000.0
    assert r["total_inss_laboral"] == 3500.0
    assert r["total_ir"] == pytest.approx(5438.33, abs=0.01)
    assert r["total_neto"] == pytest.approx(41061.67, abs=0.01)
    # Con 2 trabajadores la tasa patronal es la de menos de 50.
    assert r["total_inss_patronal"] == 10750.0
    assert r["total_inatec"] == 1000.0
    assert r["costo_empresa"] == 61750.0


def test_resumen_planilla_vacia():
    r = resumen_planilla([])
    assert r["cantidad"] == 0
    assert r["total_bruto"] == 0.0
    assert r["costo_empresa"] == 0.0


def test_aguinaldo_es_un_mes_de_salario():
    r = aguinaldo(Decimal("12000"))
    assert r["aguinaldo_anual"] == 12000.0
    assert r["aguinaldo_mensual_provisionado"] == 1000.0


# ── Bonos y comisiones dentro de la nómina ──


def test_sin_extra_el_resultado_no_cambia():
    """Regresión: calcular_nomina sin extra debe dar lo mismo que antes."""
    r = calcular_nomina(Decimal("15000"))
    assert r["salario_base"] == 15000.0
    assert r["extra_total"] == 0.0
    assert r["salario_bruto"] == 15000.0
    assert r["ir_mensual"] == 842.5
    assert r["salario_neto"] == 13107.5


def test_el_extra_sube_el_bruto_y_los_impuestos():
    base = calcular_nomina(Decimal("15000"))
    con_extra = calcular_nomina(Decimal("15000"), extra=Decimal("1000"))

    assert con_extra["salario_base"] == 15000.0
    assert con_extra["extra_total"] == 1000.0
    assert con_extra["salario_bruto"] == 16000.0
    # INSS e IR se calculan sobre 16 000, no sobre 15 000.
    assert con_extra["inss_laboral"] == 1120.0
    assert con_extra["inss_laboral"] > base["inss_laboral"]
    assert con_extra["ir_mensual"] > base["ir_mensual"]
    # Y el neto sube, pero menos que el bono completo.
    assert base["salario_neto"] < con_extra["salario_neto"] < 16000.0


def test_el_extra_negativo_se_ignora():
    r = calcular_nomina(Decimal("15000"), extra=Decimal("-500"))
    assert r["extra_total"] == 0.0
    assert r["salario_bruto"] == 15000.0


def test_detalle_extra_se_devuelve_tal_cual():
    detalle = [
        {"tipo": "comision", "concepto": "Comisión 10%", "monto": 300.0},
        {"tipo": "bono", "concepto": "Productividad", "monto": 700.0},
    ]
    r = calcular_nomina(Decimal("10000"), extra=Decimal("1000"), detalle_extra=detalle)
    assert r["detalle_extra"] == detalle


def test_el_costo_de_empresa_incluye_el_extra():
    base = calcular_nomina(Decimal("10000"))
    con_extra = calcular_nomina(Decimal("10000"), extra=Decimal("2000"))
    assert con_extra["costo_total_empleador"] > base["costo_total_empleador"]
    # 12 000 + 21.5 % + 2 %
    assert con_extra["costo_total_empleador"] == 14820.0


def test_resumen_planilla_acepta_extras():
    r = resumen_planilla([
        {"salario": 15000, "extra": 500},
        {"salario": 35000, "extra": 0},
    ])
    assert r["cantidad"] == 2
    assert r["total_base"] == 50000.0
    assert r["total_extra"] == 500.0
    assert r["total_bruto"] == 50500.0


def test_resumen_planilla_sigue_aceptando_numeros():
    r = resumen_planilla([Decimal("15000"), Decimal("35000")])
    assert r["total_extra"] == 0.0
    assert r["total_bruto"] == 50000.0
    assert r["costo_empresa"] == 61750.0


# ── Comisión ──


def test_comision_es_el_porcentaje_de_las_ventas():
    r = calcular_comision(Decimal("10000"), Decimal("10"))
    assert r["ventas"] == 10000.0
    assert r["comision_pct"] == 10.0
    assert r["comision"] == 1000.0


def test_comision_cero_no_suma():
    assert calcular_comision(Decimal("5000"), 0)["comision"] == 0.0


def test_comision_se_limita_al_cien_por_ciento():
    r = calcular_comision(Decimal("1000"), 250)
    assert r["comision_pct"] == 100.0
    assert r["comision"] == 1000.0


def test_comision_negativa_se_trata_como_cero():
    assert calcular_comision(Decimal("1000"), -5)["comision"] == 0.0


def test_ventas_negativas_se_tratan_como_cero():
    assert calcular_comision(Decimal("-1000"), 10)["ventas"] == 0.0
