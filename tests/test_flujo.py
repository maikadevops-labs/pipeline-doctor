"""Flujo completo con GitHub, S3 y Bedrock simulados: de "falló el job" a "comentario en el PR"."""
import json

from doctor import bedrock_client, diagnostico, informe, s3

LOG_JOB = """2026-10-05T12:00:02.5000000Z tests/test_agenda.py F.
2026-10-05T12:00:02.6000000Z E   AttributeError: module 'fechautil' has no attribute 'parse'
2026-10-05T12:00:02.7000000Z password=hunter2
2026-10-05T12:00:02.8000000Z ##[error]Process completed with exit code 1.
"""


def huella(job, status, version, sha, run_number, ts):
    return {
        "esquema": 1,
        "contexto": {
            "repo": "o/r", "workflow": "Demo", "job": job, "run_id": "1000",
            "run_number": run_number, "run_attempt": "1", "sha": sha, "ref": "refs/heads/main",
            "evento": "push", "rama_base": "main", "job_status": status, "timestamp": ts,
        },
        "runner": {"imagen_version": "1"},
        "herramientas": {"python": "3.12.1"},
        "dependencias": {"fechautil": version, "pytest": "8.3.5"},
        "referencias": {},
        "archivos": {"pacientes/requirements.txt": "aaa"},
    }


class GitHubFalso:
    def __init__(self, archivos_entre=None):
        self.comentarios = []
        self._archivos = archivos_entre or []

    def jobs_del_run(self, run_id, intento):
        return [
            {"id": 55, "name": "test", "conclusion": "failure",
             "steps": [{"name": "Set up job", "conclusion": "success"},
                       {"name": "Correr tests", "conclusion": "failure"}]},
            {"id": 56, "name": "lint", "conclusion": "success", "steps": []},
        ]

    def log_del_job(self, job_id):
        return LOG_JOB

    def archivos_entre(self, base, cabeza):
        return self._archivos

    def comentar(self, numero, cuerpo, marcador):
        self.comentarios.append((numero, cuerpo))
        return "creado"


def preparar(monkeypatch, tmp_path, modelo="", sha_actual="s2", archivos=None, con_verde=True):
    almacen = {
        "huellas/o/r/demo/runs/1000-1/test.json": huella("test", "failure", "1.1.0", sha_actual, "57", "2026-10-05T12:00:00Z"),
        "huellas/o/r/demo/runs/1000-1/lint.json": huella("lint", "success", "1.1.0", sha_actual, "57", "2026-10-05T12:00:00Z"),
    }
    if con_verde:
        almacen["huellas/o/r/demo/ultimo-verde/test.json"] = huella(
            "test", "success", "1.0.0", "s1", "56", "2026-10-04T12:00:00Z"
        )
    monkeypatch.setattr(s3, "listar", lambda b, p: [k for k in almacen if k.startswith(p)])
    monkeypatch.setattr(s3, "leer_json", lambda b, k: almacen.get(k))

    evento = tmp_path / "evento.json"
    evento.write_text(json.dumps({"pull_request": {"number": 12}}))
    resumen = tmp_path / "resumen.md"
    cfg = diagnostico.leer_config({
        "PD_BUCKET": "b", "PD_MODELO": modelo, "GITHUB_REPOSITORY": "o/r",
        "GITHUB_WORKFLOW": "Demo", "GITHUB_RUN_ID": "1000", "GITHUB_RUN_NUMBER": "57",
        "GITHUB_SHA": sha_actual, "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(evento), "GITHUB_STEP_SUMMARY": str(resumen),
    })
    return cfg, GitHubFalso(archivos), resumen


def test_flujo_sin_ia_codigo_identico(monkeypatch, tmp_path):
    cfg, gh, resumen = preparar(monkeypatch, tmp_path, sha_actual="s1")
    assert diagnostico._ejecutar(cfg, gh) == 0

    numero, cuerpo = gh.comentarios[0]
    assert numero == 12 and cuerpo.startswith(informe.MARCADOR)
    assert "**Tu código no cambió**" in cuerpo
    assert "| Dependencia `fechautil` | `1.0.0` | `1.1.0` |" in cuerpo
    assert "fechautil==1.0.0" in cuerpo
    assert "lint" not in cuerpo  # el job verde no se diagnostica
    assert "hunter2" not in cuerpo
    assert resumen.read_text().startswith(informe.MARCADOR)


