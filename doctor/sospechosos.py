"""Sospechosos automáticos (sin IA): ordenados por cuánta evidencia los respalda.

Es el diagnóstico de respaldo cuando no hay modelo configurado, y también la
"pista" que se le entrega al modelo para que explique en vez de adivinar.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

from .diff import Cambio
from .logs import PATRON_ERROR

ORDEN = {"alta": 0, "media": 1, "baja": 2}


def _lineas_de_error(log: str) -> str:
    """Solo las líneas que hablan del error (así 'pytest -q' no cuenta como mención de pytest)."""
    relevantes = [
        linea
        for linea in (log or "").splitlines()
        if PATRON_ERROR.search(linea) or "site-packages" in linea or linea.lstrip().startswith("File ")
    ]
    return "\n".join(relevantes).lower()


def _mencionado(nombre: str, log: str) -> bool:
    texto = _lineas_de_error(log)
    return nombre in texto or nombre.replace("-", "_") in texto


def _archivo_mencionado(ruta: str, log: str) -> bool:
    """¿El log nombra este archivo? 'agenda.py' no cuenta si el log dice 'test_agenda.py'."""
    log = log or ""
    if ruta in log:
        return True
    base = re.escape(os.path.basename(ruta))
    return re.search(rf"(?<![\w.-]){base}(?!\w)", log) is not None


def _sha_corto(url: Optional[str]) -> str:
    if not url:
        return "—"
    return url.rsplit("@", 1)[-1][:7]


def _desc(antes: Optional[str], despues: Optional[str]) -> str:
    if antes is None:
        return f"apareció (versión {despues})"
    if despues is None:
        return f"ya no está instalada (era {antes})"
    return f"cambió de {antes} a {despues}"


def generar(
    diff: Optional[Dict[str, Dict[str, Cambio]]],
    log: str,
    archivos_codigo: Optional[List[str]],
) -> List[dict]:
    sospechosos: List[dict] = []

    if diff:
        deps = diff.get("dependencias", {})
        refs = diff.get("referencias", {})
        otras = []
        for nombre, (antes, despues) in deps.items():
            if _mencionado(nombre, log):
                extra = ""
                if nombre in refs:
                    a, d = refs[nombre]
                    extra = f" (commit de origen: {_sha_corto(a)} → {_sha_corto(d)})"
                if antes is not None and despues is not None:
                    tratamiento = (
                        f"Fija `{nombre}=={antes}` en tus requisitos mientras adaptas el código "
                        f"a la versión {despues}."
                    )
                    validacion = (
                        f"En el próximo run, la huella debe mostrar `{nombre}` en {antes} "
                        "y el paso que falló debe pasar."
                    )
                elif despues is None:
                    tratamiento = f"Vuelve a agregar `{nombre}` a tus requisitos."
                    validacion = f"La huella debe volver a listar `{nombre}` {antes}."
                else:
                    tratamiento = (
                        f"Revisa si el error viene del uso de `{nombre}` {despues}, que es nueva."
                    )
                    validacion = "El paso que falló debe pasar tras ajustar el uso de la dependencia."
                sospechosos.append(
                    {
                        "nivel": "alta",
                        "titulo": f"`{nombre}` {_desc(antes, despues)}{extra}",
                        "evidencia": "Su nombre aparece en el error del log.",
                        "tratamiento": tratamiento,
                        "validacion": validacion,
                    }
                )
            else:
                otras.append((nombre, antes, despues))
        if otras:
            lista = ", ".join(f"`{n}` {_desc(a, d)}" for n, a, d in otras[:5])
            mas = f" y {len(otras) - 5} más" if len(otras) > 5 else ""
            sospechosos.append(
                {
                    "nivel": "media",
                    "titulo": f"Cambiaron {len(otras)} dependencia(s) que no aparecen en el error",
                    "evidencia": lista + mas,
                    "tratamiento": (
                        "Compara las versiones de la tabla y fija las que estén relacionadas "
                        "con el paso que falló."
                    ),
                    "validacion": "El paso que falló debe pasar con las versiones fijadas.",
                }
            )

        entorno = list(diff.get("herramientas", {}).items()) + list(diff.get("runner", {}).items())
        if entorno:
            lista = ", ".join(f"`{n}` {_desc(a, d)}" for n, (a, d) in entorno[:5])
            sospechosos.append(
                {
                    "nivel": "media",
                    "titulo": "Cambió el entorno del runner o de las herramientas",
                    "evidencia": lista,
                    "tratamiento": (
                        "Fija la versión de la herramienta afectada (por ejemplo con "
                        "`setup-python` o una imagen de contenedor) o pasa a un runner con "
                        "imagen fija."
                    ),
                    "validacion": "La huella del próximo run debe mostrar la versión fijada.",
                }
            )

        archivos = list(diff.get("archivos", {}).items())
        if archivos:
            lista = ", ".join(f"`{n}`" for n, _ in archivos[:5])
            sospechosos.append(
                {
                    "nivel": "media",
                    "titulo": "Cambiaron archivos de dependencias o del workflow",
                    "evidencia": lista,
                    "tratamiento": "Revisa el diff de esos archivos en los commits entre ambos runs.",
                    "validacion": "Tras corregirlos, el job debe pasar.",
                }
            )

    if archivos_codigo:
        mencionados = [a for a in archivos_codigo if _archivo_mencionado(a, log)]
        if mencionados:
            sospechosos.append(
                {
                    "nivel": "alta",
                    "titulo": "El código cambió y el error apunta a esos archivos",
                    "evidencia": ", ".join(f"`{a}`" for a in mencionados[:5]),
                    "tratamiento": "Revisa los cambios de esos archivos en tu PR: ahí está la causa.",
                    "validacion": "Corrige el cambio y vuelve a correr el job: debe pasar.",
                }
            )
        else:
            sospechosos.append(
                {
                    "nivel": "media",
                    "titulo": f"El código cambió en {len(archivos_codigo)} archivo(s)",
                    "evidencia": ", ".join(f"`{a}`" for a in archivos_codigo[:5]),
                    "tratamiento": "Revisa esos cambios: el error puede ser un efecto indirecto.",
                    "validacion": "Tras corregirlo, el job debe pasar.",
                }
            )

    if not sospechosos:
        sospechosos.append(
            {
                "nivel": "baja",
                "titulo": "No encontré diferencias detectables",
                "evidencia": (
                    "El entorno y el código son iguales al último run verde. "
                    "Puede ser un test intermitente, un servicio externo o la red."
                ),
                "tratamiento": "Reintenta el job; si vuelve a fallar, revisa dependencias externas.",
                "validacion": "Si pasa al reintentar, trátalo como un fallo intermitente.",
            }
        )

    sospechosos.sort(key=lambda s: ORDEN[s["nivel"]])
    return sospechosos
