"""Toma la "huella" del entorno de un job y la guarda en S3.

La huella usa una LISTA BLANCA: solo se registra lo que está definido aquí
(versiones de herramientas conocidas, paquetes instalados, hashes de archivos
de dependencias). Nunca se vuelcan todas las variables de entorno.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import platform
import re
import shlex
import sys
from typing import Dict, List, Optional

from . import s3
from .diff import normalizar_nombre
from .redact import redactar
from .util import ahora_iso, ejecutar

ESQUEMA = 1

# (nombre, comando). El primer número de versión que aparezca en la salida es el que se guarda.
HERRAMIENTAS_BASE = [
    ("pip", None),  # se resuelve con el mismo Python que ejecuta este script
    ("uv", ["uv", "--version"]),
    ("node", ["node", "--version"]),
    ("npm", ["npm", "--version"]),
    ("git", ["git", "--version"]),
    ("docker", ["docker", "--version"]),
    ("aws", ["aws", "--version"]),
    ("gh", ["gh", "--version"]),
    ("terraform", ["terraform", "version"]),
    ("kubectl", ["kubectl", "version", "--client"]),
    ("helm", ["helm", "version", "--short"]),
    ("java", ["java", "-version"]),
    ("go", ["go", "version"]),
]

PATRONES_ARCHIVOS_BASE = [
    "**/requirements*.txt",
    "**/constraints*.txt",
    "**/uv.lock",
    "**/poetry.lock",
    "**/Pipfile.lock",
    "**/pyproject.toml",
    "**/package-lock.json",
    "**/yarn.lock",
    "**/pnpm-lock.yaml",
    "**/Dockerfile",
    ".tool-versions",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
]
EXCLUIDOS = {".git", "node_modules", ".venv", "venv", ".tox", "__pycache__", "site-packages"}
MAX_ARCHIVOS = 200

_VERSION = re.compile(r"\d+(?:\.\d+)+")


def _version_de(salida: str) -> Optional[str]:
    m = _VERSION.search(salida or "")
    return m.group(0) if m else None


def _version_comando(cmd: List[str]) -> Optional[str]:
    try:
        r = ejecutar(cmd, timeout=10, check=False)
    except (OSError, ValueError):
        return None
    except Exception:  # tiempo agotado u otro problema: la herramienta simplemente no se registra
        return None
    if r.returncode != 0 and not (r.stdout or r.stderr):
        return None
    return _version_de((r.stdout or "") + "\n" + (r.stderr or ""))


def herramientas(extra: str = "") -> Dict[str, str]:
    """Versiones de las herramientas conocidas (solo las que existen en el runner)."""
    resultado = {"python": platform.python_version()}

    r = ejecutar([sys.executable, "-m", "pip", "--version"], timeout=20, check=False)
    pip = _version_de(r.stdout) if r.returncode == 0 else None
    if pip:
        resultado["pip"] = pip

    for nombre, cmd in HERRAMIENTAS_BASE:
        if cmd is None:
            continue
        v = _version_comando(cmd)
        if v:
            resultado[nombre] = v

    for linea in (extra or "").splitlines():
        linea = linea.strip()
        if not linea or "=" not in linea:
            continue
        nombre, comando = linea.split("=", 1)
        v = _version_comando(shlex.split(comando))
        if v:
            resultado[nombre.strip()] = v
    return resultado


def dependencias_python() -> Dict[str, Dict[str, str]]:
    """Paquetes instalados (incluye transitivos) y los que vienen de una URL."""
    versiones: Dict[str, str] = {}
    referencias: Dict[str, str] = {}

    r = ejecutar(
        [sys.executable, "-m", "pip", "list", "--format=json", "--disable-pip-version-check"],
        timeout=60,
        check=False,
    )
    if r.returncode == 0:
        try:
            for paquete in json.loads(r.stdout):
                versiones[normalizar_nombre(paquete["name"])] = paquete["version"]
        except (ValueError, KeyError, TypeError):
            pass

    r = ejecutar(
        [sys.executable, "-m", "pip", "freeze", "--disable-pip-version-check"],
        timeout=60,
        check=False,
    )
    if r.returncode == 0:
        for linea in r.stdout.splitlines():
            m = re.match(r"^([A-Za-z0-9_.-]+)\s*@\s*((?:git\+)?https?://\S+)", linea.strip())
            if m:
                referencias[normalizar_nombre(m.group(1))] = redactar(m.group(2))
    return {"versiones": versiones, "referencias": referencias}


def _hash_archivo(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def hashes_de_archivos(raiz: str, extra: str = "") -> Dict[str, str]:
    patrones = list(PATRONES_ARCHIVOS_BASE)
    patrones += [p.strip() for p in (extra or "").splitlines() if p.strip()]
    encontrados = {}
    for patron in patrones:
        for ruta in glob.glob(os.path.join(raiz, patron), recursive=True):
            relativa = os.path.relpath(ruta, raiz).replace(os.sep, "/")
            if set(relativa.split("/")) & EXCLUIDOS or not os.path.isfile(ruta):
                continue
            encontrados[relativa] = ruta
            if len(encontrados) >= MAX_ARCHIVOS:
                break
    return {rel: _hash_archivo(ruta) for rel, ruta in sorted(encontrados.items())}


def _rama_base(env) -> str:
    try:
        with open(env.get("GITHUB_EVENT_PATH", ""), encoding="utf-8") as f:
            return json.load(f)["repository"]["default_branch"]
    except (OSError, ValueError, KeyError):
        return "main"


def recolectar(env=None, raiz: Optional[str] = None, archivos_extra: str = "",
               herramientas_extra: str = "", job_status: str = "unknown") -> dict:
    env = os.environ if env is None else env
    raiz = raiz or env.get("GITHUB_WORKSPACE") or os.getcwd()
    deps = dependencias_python()
    return {
        "esquema": ESQUEMA,
        "contexto": {
            "repo": env.get("GITHUB_REPOSITORY", ""),
            "workflow": env.get("GITHUB_WORKFLOW", ""),
            "job": env.get("GITHUB_JOB", ""),
            "run_id": env.get("GITHUB_RUN_ID", ""),
            "run_number": env.get("GITHUB_RUN_NUMBER", ""),
            "run_attempt": env.get("GITHUB_RUN_ATTEMPT", "1"),
            "sha": env.get("GITHUB_SHA", ""),
            "ref": env.get("GITHUB_REF", ""),
            "evento": env.get("GITHUB_EVENT_NAME", ""),
            "rama_base": _rama_base(env),
            "job_status": (job_status or "unknown").lower(),
            "timestamp": ahora_iso(),
        },
        "runner": {
            "imagen_os": env.get("ImageOS", ""),
            "imagen_version": env.get("ImageVersion", ""),
            "runner_os": env.get("RUNNER_OS", platform.system()),
            "runner_arch": env.get("RUNNER_ARCH", platform.machine()),
            "kernel": platform.release(),
        },
        "herramientas": herramientas(herramientas_extra),
        "dependencias": deps["versiones"],
        "referencias": deps["referencias"],
        "archivos": hashes_de_archivos(raiz, archivos_extra),
    }


def debe_actualizar_verde(huella: dict) -> bool:
    """El puntero 'último verde' solo avanza con runs exitosos de la rama base."""
    c = huella["contexto"]
    return c["job_status"] == "success" and c["ref"] == f"refs/heads/{c['rama_base']}"


def _main() -> int:
    bucket = os.environ.get("PD_BUCKET", "")
    if not bucket:
        print("::warning title=Pipeline Doctor::Falta el input 'bucket'; no se guarda la huella.")
        return 0
    prefijo = os.environ.get("PD_PREFIJO") or s3.PREFIJO_POR_DEFECTO
    estado = os.environ.get("PD_JOB_STATUS", "unknown")
    if estado == "unknown":
        print("::warning title=Pipeline Doctor::No recibí 'job-status'; no se actualizará el último verde.")

    huella = recolectar(
        archivos_extra=os.environ.get("PD_ARCHIVOS", ""),
        herramientas_extra=os.environ.get("PD_HERRAMIENTAS_EXTRA", ""),
        job_status=estado,
    )
    c = huella["contexto"]
    clave = s3.clave_run(prefijo, c["repo"], c["workflow"], c["run_id"], c["run_attempt"], c["job"])
    s3.subir_json(bucket, clave, huella)
    print(
        f"Huella guardada ({len(huella['dependencias'])} paquetes, "
        f"{len(huella['herramientas'])} herramientas, {len(huella['archivos'])} archivos). "
        f"Estado del job: {c['job_status']}."
    )

    if debe_actualizar_verde(huella):
        s3.subir_json(bucket, s3.clave_verde(prefijo, c["repo"], c["workflow"], c["job"]), huella)
        print("Este run es verde en la rama base: actualicé la referencia 'último verde'.")
    return 0


def main() -> int:
    try:
        return _main()
    except Exception as e:  # la huella nunca debe romper tu pipeline
        print(f"::warning title=Pipeline Doctor::No pude guardar la huella: {str(e)[:300]}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
