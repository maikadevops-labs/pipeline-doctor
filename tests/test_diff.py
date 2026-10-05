from doctor.diff import comparar, filas, hay_cambios, normalizar_nombre


def huella(**kw):
    base = {"dependencias": {}, "referencias": {}, "herramientas": {}, "runner": {}, "archivos": {}}
    base.update(kw)
    return base


def test_normaliza_nombres_pep503():
    assert normalizar_nombre("Foo_Bar.baz") == "foo-bar-baz"


def test_sin_cambios():
    h = huella(dependencias={"pytest": "8.3.5"}, runner={"imagen_version": "1"})
    assert not hay_cambios(comparar(h, h))


def test_dependencia_cambiada_agregada_y_quitada():
    verde = huella(dependencias={"fechautil": "1.0.0", "viejo": "1.0"})
    actual = huella(dependencias={"fechautil": "1.1.0", "nuevo": "2.0"})
    d = comparar(verde, actual)["dependencias"]
    assert d["fechautil"] == ("1.0.0", "1.1.0")
    assert d["nuevo"] == (None, "2.0")
    assert d["viejo"] == ("1.0", None)


def test_nombres_con_distinta_grafia_son_el_mismo_paquete():
    verde = huella(dependencias={"Foo_Bar": "1"})
    actual = huella(dependencias={"foo-bar": "2"})
    assert comparar(verde, actual)["dependencias"] == {"foo-bar": ("1", "2")}


def test_filas_ordena_dependencias_primero():
    verde = huella(dependencias={"a": "1"}, runner={"imagen_version": "1"})
    actual = huella(dependencias={"a": "2"}, runner={"imagen_version": "2"})
    categorias = [f[0] for f in filas(comparar(verde, actual))]
    assert categorias == ["dependencias", "runner"]


def test_archivos_y_referencias():
    verde = huella(archivos={"requirements.txt": "aaa"}, referencias={"x": "git+https://h/x@111"})
    actual = huella(archivos={"requirements.txt": "bbb"}, referencias={"x": "git+https://h/x@222"})
    d = comparar(verde, actual)
    assert d["archivos"]["requirements.txt"] == ("aaa", "bbb")
    assert d["referencias"]["x"] == ("git+https://h/x@111", "git+https://h/x@222")
