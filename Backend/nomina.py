"""Cálculo de nómina e impuestos de Nicaragua.

Fuentes normativas (verificadas, no inventadas):

- **IR sobre rentas del trabajo**: Ley 822 (Ley de Concertación Tributaria),
  artículo 23. Tarifa progresiva sobre la renta neta anual:
      hasta 100 000           → 0 %
      100 000.01 – 200 000    → 15 % sobre el exceso de 100 000
      200 000.01 – 350 000    → 15 000 + 20 % sobre el exceso de 200 000
      350 000.01 – 500 000    → 45 000 + 25 % sobre el exceso de 350 000
      más de 500 000          → 82 500 + 30 % sobre el exceso de 500 000
  El empleador proyecta la renta anual (salario menos INSS, por 12), aplica la
  tabla y divide entre 12 para la retención mensual. Reglamento (Decreto
  01-2013), artículo 19: la retención es una expectativa anual.

- **INSS laboral**: 7 % del salario bruto en el régimen integral (Decreto
  06-2019, artículo 11). No existe tope máximo desde febrero de 2019.

- **INSS patronal**: 21.50 % con menos de 50 trabajadores y 22.50 % con 50 o
  más (mismo artículo). Es costo del empleador, no se descuenta al trabajador.

- **INATEC**: 2 % sobre la planilla (Ley 1063, artículo 24).

El aguinaldo y los viáticos no cotizan al INSS. El aguinaldo no se incluye en
la proyección mensual: se calcula aparte al pagarlo.

Este módulo es una ayuda de cálculo. No sustituye la asesoría de un contador
ni la confirmación de las cifras vigentes con la DGI, el INSS y el MITRAB.
"""

from datetime import date, datetime
from decimal import Decimal

from Backend.dinero import CIEN, CERO, dinero, porcentaje, sumar

# ── Parámetros vigentes ──

INSS_LABORAL = Decimal("0.07")
INSS_PATRONAL_MENOS_50 = Decimal("0.215")
INSS_PATRONAL_50_O_MAS = Decimal("0.225")
INATEC = Decimal("0.02")
LIMITE_EMPLEADOR_GRANDE = 50
MESES_DEL_ANIO = 12

# (tope inferior, tope superior, impuesto base, tasa, exceso sobre)
# El primer tramo es exento.
TRAMOS_IR = [
    (Decimal("0"), Decimal("100000"), CERO, Decimal("0"), CERO),
    (Decimal("100000"), Decimal("200000"), CERO, Decimal("0.15"), Decimal("100000")),
    (Decimal("200000"), Decimal("350000"), Decimal("15000"), Decimal("0.20"), Decimal("200000")),
    (Decimal("350000"), Decimal("500000"), Decimal("45000"), Decimal("0.25"), Decimal("350000")),
    (Decimal("500000"), None, Decimal("82500"), Decimal("0.30"), Decimal("500000")),
]

VERSION_TABLA = "Ley 822 art. 23 · INSS Decreto 06-2019 · INATEC Ley 1063"


def ir_anual(renta_neta_anual) -> Decimal:
    """Impuesto anual según la tarifa progresiva del artículo 23."""
    renta = dinero(renta_neta_anual)
    if renta <= CERO:
        return CERO

    for _desde, hasta, base, tasa, exceso in TRAMOS_IR:
        if hasta is None or renta <= hasta:
            # `porcentaje` trabaja con Decimal: `multiplicar` trunca a entero
            # porque está pensado para cantidades de producto.
            return dinero(base + porcentaje(renta - exceso, tasa * 100))
    return CERO


def tramo_de(renta_neta_anual) -> dict:
    """Tramo aplicable, para poder mostrar 'estás en el 15 %'."""
    renta = dinero(renta_neta_anual)
    for desde, hasta, base, tasa, exceso in TRAMOS_IR:
        if hasta is None or renta <= hasta:
            return {
                "desde": float(desde),
                "hasta": float(hasta) if hasta is not None else None,
                "tasa": float(tasa * 100),
                "impuesto_base": float(base),
                "exceso_sobre": float(exceso),
            }
    return {}


