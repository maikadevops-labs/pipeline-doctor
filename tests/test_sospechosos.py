from doctor.diff import comparar
from doctor.sospechosos import generar

LOG = "E   AttributeError: module 'fechautil' has no attribute 'parse'"


def h(deps=None, runner=None):
    return {
        "dependencias": deps or {},
        "referencias": {},
        "herramientas": {},
        "runner": runner or {},
        "archivos": {},
    }


def test_dependencia_mencionada_en_el_error_es_el_sospechoso_principal():
    diff = comparar(
        h({"fechautil": "1.0.0", "packaging": "24.0"}),
        h({"fechautil": "1.1.0", "packaging": "25.0"}),
    )
    s = generar(diff, LOG, [])
    assert s[0]["nivel"] == "alta" and "fechautil" in s[0]["titulo"]
    assert "fechautil==1.0.0" in s[0]["tratamiento"]
    assert any("packaging" in x["evidencia"] for x in s[1:])


def test_codigo_que_aparece_en_el_log_es_alto():
    s = generar(None, "FAILED tests/test_agenda.py::test_dias", ["pacientes/app/agenda.py", "README.md"])
    assert s[0]["nivel"] == "media"  # agenda.py no aparece completo en el log
    s = generar(None, "File pacientes/app/agenda.py, line 5", ["pacientes/app/agenda.py"])
    assert s[0]["nivel"] == "alta"


def test_sin_diferencias_devuelve_un_sospechoso_bajo():
    s = generar(comparar(h({"a": "1"}), h({"a": "1"})), "boom", [])
    assert len(s) == 1 and s[0]["nivel"] == "baja"


def test_runner_distinto_es_sospechoso_medio():
    diff = comparar(h(runner={"imagen_version": "1"}), h(runner={"imagen_version": "2"}))
    assert generar(diff, "x", [])[0]["nivel"] == "media"


def test_una_dependencia_nombrada_en_un_comando_no_cuenta_como_mencion():
    diff = comparar(h({"pytest": "8.3.4"}), h({"pytest": "8.3.5"}))
    log = "##[group]Run pytest -q\nE   AssertionError: assert 1 == 2"
    assert generar(diff, log, [])[0]["nivel"] == "media"
