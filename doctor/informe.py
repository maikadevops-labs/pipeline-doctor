"""Arma el informe en Markdown: síntomas → historial → diagnóstico → tratamiento → validación."""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from .diff import filas, hay_cambios
from .util import hace

MARCADOR = "<!-- pipeline-doctor -->"
MAX_FILAS = 12
MAX_CAMPO_IA = 900
CONFIANZAS = ("alta", "media", "baja")


# --- limpieza del texto que escribe el modelo --------------------------------------------

_IMAGEN_O_ENLACE = re.compile(r"!?\[([^\]]*)\]\((?:https?:)?//[^)]*\)")
_URL = re.compile(r"https?://\S+")
_MENCION = re.compile(r"@(?=[A-Za-z0-9_-])")


def texto_ia(valor, max_len: int = MAX_CAMPO_IA) -> str:
    """Neutraliza enlaces, imágenes, menciones y comentarios HTML del texto del modelo."""
    s = str(valor or "").strip()
    s = _IMAGEN_O_ENLACE.sub(r"\1", s)
    s = _URL.sub("[enlace omitido]", s)
    s = _MENCION.sub("@​", s)
    s = s.replace("<!--", "").replace("-->", "")
    return s[:max_len]


# --- piezas ---------------------------------------------------------------------------


def _celda(valor: Optional[str], categoria: str, vacio: str) -> str:
    if valor is None:
        return vacio
    if categoria == "archivos":
        valor = valor[:8]
    elif categoria == "referencias":
        valor = valor.rsplit("@", 1)[-1][:7]
    return "`" + valor.replace("|", "\\|").replace("`", "'") + "`"


_ETIQUETA = {
    "dependencias": "Dependencia",
    "referencias": "Origen (commit)",
    "herramientas": "Herramienta",
    "runner": "Runner",
    "archivos": "Archivo",
}


def tabla_cambios(diff: Dict, verde_n, actual_n) -> str:
    lista = filas(diff)
    encabezado = (
        f"| Qué | Último verde (#{verde_n}) | Este run (#{actual_n}) |\n|---|---|---|\n"
    )
    cuerpo = []
    for categoria, nombre, antes, despues in lista[:MAX_FILAS]:
        nombre_md = nombre.replace("|", "\\|").replace("`", "'")
        cuerpo.append(
            f"| {_ETIQUETA[categoria]} `{nombre_md}` "
            f"| {_celda(antes, categoria, '(no estaba)')} "
            f"| {_celda(despues, categoria, '(ya no está)')} |"
        )
    resto = len(lista) - MAX_FILAS
    if resto > 0:
        cuerpo.append(f"| …y {resto} cambio(s) más | | |")
    return encabezado + "\n".join(cuerpo)


def frase_codigo(codigo: Optional[dict], verde_n, actual_n) -> str:
    if codigo is None:
        return ""
    if codigo.get("identico"):
        return f"**Tu código no cambió** entre #{verde_n} y #{actual_n} (mismo commit)."
    archivos = codigo.get("archivos")
    if archivos is None:
        return f"No pude comparar el código entre #{verde_n} y #{actual_n}."
    if not archivos:
        return f"**Tu código no cambió** entre #{verde_n} y #{actual_n} (ningún archivo distinto)."
    muestra = ", ".join(f"`{a}`" for a in archivos[:8])
    mas = f" y {len(archivos) - 8} más" if len(archivos) > 8 else ""
    return f"Entre #{verde_n} y #{actual_n} **cambiaron {len(archivos)} archivo(s)**: {muestra}{mas}."


# --- informe de un job -------------------------------------------------------------------


def construir(ctx: dict, analisis: Optional[dict] = None) -> str:
    """ctx: datos del run/job. analisis: respuesta (ya parseada) del modelo, si hubo."""
    sospechosos: List[dict] = ctx["sospechosos"]
    principal = sospechosos[0]
    verde = ctx.get("verde")
    run_n = ctx.get("run_number") or ctx.get("run_id")
    analisis = analisis or {}

    # Cada elemento es un párrafo: así se ve igual en un comentario de PR y en el resumen del job.
    lineas = [f"### 🩺 Pipeline Doctor: consulta del run #{run_n}"]
    if ctx.get("run_url"):
        lineas[0] += f" ([ver run]({ctx['run_url']}))"

    # Síntomas
    paso = ctx.get("paso")
    donde = f"el job `{ctx['job']}` falló" + (f" en el paso *{paso}*" if paso else "")
    sintoma = texto_ia(analisis.get("sintomas")) or (
        f"`{ctx['linea_error']}`" if ctx.get("linea_error") else ""
    )
    lineas.append(f"**Síntomas:** {donde}." + (f" {sintoma}" if sintoma else ""))

    # Historial
    if verde:
        verde_n = verde.get("run_number") or verde.get("run_id")
        lineas.append(
            f"**Historial:** último run verde: #{verde_n} ({hace(verde.get('timestamp'))}). "
            + frase_codigo(ctx.get("codigo"), verde_n, run_n)
        )
        diff = ctx.get("diff")
        if diff and hay_cambios(diff):
            lineas += ["**Qué cambió en el entorno:**", tabla_cambios(diff, verde_n, run_n)]
        elif diff is not None:
            lineas.append("**Entorno:** no encontré diferencias entre ambos runs (mismo runner, herramientas y dependencias).")
    elif ctx.get("huella_actual"):
        lineas.append(
            "**Historial:** todavía no hay un run verde guardado en la rama base, "
            "así que no puedo comparar. Cuando este job pase en esa rama, guardaré la referencia."
        )
    else:
        lineas.append(
            "**Historial:** este job no guardó su huella, así que no puedo comparar "
            "(¿falta el paso `huella` con `if: always()`?)."
        )

    # Diagnóstico
    diagnostico = texto_ia(analisis.get("diagnostico"))
    if not diagnostico:
        diagnostico = f"{principal['titulo']}. {principal['evidencia']}"
    descartado = [texto_ia(d, 200) for d in (analisis.get("descartado") or []) if d][:5]
    if descartado:
        diagnostico += " **Descartado:** " + "; ".join(descartado) + "."
    lineas.append(f"**Diagnóstico:** {diagnostico}")

    # Tratamiento y validación
    lineas.append(f"**Tratamiento:** {texto_ia(analisis.get('tratamiento')) or principal['tratamiento']}")
    lineas.append(f"**Validación:** {texto_ia(analisis.get('validacion')) or principal['validacion']}")

    confianza = str(analisis.get("confianza", "")).lower()
    if confianza not in CONFIANZAS:
        confianza = principal["nivel"]
    pie = f"**Confianza:** {confianza} · *Pipeline Doctor propone, tú decides.*"
    lineas.append(pie)

    notas = []
    if not ctx.get("modelo"):
        notas.append("Modo sin IA: el diagnóstico sale solo de la comparación automática.")
    elif ctx.get("ia_error"):
        notas.append(
            "No pude consultar el modelo (revisa permisos y el ID del modelo en el log del job); "
            "este diagnóstico sale de la comparación automática."
        )
    if ctx.get("modelo") and ctx.get("redacciones"):
        notas.append(f"Se ocultaron {ctx['redacciones']} posible(s) secreto(s) del log antes del análisis.")
    if notas:
        lineas.append("<sub>" + " ".join(notas) + "</sub>")
    return "\n\n".join(lineas)


def envolver(secciones: List[str]) -> str:
    return MARCADOR + "\n" + "\n\n---\n\n".join(secciones) + "\n"
