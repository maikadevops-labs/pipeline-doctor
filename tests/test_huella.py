import json

from doctor import huella, s3


def entorno(tmp_path, **extra):
    evento = tmp_path / "evento.json"
    evento.write_text(json.dumps({"repository": {"default_branch": "main"}}))
    env = {
        "GITHUB_REPOSITORY": "maikadevops-labs/pipeline-doctor",
        "GITHUB_WORKFLOW": "Demo paciente",
        "GITHUB_JOB": "test",
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_NUMBER": "7",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "abc123",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_EVENT_PATH": str(evento),
        "ImageOS": "ubuntu24",
        "ImageVersion": "20260928.1.0",
        "SECRETO_DEL_ENTORNO": "no-debe-aparecer",
    }
    env.update(extra)
    return env


def test_la_huella_usa_lista_blanca_y_no_vuelca_el_entorno(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest==8.3.5\n")
    h = huella.recolectar(env=entorno(tmp_path), raiz=str(tmp_path), job_status="success")
    assert "no-debe-aparecer" not in json.dumps(h)
    assert h["contexto"]["workflow"] == "Demo paciente"
    assert h["runner"]["imagen_version"] == "20260928.1.0"
    assert "python" in h["herramientas"]
    assert "pytest" in h["dependencias"]  # pytest corre estos tests, así que está instalado
    assert "requirements.txt" in h["archivos"] and len(h["archivos"]["requirements.txt"]) == 64


def test_hashes_ignoran_carpetas_excluidas(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "package-lock.json").write_text("{}")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "requirements-dev.txt").write_text("x")
    assert list(huella.hashes_de_archivos(str(tmp_path))) == ["app/requirements-dev.txt"]


def test_archivos_extra(tmp_path):
    (tmp_path / "datos.cfg").write_text("x")
    assert "datos.cfg" in huella.hashes_de_archivos(str(tmp_path), extra="*.cfg")


def test_el_puntero_verde_solo_avanza_en_la_rama_base(tmp_path):
    base = huella.recolectar(env=entorno(tmp_path), raiz=str(tmp_path), job_status="success")
    assert huella.debe_actualizar_verde(base)

    fallo = huella.recolectar(env=entorno(tmp_path), raiz=str(tmp_path), job_status="failure")
    assert not huella.debe_actualizar_verde(fallo)

    pr = huella.recolectar(
        env=entorno(tmp_path, GITHUB_REF="refs/pull/5/merge", GITHUB_EVENT_NAME="pull_request"),
        raiz=str(tmp_path),
        job_status="success",
    )
    assert not huella.debe_actualizar_verde(pr)


def test_claves_de_s3():
    assert s3.clave_run("huellas", "o/r", "Demo paciente", 1, 2, "test") == (
        "huellas/o/r/demo-paciente/runs/1-2/test.json"
    )
    assert s3.clave_verde("huellas", "o/r", "Demo paciente", "test") == (
        "huellas/o/r/demo-paciente/ultimo-verde/test.json"
    )
