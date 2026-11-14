"""Vacaciones: cálculo legal del art. 76 (Ley 185) y su valor en dinero."""

from datetime import date

import pytest

from Backend.nomina import calcular_vacaciones


def _hasta(y, m, d):
    return date(y, m, d)


def test_sin_fecha_de_ingreso_no_calcula():
    r = calcular_vacaciones(None, 12000, 0)
    assert r["configurado"] is False
    assert r["dias_disponibles"] == 0.0
    assert r["valor_dias"] == 0.0


def test_seis_meses_dan_quince_dias():
    """Art. 76: quince días por cada seis meses de trabajo."""
    r = calcular_vacaciones(date(2026, 1, 1), 12000, 0, hasta=_hasta(2026, 7, 1))
    assert r["antiguedad_meses"] == 6
    assert r["dias_devengados"] == 15.0
    assert r["dias_disponibles"] == 15.0


def test_un_anio_da_treinta_dias():
    r = calcular_vacaciones(date(2025, 1, 1), 12000, 0, hasta=_hasta(2026, 1, 1))
    assert r["antiguedad_meses"] == 12
    assert r["dias_devengados"] == 30.0


def test_prorrateo_mensual_de_dos_punto_cinco():
    r = calcular_vacaciones(date(2026, 1, 1), 12000, 0, hasta=_hasta(2026, 4, 1))
    assert r["antiguedad_meses"] == 3
    assert r["dias_devengados"] == 7.5


def test_tope_anual_no_acumula_mas_de_treinta():
    # Dos años trabajados siguen dando 30 días, no 60.
    r = calcular_vacaciones(date(2024, 1, 1), 12000, 0, hasta=_hasta(2026, 1, 1))
    assert r["dias_devengados"] == 30.0


def test_resta_los_dias_tomados():
    r = calcular_vacaciones(date(2025, 1, 1), 12000, 10, hasta=_hasta(2026, 1, 1))
    assert r["dias_tomados"] == 10
    assert r["dias_disponibles"] == 20.0


def test_nunca_queda_negativo():
    r = calcular_vacaciones(date(2026, 1, 1), 12000, 40, hasta=_hasta(2026, 2, 1))
    assert r["dias_disponibles"] == 0.0
    assert r["excedido"] is True


def test_valor_en_dinero_usa_salario_diario_de_treinta():
    """MITRAB: salario diario = mensual / 30."""
    r = calcular_vacaciones(date(2025, 1, 1), 12000, 0, hasta=_hasta(2026, 1, 1))
    # 30 días × (12 000 / 30) = 12 000
    assert r["salario_diario"] == 400.0
    assert r["valor_dias"] == 12000.0


def test_valor_proporcional_en_dias_parciales():
    r = calcular_vacaciones(date(2026, 1, 1), 15000, 2, hasta=_hasta(2026, 7, 1))
    # 15 devengados - 2 tomados = 13 × 500
    assert r["dias_disponibles"] == 13.0
    assert r["valor_dias"] == 6500.0


def test_mes_incompleto_no_cuenta():
    # Del 1 al 20 de marzo no llega a un mes completo.
    r = calcular_vacaciones(date(2026, 1, 1), 12000, 0, hasta=_hasta(2026, 3, 20))
    assert r["antiguedad_meses"] == 2


def test_proximo_aniversario():
    r = calcular_vacaciones(date(2025, 3, 10), 12000, 0, hasta=_hasta(2026, 1, 15))
    assert r["proximo_aniversario"] == "2026-03-10"


def test_los_dias_tomados_negativos_se_ignoran():
    r = calcular_vacaciones(date(2026, 1, 1), 12000, -5, hasta=_hasta(2026, 7, 1))
    assert r["dias_tomados"] == 0
    assert r["dias_disponibles"] == 15.0


@pytest.mark.parametrize("valor", ["2025-01-01", date(2025, 1, 1)])
def test_acepta_string_iso_o_date(valor):
    r = calcular_vacaciones(valor, 12000, 0, hasta=_hasta(2026, 1, 1))
    assert r["dias_devengados"] == 30.0
