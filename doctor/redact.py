"""Oculta secretos probables antes de enviar un texto a un modelo o de publicarlo.

Es deliberadamente agresivo: prefiere ocultar de más (falsos positivos) a dejar
pasar una credencial. GitHub ya enmascara los secretos registrados como `***`,
pero no todo lo que aparece en un log es un secreto registrado.
"""
from __future__ import annotations

import re
from typing import Tuple

REDACTADO = "[REDACTED]"

_BLOQUE_CLAVE_PRIVADA = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)

# Formatos de token con prefijo reconocible.
_TOKENS = [
    re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA)[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),  # GitHub
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),  # GitHub fine-grained
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),  # GitLab
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),  # Slack
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),  # Google API key
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),  # claves tipo "sk-..."
    re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"),  # JWT
]

_URL_CON_CREDENCIALES = re.compile(r"\b([A-Za-z][A-Za-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@")
_BEARER = re.compile(r"\b([Bb]earer|[Bb]asic)\s+[A-Za-z0-9._~+/=-]{8,}")
_ASIGNACION = re.compile(
    r"(\b[\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key"
    r"|private[_-]?key|credential|authorization)[\w.-]*)"
    r"(\s*[:=]\s*)"
    r"(\"[^\"\n]*\"|'[^'\n]*'|[^\s,;]+)",
    re.IGNORECASE,
)


def redactar_contando(texto: str) -> Tuple[str, int]:
    """Devuelve (texto_limpio, cantidad_de_cosas_ocultadas)."""
    total = 0

    def contar(_m):
        nonlocal total
        total += 1
        return REDACTADO

    texto = _BLOQUE_CLAVE_PRIVADA.sub(contar, texto)

    def url(m):
        nonlocal total
        total += 1
        return f"{m.group(1)}{REDACTADO}@"

    texto = _URL_CON_CREDENCIALES.sub(url, texto)

    def bearer(m):
        nonlocal total
        total += 1
        return f"{m.group(1)} {REDACTADO}"

    texto = _BEARER.sub(bearer, texto)

    for patron in _TOKENS:
        texto = patron.sub(contar, texto)

    def asignacion(m):
        nonlocal total
        valor = m.group(3).strip("\"'")
        if valor in (REDACTADO, "***", ""):
            return m.group(0)
        total += 1
        return f"{m.group(1)}{m.group(2)}{REDACTADO}"

    texto = _ASIGNACION.sub(asignacion, texto)
    return texto, total


def redactar(texto: str) -> str:
    return redactar_contando(texto)[0]
