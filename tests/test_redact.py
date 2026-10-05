"""Los secretos de prueba se arman por partes para que ningún escáner los confunda con reales."""
from doctor.redact import REDACTADO, redactar, redactar_contando


def test_llave_de_aws():
    clave = "AKIA" + "A" * 16
    assert clave not in redactar(f"usando {clave} para subir")


def test_token_de_github():
    token = "ghp_" + "a" * 36
    assert token not in redactar(f"token {token} listo")
    assert "github_pat_" + "x" * 30 not in redactar("github_pat_" + "x" * 30)


def test_jwt():
    jwt = "eyJ" + "a" * 10 + ".eyJ" + "b" * 10 + "." + "c" * 10
    assert jwt not in redactar(f"id_token={jwt}")


def test_bloque_de_clave_privada_multilinea():
    inicio = "-----BEGIN " + "RSA PRIVATE KEY-----"
    fin = "-----END " + "RSA PRIVATE KEY-----"
    texto = f"antes\n{inicio}\nMIIEabc\nxyz123\n{fin}\ndespués"
    salida = redactar(texto)
    assert "MIIEabc" not in salida and "antes" in salida and "después" in salida


def test_asignaciones_con_nombre_sospechoso():
    salida = redactar("aws_secret_access_key = wJalrXUtnFEMI\nDB_PASSWORD: hunter2\napi_key='abc123'")
    for secreto in ("wJalrXUtnFEMI", "hunter2", "abc123"):
        assert secreto not in salida
    assert "DB_PASSWORD" in salida  # el nombre se conserva, solo se oculta el valor


def test_bearer_y_authorization():
    salida = redactar("Authorization: Bearer abcdefghijklmnop")
    assert "abcdefghijklmnop" not in salida


def test_url_con_credenciales():
    salida = redactar("git clone https://usuario:clave123@github.com/x/y.git")
    assert "clave123" not in salida and "github.com/x/y.git" in salida


def test_texto_normal_no_se_toca():
    texto = "ModuleNotFoundError: No module named 'fechautil'\nE   AttributeError: parse"
    assert redactar(texto) == texto


def test_no_vuelve_a_contar_lo_ya_oculto():
    texto, n1 = redactar_contando("password=hunter2")
    _, n2 = redactar_contando(texto)
    assert n1 == 1 and n2 == 0 and REDACTADO in texto


def test_valor_enmascarado_por_github_no_cuenta():
    _, n = redactar_contando("token: ***")
    assert n == 0
