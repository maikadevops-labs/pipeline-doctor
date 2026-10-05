"""Comparación determinística entre dos huellas (sin IA)."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

Cambio = Tuple[Optional[str], Optional[str]]  # (antes, después)

CATEGORIAS = ("dependencias", "referencias", "herramientas", "runner", "archivos")


def normalizar_nombre(nombre: str) -> str:
    """PEP 503: 'Foo_Bar' y 'foo-bar' son el mismo paquete."""
    return re.sub(r"[-_.]+", "-", nombre).lower()


def _cambios(antes: Dict[str, str], despues: Dict[str, str]) -> Dict[str, Cambio]:
    resultado: Dict[str, Cambio] = {}
    for clave in sorted(set(antes) | set(despues)):
        a, d = antes.get(clave), despues.get(clave)
        if a != d:
            resultado[clave] = (a, d)
    return resultado


def _normalizado(d: Dict[str, str]) -> Dict[str, str]:
    return {normalizar_nombre(k): v for k, v in d.items()}


def comparar(verde: dict, actual: dict) -> Dict[str, Dict[str, Cambio]]:
    """Qué cambió entre la huella del último run verde y la del run que falló."""
    return {
        "dependencias": _cambios(
            _normalizado(verde.get("dependencias", {})),
            _normalizado(actual.get("dependencias", {})),
        ),
        "referencias": _cambios(
            _normalizado(verde.get("referencias", {})),
            _normalizado(actual.get("referencias", {})),
        ),
        "herramientas": _cambios(verde.get("herramientas", {}), actual.get("herramientas", {})),
        "runner": _cambios(verde.get("runner", {}), actual.get("runner", {})),
        "archivos": _cambios(verde.get("archivos", {}), actual.get("archivos", {})),
    }


def hay_cambios(diff: Dict[str, Dict[str, Cambio]]) -> bool:
    return any(diff.get(c) for c in CATEGORIAS)


def filas(diff: Dict[str, Dict[str, Cambio]]) -> List[Tuple[str, str, Optional[str], Optional[str]]]:
    """Lista plana (categoría, nombre, antes, después), de lo más a lo menos relevante."""
    salida = []
    for categoria in CATEGORIAS:
        for nombre, (antes, despues) in diff.get(categoria, {}).items():
            salida.append((categoria, nombre, antes, despues))
    return salida
