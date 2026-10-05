"""Acceso a S3 usando el AWS CLI (ya viene instalado en los runners de GitHub).

Se usa el CLI y no boto3 a propósito: así Pipeline Doctor no instala nada en el
entorno del job y no "contamina" la huella que está midiendo.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import List, Optional

from .util import ejecutar, slug

PREFIJO_POR_DEFECTO = "huellas"


def clave_run(prefijo: str, repo: str, workflow: str, run_id, intento, job: str) -> str:
    return f"{prefijo}/{repo}/{slug(workflow)}/runs/{run_id}-{intento}/{slug(job)}.json"


def prefijo_run(prefijo: str, repo: str, workflow: str, run_id, intento) -> str:
    return f"{prefijo}/{repo}/{slug(workflow)}/runs/{run_id}-{intento}/"


def clave_verde(prefijo: str, repo: str, workflow: str, job: str) -> str:
    return f"{prefijo}/{repo}/{slug(workflow)}/ultimo-verde/{slug(job)}.json"


def subir_json(bucket: str, clave: str, datos: dict) -> None:
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "huella.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1, sort_keys=True)
        ejecutar(
            [
                "aws", "s3", "cp", ruta, f"s3://{bucket}/{clave}",
                "--only-show-errors", "--content-type", "application/json",
            ]
        )


def leer_json(bucket: str, clave: str) -> Optional[dict]:
    """Devuelve el JSON guardado, o None si no existe."""
    r = ejecutar(
        ["aws", "s3", "cp", f"s3://{bucket}/{clave}", "-", "--only-show-errors"],
        check=False,
    )
    if r.returncode != 0:
        detalle = (r.stderr or "").strip()
        if "404" not in detalle and "does not exist" not in detalle:
            print(f"::warning title=Pipeline Doctor::No pude leer {clave}: {detalle[:200]}")
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def listar(bucket: str, prefijo: str) -> List[str]:
    r = ejecutar(
        [
            "aws", "s3api", "list-objects-v2", "--bucket", bucket,
            "--prefix", prefijo, "--query", "Contents[].Key", "--output", "json",
        ]
    )
    return json.loads(r.stdout or "null") or []
