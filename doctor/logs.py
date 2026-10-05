"""Limpieza y recorte del log de un job para quedarse con la zona del error."""
from __future__ import annotations

import re

_TIMESTAMP = re.compile(r"^﻿?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z ?")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

PATRON_ERROR = re.compile(
    r"(##\[error\]|Traceback \(most recent call last\)|\b(?:ERROR|FAILED|FAIL)\b"
    r"|\b\w*Error\b|\bfatal:|\bException\b|command not found|No such file or directory"
    r"|Permission denied|timed out|AccessDenied|not authorized)"
)

_GENERICAS = ("Process completed with exit code",)


def limpiar(texto: str) -> str:
    """Quita marcas de tiempo, colores ANSI y retornos de carro."""
    salida = []
    for linea in texto.replace("\r", "").split("\n"):
        linea = _ANSI.sub("", _TIMESTAMP.sub("", linea))
        salida.append(linea.rstrip())
    return "\n".join(salida)


def extraer(texto: str, max_chars: int = 6000, antes: int = 60, despues: int = 5) -> str:
    """Devuelve la zona del log donde está el error (y no el log completo)."""
    lineas = texto.splitlines()
    if not lineas:
        return ""

    marcadas = [i for i, linea in enumerate(lineas) if "##[error]" in linea]
    if marcadas:
        ancla = marcadas[-1]
        ini, fin = max(0, ancla - antes), min(len(lineas), ancla + despues + 1)
    else:
        coincidencias = [i for i, linea in enumerate(lineas) if PATRON_ERROR.search(linea)]
        if coincidencias:
            ancla = coincidencias[0]
            ini, fin = max(0, ancla - 10), min(len(lineas), ancla + 40)
        else:
            ini, fin = max(0, len(lineas) - 60), len(lineas)

    bloque = "\n".join(lineas[ini:fin])
    if len(bloque) > max_chars:
        bloque = "…(recortado)…\n" + bloque[-max_chars:]
    return bloque


def linea_clave(extracto: str) -> str:
    """La línea más informativa del extracto, para el campo 'Síntomas'."""
    lineas = [linea.strip() for linea in extracto.splitlines() if linea.strip()]
    candidatas = [
        linea
        for linea in lineas
        if PATRON_ERROR.search(linea) and not any(g in linea for g in _GENERICAS)
    ]
    elegida = candidatas[-1] if candidatas else (lineas[-1] if lineas else "")
    elegida = elegida.replace("##[error]", "").strip()
    if elegida.startswith("E "):  # formato de pytest: "E   AttributeError: ..."
        elegida = elegida[1:].strip()
    return elegida[:300]
