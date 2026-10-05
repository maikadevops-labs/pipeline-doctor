from datetime import date

from app.agenda import describir, dias_para


def test_dias_para():
    assert dias_para("2026-10-10", hoy=date(2026, 10, 5)) == 5


def test_dias_para_fecha_pasada():
    assert dias_para("2026-10-01", hoy=date(2026, 10, 5)) == -4


def test_describir_iso():
    assert describir("2026-10-05") == "5 de octubre de 2026"


def test_describir_formato_latino():
    assert describir("5/10/2026") == "5 de octubre de 2026"
