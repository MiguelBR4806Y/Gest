from datetime import date, datetime, timezone
from decimal import Decimal

from Backend.dinero import a_float, dinero, multiplicar, porcentaje, tasa_cambio
from Backend.tiempo import rango_dia


def test_redondeo_comercial_half_up():
    # El caso clásico que float rompe: 2.675 en binario es 2.674999...
    assert dinero("2.675") == Decimal("2.68")
    assert dinero(0.005) == Decimal("0.01")
    assert dinero(2.674) == Decimal("2.67")


def test_suma_de_centavos_es_exacta():
    total = sum((dinero("0.10"), dinero("0.20")))
    assert total == Decimal("0.30")
    assert total == dinero("0.3")
    # float daría 0.30000000000000004
    assert float(total) == 0.3


def test_multiplicar_y_porcentaje():
    assert multiplicar("19.99", 3) == Decimal("59.97")
    assert porcentaje("100.00", "33.33") == Decimal("33.33")
    assert multiplicar("0.10", 1000000) == Decimal("100000.00")


def test_entradas_invalidas_no_revientan():
    assert dinero(None) == Decimal("0.00")
    assert dinero("no-es-numero") == Decimal("0.00")
    assert dinero(float("nan")) == Decimal("0.00")
    assert dinero(float("inf")) == Decimal("0.00")


def test_tasa_conserva_cuatro_decimales():
    assert tasa_cambio("36.54321") == Decimal("36.5432")
    assert tasa_cambio(36) == Decimal("36.0000")


def test_a_float_solo_en_el_borde():
    assert a_float(Decimal("1234.565")) == 1234.57


def test_rango_dia_respeta_la_zona_del_negocio():
    inicio, fin = rango_dia(date(2026, 5, 10), "America/Managua")
    # Managua es UTC-6 todo el año: medianoche local = 06:00 UTC.
    assert inicio == datetime(2026, 5, 10, 6, 0, tzinfo=timezone.utc)
    assert fin == datetime(2026, 5, 11, 6, 0, tzinfo=timezone.utc)

    inicio_madrid, fin_madrid = rango_dia(date(2026, 5, 10), "Europe/Madrid")
    assert inicio_madrid == datetime(2026, 5, 9, 22, 0, tzinfo=timezone.utc)
    assert fin_madrid == datetime(2026, 5, 10, 22, 0, tzinfo=timezone.utc)


def test_rango_dia_en_cambio_de_horario():
    # 29/03/2026 en Madrid dura 23 horas (salto a horario de verano).
    inicio, fin = rango_dia(date(2026, 3, 29), "Europe/Madrid")
    assert (fin - inicio).total_seconds() == 23 * 3600