def calcular_nomina(salario_bruto, empleados_empresa: int = 1, extra=0, detalle_extra=None) -> dict:
    """Desglose mensual de un salario: INSS, IR, neto y costo patronal.

    `empleados_empresa` decide la tasa patronal (21.50 % o 22.50 %).
    `extra` son los bonos y comisiones del periodo: se suman al bruto **antes**
    de INSS e IR, porque son renta del trabajo. Sin `extra` el resultado es
    idéntico al de siempre.
    """
    base = dinero(salario_bruto)
    if base < CERO:
        base = CERO
    adicional = dinero(extra)
    if adicional < CERO:
        adicional = CERO
    bruto = dinero(base + adicional)

    inss_laboral = porcentaje(bruto, INSS_LABORAL * 100)
    base_gravable_mensual = dinero(bruto - inss_laboral)
    renta_anual = dinero(base_gravable_mensual * MESES_DEL_ANIO)
    impuesto_anual = ir_anual(renta_anual)
    ir_mensual = dinero(impuesto_anual / MESES_DEL_ANIO)

    neto = dinero(bruto - inss_laboral - ir_mensual)

    tasa_patronal = (
        INSS_PATRONAL_50_O_MAS
        if empleados_empresa >= LIMITE_EMPLEADOR_GRANDE
        else INSS_PATRONAL_MENOS_50
    )
    inss_patronal = porcentaje(bruto, tasa_patronal * 100)
    inatec = porcentaje(bruto, INATEC * 100)
    costo_total = sumar([bruto, inss_patronal, inatec])

    return {
        "salario_base": float(base),
        "extra_total": float(adicional),
        "detalle_extra": detalle_extra or [],
        "salario_bruto": float(bruto),
        "inss_laboral": float(inss_laboral),
        "base_gravable_mensual": float(base_gravable_mensual),
        "renta_anual_proyectada": float(renta_anual),
        "ir_anual": float(impuesto_anual),
        "ir_mensual": float(ir_mensual),
        "salario_neto": float(neto),
        "tasa_patronal": float(tasa_patronal * 100),
        "inss_patronal": float(inss_patronal),
        "inatec": float(inatec),
        "costo_total_empleador": float(costo_total),
        "tramo": tramo_de(renta_anual),
        "exento_ir": impuesto_anual == CERO,
        "parametros": {
            "inss_laboral_pct": float(INSS_LABORAL * 100),
            "inss_patronal_pct": float(tasa_patronal * 100),
            "inatec_pct": float(INATEC * 100),
            "version": VERSION_TABLA,
        },
    }


def calcular_comision(ventas_periodo, comision_pct) -> dict:
    """Comisión sobre las ventas del periodo. El % lo fija el admin."""
    ventas = dinero(ventas_periodo)
    if ventas < CERO:
        ventas = CERO
    pct = Decimal(str(comision_pct or 0))
    if pct < CERO:
        pct = CERO
    if pct > CIEN:
        pct = CIEN

    return {
        "ventas": float(ventas),
        "comision_pct": float(pct),
        "comision": float(porcentaje(ventas, pct)),
    }


# Art. 76 del Código del Trabajo (Ley 185): 15 días por cada 6 meses
# ininterrumpidos, es decir 2.5 días por mes y 30 al año.
DIAS_VACACIONES_POR_MES = Decimal("2.5")
DIAS_VACACIONES_AL_ANIO = Decimal("30")
DIAS_SALARIO_MES = Decimal("30")


