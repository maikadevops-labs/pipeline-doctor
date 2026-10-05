"""Utilidades pequeñas compartidas por los demás módulos (solo librería estándar)."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from typing import List, Optional


def slug(texto) -> str:
    """Convierte un nombre en algo seguro para usar dentro de una clave de S3."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", str(texto)).strip("-").lower()
    return s or "x"


def ahora_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ejecutar(
    cmd: List[str],
    entrada: Optional[str] = None,
    timeout: int = 120,
    check: bool = True,
    env=None,
) -> subprocess.CompletedProcess:
    """Ejecuta un comando sin shell. Si falla, el error incluye un detalle corto."""
    r = subprocess.run(
        cmd,
        input=entrada,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if check and r.returncode != 0:
        detalle = (r.stderr or r.stdout or "").strip()[:500]
        raise RuntimeError(f"`{' '.join(cmd[:2])}` terminó con código {r.returncode}: {detalle}")
    return r


def hace(iso: Optional[str], ahora: Optional[datetime] = None) -> str:
    """Devuelve una frase como 'hace 18 h' a partir de una fecha ISO en UTC."""
    try:
        t = datetime.strptime(iso or "", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return "hace un tiempo"
    seg = int(((ahora or datetime.now(timezone.utc)) - t).total_seconds())
    if seg < 90:
        return "hace un momento"
    if seg < 5400:
        return f"hace {round(seg / 60)} min"
    if seg < 172800:
        return f"hace {round(seg / 3600)} h"
    return f"hace {round(seg / 86400)} días"
