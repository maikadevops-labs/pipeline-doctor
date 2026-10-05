"""Orquestador de la consulta: se ejecuta en el job `doctor`, solo cuando algo falló."""
from __future__ import annotations

import json
from collections import Counter
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

from . import bedrock_client, diff as difmod, informe, logs, prompt, redact, s3, sospechosos
from .github_client import GitHub
from .util import slug

MAX_JOBS = 3
MAX_LOG_CRUDO = 2_000_000


@dataclass
class Config:
    bucket: str
    prefijo: str
    modelo: str
    region_bedrock: str
    token: str
    repo: str
    workflow: str
    run_id: str
    run_number: str
    intento: str
    sha: str
    evento: str
    evento_path: str
    server: str
    resumen_path: str


def leer_config(env=None) -> Config:
    e = os.environ if env is None else env
    return Config(
        bucket=e.get("PD_BUCKET", ""),
        prefijo=e.get("PD_PREFIJO") or s3.PREFIJO_POR_DEFECTO,
        modelo=e.get("PD_MODELO", "").strip(),
        region_bedrock=e.get("PD_REGION_BEDROCK", "").strip(),
        token=e.get("PD_GITHUB_TOKEN", ""),
        repo=e.get("GITHUB_REPOSITORY", ""),
        workflow=e.get("GITHUB_WORKFLOW", ""),
        run_id=e.get("GITHUB_RUN_ID", ""),
        run_number=e.get("GITHUB_RUN_NUMBER", ""),
        intento=e.get("GITHUB_RUN_ATTEMPT", "1"),
        sha=e.get("GITHUB_SHA", ""),
        evento=e.get("GITHUB_EVENT_NAME", ""),
        evento_path=e.get("GITHUB_EVENT_PATH", ""),
        server=e.get("GITHUB_SERVER_URL", "https://github.com"),
        resumen_path=e.get("GITHUB_STEP_SUMMARY", ""),
    )


# --- piezas ---------------------------------------------------------------------------


def huellas_fallidas_del_run(cfg: Config) -> List[dict]:
    """Huellas guardadas por este run cuyo job terminó en failure."""
    claves = s3.listar(cfg.bucket, s3.prefijo_run(cfg.prefijo, cfg.repo, cfg.workflow, cfg.run_id, cfg.intento))
    huellas = []
    for clave in claves[:20]:
        h = s3.leer_json(cfg.bucket, clave)
        if h and h.get("contexto", {}).get("job_status") == "failure":
            huellas.append(h)
    return huellas


def emparejar(job: dict, huellas: List[dict], total_fallidos: int) -> Optional[dict]:
    """Une el job que reporta la API con la huella que guardó el propio job."""
    por_nombre = [h for h in huellas if slug(h["contexto"].get("job")) == slug(job.get("name"))]
    if por_nombre:
        return por_nombre[0]
    if len(huellas) == 1 and total_fallidos == 1:
        return huellas[0]
    return None


def comparar_codigo(cfg: Config, gh: GitHub, verde: dict) -> dict:
    sha_verde = verde["contexto"].get("sha", "")
    if sha_verde and sha_verde == cfg.sha:
        return {"identico": True, "archivos": []}
    try:
        return {"identico": False, "archivos": gh.archivos_entre(sha_verde, cfg.sha)}
    except Exception as e:  # el commit base puede no existir (force-push) o faltar permisos
        print(f"::warning title=Pipeline Doctor::No pude comparar el código: {str(e)[:200]}")
        return {"identico": False, "archivos": None}


def evidencia_para_modelo(ctx: dict) -> dict:
    verde = ctx.get("verde")
    cambios = [
        {"categoria": c, "nombre": n, "antes": a, "despues": d}
        for c, n, a, d in (difmod.filas(ctx["diff"]) if ctx.get("diff") else [])
    ][:40]
    codigo = ctx.get("codigo")
    return {
        "job": ctx["job"],
        "paso_fallido": ctx.get("paso"),
        "evento": ctx.get("evento"),
        "ultimo_verde": (
            {"run": verde.get("run_number"), "commit": (verde.get("sha") or "")[:7]} if verde else None
        ),
        "codigo": (
            None
            if codigo is None
            else {
                "mismo_commit": codigo.get("identico"),
                "archivos_cambiados": (codigo.get("archivos") or [])[:30]
                if codigo.get("archivos") is not None
                else "no se pudo comparar",
            }
        ),
        "cambios_de_entorno": cambios,
        "pistas_automaticas": [
            {"nivel": s["nivel"], "titulo": s["titulo"], "evidencia": s["evidencia"]}
            for s in ctx["sospechosos"]
        ],
    }