def _a_fecha(valor) -> date | None:
    """Acepta date, datetime o ISO string; devuelve solo la fecha."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _meses_completos(desde: date, hasta: date) -> int:
    """Meses calendario completos entre dos fechas (no días / 30)."""
    if hasta < desde:
        return 0
    meses = (hasta.year - desde.year) * 12 + (hasta.month - desde.month)
    if hasta.day < desde.day:
        meses -= 1
    return max(meses, 0)


def calcular_vacaciones(
    fecha_ingreso,
    salario,
    dias_tomados=0,
    hasta=None,
) -> dict:
    """Saldo de vacaciones según el art. 76 y su valor en dinero.

    Devengados = 2.5 días por mes completo, con tope de 30 al año. El saldo no
    puede quedar negativo aunque se hayan registrado más días de los devengados
    (se informa en `excedido`).
    """
    hoy = _a_fecha(hasta) or date.today()
    tomados = max(int(dias_tomados or 0), 0)
    ingreso = _a_fecha(fecha_ingreso)

    if ingreso is None:
        return {
            "configurado": False,
            "antiguedad_meses": 0,
            "dias_devengados": 0.0,
            "dias_tomados": tomados,
            "dias_disponibles": 0.0,
            "valor_dias": 0.0,
            "excedido": tomados > 0,
            "proximo_aniversario": None,
        }

    meses = _meses_completos(ingreso, hoy)
    # Tope anual: no se acumula más de un año de vacaciones.
    tope = int(DIAS_VACACIONES_AL_ANIO)
    devengados_dec = min(DIAS_VACACIONES_POR_MES * meses, Decimal(tope))
    disponibles_dec = devengados_dec - tomados
    excedido = disponibles_dec < 0
    if disponibles_dec < 0:
        disponibles_dec = CERO

    salario_diario = dinero(dinero(salario) / DIAS_SALARIO_MES)
    valor = dinero(disponibles_dec * salario_diario)

    aniversario = ingreso.replace(year=hoy.year)
    if aniversario < hoy:
        aniversario = aniversario.replace(year=hoy.year + 1)

    return {
        "configurado": True,
        "antiguedad_meses": meses,
        "dias_devengados": float(devengados_dec),
        "dias_tomados": tomados,
        "dias_disponibles": float(disponibles_dec),
        "valor_dias": float(valor),
        "salario_diario": float(salario_diario),
        "excedido": excedido,
        "proximo_aniversario": aniversario.isoformat(),
    }


def aguinaldo(salario_bruto) -> dict:
    """Aguinaldo proporcional: un mes de salario por año trabajado.

    Está exento del IR de rentas del trabajo hasta el límite legal, pero sí se
    reporta. Se muestra como dato informativo del costo anual.
    """
    bruto = dinero(salario_bruto)
    return {
        "aguinaldo_mensual_provisionado": float(dinero(bruto / MESES_DEL_ANIO)),
        "aguinaldo_anual": float(bruto),
    }


def resumen_planilla(salarios: list) -> dict:
    """Totales de la plantilla a partir de salarios o de pares (salario, extra).

    Acepta tanto `[15000, 35000]` como `[{"salario": 15000, "extra": 500}]`,
    para no romper las llamadas anteriores al añadir bonos y comisiones.
    """
    filas = []
    for item in salarios or []:
        if isinstance(item, dict):
            filas.append((item.get("salario", 0), item.get("extra", 0)))
        else:
            filas.append((item, 0))

    total_bruto = sumar([s for s, _e in filas]) if filas else CERO
    total_extra = sumar([e for _s, e in filas]) if filas else CERO
    cantidad = len(filas)

    detalle = [calcular_nomina(s, cantidad, e) for s, e in filas]
    total_neto = sumar([d["salario_neto"] for d in detalle]) if detalle else CERO
    total_inss_laboral = sumar([d["inss_laboral"] for d in detalle]) if detalle else CERO
    total_ir = sumar([d["ir_mensual"] for d in detalle]) if detalle else CERO
    total_patronal = sumar([d["inss_patronal"] for d in detalle]) if detalle else CERO
    total_inatec = sumar([d["inatec"] for d in detalle]) if detalle else CERO
    bruto_con_extra = dinero(total_bruto + total_extra)

    return {
        "cantidad": cantidad,
        "total_base": float(total_bruto),
        "total_extra": float(total_extra),
        "total_bruto": float(bruto_con_extra),
        "total_inss_laboral": float(total_inss_laboral),
        "total_ir": float(total_ir),
        "total_neto": float(total_neto),
        "total_inss_patronal": float(total_patronal),
        "total_inatec": float(total_inatec),
        "costo_empresa": float(dinero(bruto_con_extra + total_patronal + total_inatec)),
    }
