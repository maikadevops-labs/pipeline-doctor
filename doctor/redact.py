"""Oculta secretos probables antes de enviar un texto a un modelo o de publicarlo.

Es deliberadamente agresivo: prefiere ocultar de más (falsos positivos) a dejar
pasar una credencial. GitHub ya enmascara los secretos registrados como `***`,
pero no todo lo que aparece en un log es un secreto registrado.
"""
from __future__ import annotations

import re
from typing import List, Tuple

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

_NO_SON_SECRETOS = {"true", "false", "yes", "no", "on", "off", "null", "none", "basic", "bearer", "token"}

_URL_CON_CREDENCIALES = re.compile(r"\b([A-Za-z][A-Za-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@")
_BEARER = re.compile(r"\b([Bb]earer|[Bb]asic)\s+[A-Za-z0-9._~+/=-]{8,}")
_ASIGNACION = re.compile(
    r"(\b[\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key"
    r"|private[_-]?key|credential|authorization)[\w.-]*)"
    r"(\s*[:=]\s*)"
    r"(\"[^\"\n]*\"|'[^'\n]*'|[^\s,;]+)",
    re.IGNORECASE,
)


_ETIQUETAS_TOKEN = [
    "llave de acceso de AWS",
    "token de GitHub",
    "token fino de GitHub",
    "token de GitLab",
    "token de Slack",
    "llave de API de Google",
    "llave tipo sk-",
    "JWT",
]


def redactar_detalle(texto: str) -> Tuple[str, List[str]]:
    """Devuelve (texto_limpio, hallazgos). Los hallazgos describen el TIPO (y el nombre de la
    variable, si la hay), nunca el valor: sirven para depurar falsos positivos sin filtrar nada."""
    hallazgos: List[str] = []

    def simple(etiqueta):
        def _sub(_m):
            hallazgos.append(etiqueta)
            return REDACTADO

        return _sub

    texto = _BLOQUE_CLAVE_PRIVADA.sub(simple("clave privada"), texto)

    def url(m):
        hallazgos.append("URL con credenciales")
        return f"{m.group(1)}{REDACTADO}@"

    texto = _URL_CON_CREDENCIALES.sub(url, texto)

    def bearer(m):
        hallazgos.append("cabecera Bearer/Basic")
        return f"{m.group(1)} {REDACTADO}"

    texto = _BEARER.sub(bearer, texto)

    for patron, etiqueta in zip(_TOKENS, _ETIQUETAS_TOKEN):
        texto = patron.sub(simple(etiqueta), texto)

    def asignacion(m):
        valor = m.group(3).strip("\"'")
        if valor in (REDACTADO, "") or valor.startswith("***"):
            return m.group(0)
        # Opciones y palabras de esquema, no secretos: `persist-credentials: true`, `Authorization: basic ***`.
        if valor.lower() in _NO_SON_SECRETOS:
            return m.group(0)
        hallazgos.append(f"valor de la variable '{m.group(1)[:40]}'")
        return f"{m.group(1)}{m.group(2)}{REDACTADO}"

    texto = _ASIGNACION.sub(asignacion, texto)
    return texto, hallazgos


def redactar_contando(texto: str) -> Tuple[str, int]:
    """Devuelve (texto_limpio, cantidad_de_cosas_ocultadas)."""
    limpio, hallazgos = redactar_detalle(texto)
    return limpio, len(hallazgos)


def redactar(texto: str) -> str:
    return redactar_detalle(texto)[0]