def consultar_modelo(cfg: Config, ctx: dict, extracto: str):
    """Devuelve (analisis | None, error | None)."""
    if not cfg.modelo:
        return None, None
    try:
        texto, uso = bedrock_client.consultar(
            cfg.modelo,
            cfg.region_bedrock or None,
            prompt.SISTEMA,
            prompt.construir_usuario(evidencia_para_modelo(ctx), extracto),
        )
        analisis = bedrock_client.parsear_json(texto)
        if analisis is None:
            analisis = {"diagnostico": texto[: informe.MAX_CAMPO_IA]}
        print(f"Bedrock respondió ({uso.get('inputTokens', '?')} tokens de entrada, "
              f"{uso.get('outputTokens', '?')} de salida).")
        return analisis, None
    except Exception as e:
        print(f"::warning title=Pipeline Doctor::No pude consultar Bedrock: {str(e)[:400]}")
        return None, str(e)[:200]


def diagnosticar_job(cfg: Config, gh: GitHub, job: dict, huellas: List[dict], total_fallidos: int) -> str:
    paso = next((s["name"] for s in job.get("steps", []) if s.get("conclusion") == "failure"), None)

    try:
        crudo = gh.log_del_job(job["id"])[-MAX_LOG_CRUDO:]
    except Exception as e:
        print(f"::warning title=Pipeline Doctor::No pude descargar el log del job: {str(e)[:200]}")
        crudo = ""
    limpio, hallazgos = redact.redactar_detalle(logs.limpiar(crudo))
    redacciones = len(hallazgos)
    if hallazgos:
        # Solo tipos y nombres de variables, nunca valores: sirve para detectar falsos positivos.
        resumen_hallazgos = ", ".join(f"{t} (x{n})" for t, n in sorted(Counter(hallazgos).items()))
        print(f"::notice title=Pipeline Doctor::Ocultado en el log antes del análisis: {resumen_hallazgos}")
    extracto = logs.extraer(limpio)

    huella = emparejar(job, huellas, total_fallidos)
    verde = diff = codigo = None
    if huella:
        c = huella["contexto"]
        verde = s3.leer_json(cfg.bucket, s3.clave_verde(cfg.prefijo, cfg.repo, cfg.workflow, c["job"]))
        if verde:
            diff = difmod.comparar(verde, huella)
            codigo = comparar_codigo(cfg, gh, verde)

    ctx = {
        "run_id": cfg.run_id,
        "run_number": cfg.run_number,
        "run_url": f"{cfg.server}/{cfg.repo}/actions/runs/{cfg.run_id}",
        "evento": cfg.evento,
        "job": job.get("name", ""),
        "paso": paso,
        "linea_error": logs.linea_clave(extracto),
        "verde": verde["contexto"] if verde else None,
        "huella_actual": huella is not None,
        "diff": diff,
        "codigo": codigo,
        "redacciones": redacciones,
        "modelo": cfg.modelo or None,
    }
    ctx["sospechosos"] = sospechosos.generar(
        diff, extracto, codigo["archivos"] if codigo else None
    )

    analisis, error = consultar_modelo(cfg, ctx, extracto)
    ctx["ia_error"] = error
    return informe.construir(ctx, analisis)


# --- flujo principal -------------------------------------------------------------------


def numero_de_pr(cfg: Config) -> Optional[int]:
    if cfg.evento != "pull_request":
        return None
    try:
        with open(cfg.evento_path, encoding="utf-8") as f:
            return int(json.load(f)["pull_request"]["number"])
    except (OSError, ValueError, KeyError):
        return None


def _ejecutar(cfg: Config, gh: Optional[GitHub] = None) -> int:
    if not cfg.bucket:
        print("::warning title=Pipeline Doctor::Falta el input 'bucket'.")
        return 0
    gh = gh or GitHub(cfg.repo, cfg.token)

    jobs = gh.jobs_del_run(cfg.run_id, cfg.intento)
    fallidos = [j for j in jobs if j.get("conclusion") == "failure"]
    if not fallidos:
        print("No encontré jobs fallidos en este run: no hay nada que diagnosticar.")
        return 0

    huellas = huellas_fallidas_del_run(cfg)
    secciones = [diagnosticar_job(cfg, gh, j, huellas, len(fallidos)) for j in fallidos[:MAX_JOBS]]
    cuerpo = informe.envolver(secciones)

    if cfg.resumen_path:
        with open(cfg.resumen_path, "a", encoding="utf-8") as f:
            f.write(cuerpo + "\n")
    print("::group::Informe de Pipeline Doctor")
    print(informe.texto_plano(cuerpo))
    print("::endgroup::")
    print("::notice title=Pipeline Doctor::Informe publicado en la pestaña Summary del run.")

    numero = numero_de_pr(cfg)
    if numero:
        try:
            accion = gh.comentar(numero, cuerpo, informe.MARCADOR)
            print(f"Comentario {accion} en el PR #{numero}.")
        except Exception as e:  # por ejemplo, PRs desde forks no tienen permiso de escritura
            print(f"::warning title=Pipeline Doctor::No pude comentar en el PR: {str(e)[:200]}")
    return 0


def main() -> int:
    try:
        return _ejecutar(leer_config())
    except Exception as e:
        print(f"::warning title=Pipeline Doctor::No pude completar el diagnóstico: {str(e)[:300]}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