def test_flujo_con_ia_usa_la_respuesta_del_modelo(monkeypatch, tmp_path):
    visto = {}

    def falso(modelo, region, sistema, usuario, max_tokens=1500):
        visto["usuario"] = usuario
        respuesta = {
            "sintomas": "Falla `fechautil.parse`.", "diagnostico": "La API de fechautil cambió en 1.1.0.",
            "descartado": ["runner: misma imagen"], "tratamiento": "Fija fechautil==1.0.0.",
            "validacion": "Debe pasar.", "confianza": "alta",
        }
        return json.dumps(respuesta), {"inputTokens": 10, "outputTokens": 5}

    monkeypatch.setattr(bedrock_client, "consultar", falso)
    cfg, gh, _ = preparar(monkeypatch, tmp_path, modelo="amazon.nova-lite-v1:0", sha_actual="s1")
    diagnostico._ejecutar(cfg, gh)

    cuerpo = gh.comentarios[0][1]
    assert "La API de fechautil cambió en 1.1.0." in cuerpo and "Modo sin IA" not in cuerpo
    # lo que viaja al modelo ya está limpio de secretos
    assert "hunter2" not in visto["usuario"] and "[REDACTED]" in visto["usuario"]
    assert "Se ocultaron 1 posible(s) secreto(s)" in cuerpo


def test_flujo_si_el_modelo_falla_cae_al_diagnostico_automatico(monkeypatch, tmp_path):
    def roto(*a, **k):
        raise RuntimeError("AccessDeniedException")

    monkeypatch.setattr(bedrock_client, "consultar", roto)
    cfg, gh, _ = preparar(monkeypatch, tmp_path, modelo="m", sha_actual="s1")
    diagnostico._ejecutar(cfg, gh)
    cuerpo = gh.comentarios[0][1]
    assert "No pude consultar el modelo" in cuerpo and "fechautil" in cuerpo


def test_flujo_con_codigo_cambiado(monkeypatch, tmp_path):
    cfg, gh, _ = preparar(monkeypatch, tmp_path, sha_actual="s2", archivos=["pacientes/app/agenda.py"])
    diagnostico._ejecutar(cfg, gh)
    assert "cambiaron 1 archivo(s)" in gh.comentarios[0][1]


def test_flujo_sin_run_verde(monkeypatch, tmp_path):
    cfg, gh, _ = preparar(monkeypatch, tmp_path, con_verde=False)
    diagnostico._ejecutar(cfg, gh)
    assert "Todavía no hay un run verde" in gh.comentarios[0][1]


def test_emparejar_por_nombre_y_por_unicidad():
    h = [huella("test", "failure", "1", "s", "1", "t")]
    assert diagnostico.emparejar({"name": "test"}, h, 1) is h[0]
    assert diagnostico.emparejar({"name": "Nombre bonito"}, h, 1) is h[0]
    assert diagnostico.emparejar({"name": "Nombre bonito"}, h, 2) is None


def test_si_no_hay_jobs_fallidos_no_hace_nada(monkeypatch, tmp_path):
    cfg, gh, _ = preparar(monkeypatch, tmp_path)
    gh.jobs_del_run = lambda *a: [{"id": 1, "name": "test", "conclusion": "success"}]
    assert diagnostico._ejecutar(cfg, gh) == 0 and gh.comentarios == []


def test_log_crudo_pide_permiso_para_secuencias_de_escape(monkeypatch):
    llamadas = []

    def falso(cmd, **kw):
        llamadas.append(cmd)

        class R:
            stdout = "\x1b[31mFAILED\x1b[0m"

        return R()

    from doctor import github_client

    monkeypatch.setattr(github_client, "ejecutar", falso)
    texto = github_client.GitHub("o/r", "t").log_del_job(1)
    assert "--allow-escape-sequences" in llamadas[0]
    assert "FAILED" in texto


def test_log_crudo_reintenta_si_gh_no_conoce_la_opcion(monkeypatch):
    llamadas = []

    def falso(cmd, **kw):
        llamadas.append(cmd)
        if "--allow-escape-sequences" in cmd:
            raise RuntimeError("`gh api` terminó con código 1: unknown flag: --allow-escape-sequences")

        class R:
            stdout = "ok"

        return R()

    from doctor import github_client

    monkeypatch.setattr(github_client, "ejecutar", falso)
    assert github_client.GitHub("o/r", "t").log_del_job(1) == "ok"
    assert len(llamadas) == 2
