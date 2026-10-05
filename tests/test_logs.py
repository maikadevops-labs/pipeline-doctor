from doctor import logs

LOG_PYTEST = """2026-10-05T12:00:01.1234567Z ##[group]Run pytest -q
2026-10-05T12:00:01.2000000Z pytest -q
2026-10-05T12:00:02.0000000Z ============ test session starts ============
2026-10-05T12:00:02.5000000Z tests/test_agenda.py F.
2026-10-05T12:00:02.6000000Z E   AttributeError: module 'fechautil' has no attribute 'parse'
2026-10-05T12:00:02.7000000Z FAILED tests/test_agenda.py::test_dias - AttributeError: module 'fechautil' has no attribute 'parse'
2026-10-05T12:00:02.8000000Z ##[error]Process completed with exit code 1.
"""


def test_limpiar_quita_marcas_de_tiempo_y_ansi():
    sucio = "2026-10-05T12:00:01.1234567Z \x1b[31mrojo\x1b[0m\r\nlinea"
    assert logs.limpiar(sucio) == "rojo\nlinea"


def test_extraer_centra_en_el_ultimo_error():
    extracto = logs.extraer(logs.limpiar(LOG_PYTEST))
    assert "AttributeError" in extracto and "##[error]" in extracto


def test_extraer_sin_marca_error_usa_primera_coincidencia():
    texto = "\n".join(["ok"] * 100 + ["Traceback (most recent call last):", "ValueError: x"] + ["ok"] * 100)
    extracto = logs.extraer(texto)
    assert "Traceback" in extracto and len(extracto.splitlines()) < 60


def test_extraer_respeta_el_maximo_y_conserva_el_final():
    texto = "\n".join(["x" * 100] * 200 + ["##[error]FINAL"])
    extracto = logs.extraer(texto, max_chars=500)
    assert len(extracto) < 600 and extracto.endswith("FINAL")


def test_extraer_log_vacio():
    assert logs.extraer("") == ""


def test_linea_clave_prefiere_el_error_real_al_generico():
    extracto = logs.extraer(logs.limpiar(LOG_PYTEST))
    clave = logs.linea_clave(extracto)
    assert "AttributeError" in clave and "exit code" not in clave
