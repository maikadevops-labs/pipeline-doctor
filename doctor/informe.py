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


def _bloque(texto: str) -> str:
    """Bloque de código para una línea del log (sin permitir que cierre el bloque)."""
    return "```text\n" + texto.replace("```", "'''") + "\n```"


def construir(ctx: dict, analisis: Optional[dict] = None) -> str:
    """ctx: datos del run/job. analisis: respuesta (ya parseada) del modelo, si hubo."""
    sospechosos: List[dict] = ctx["sospechosos"]
    principal = sospechosos[0]
    verde = ctx.get("verde")
    run_n = ctx.get("run_number") or ctx.get("run_id")
    analisis = analisis or {}

    # Cada elemento es un bloque: así se ve igual en un comentario de PR y en el resumen del job.
    titulo = f"### 🩺 Pipeline Doctor: consulta del run #{run_n}"
    if ctx.get("run_url"):
        titulo += f" ([ver run]({ctx['run_url']}))"
    bloques = [titulo]

    # Síntomas
    paso = ctx.get("paso")
    donde = f"El job `{ctx['job']}` falló" + (f" en el paso *{paso}*." if paso else ".")
    sintoma_ia = texto_ia(analisis.get("sintomas"))
    bloques += ["#### 🔍 Síntomas", donde + (f" {sintoma_ia}" if sintoma_ia else "")]
    if not sintoma_ia and ctx.get("linea_error"):
        bloques.append(_bloque(ctx["linea_error"]))

    # Historial
    bloques.append("#### 📜 Historial")
    if verde:
        verde_n = verde.get("run_number") or verde.get("run_id")
        bloques.append(
            f"Último run verde: #{verde_n} ({hace(verde.get('timestamp'))}). "
            + frase_codigo(ctx.get("codigo"), verde_n, run_n)
        )
        diff = ctx.get("diff")
        if diff and hay_cambios(diff):
            bloques += ["#### 🧬 Qué cambió en el entorno", tabla_cambios(diff, verde_n, run_n)]
        elif diff is not None:
            bloques.append(
                "No encontré diferencias entre ambos runs en el entorno "
                "(mismo runner, herramientas y dependencias)."
            )
    elif ctx.get("huella_actual"):
        bloques.append(
            "Todavía no hay un run verde guardado en la rama base, "
            "así que no puedo comparar. Cuando este job pase en esa rama, guardaré la referencia."
        )
    else:
        bloques.append(
            "Este job no guardó su huella, así que no puedo comparar "
            "(¿falta el paso `huella` con `if: always()`?)."
        )

    # Diagnóstico
    diagnostico = texto_ia(analisis.get("diagnostico"))
    if not diagnostico:
        diagnostico = f"{principal['titulo']}. {principal['evidencia']}"
    bloques += ["#### 🩺 Diagnóstico", diagnostico]
    descartado = [t for t in (texto_ia(d, 200).rstrip(" .;") for d in (analisis.get("descartado") or []) if d) if t][:5]
    if descartado:
        bloques.append("**Descartado:** " + "; ".join(descartado) + ".")

    # Tratamiento y validación
    bloques += [
        "#### 💊 Tratamiento",
        texto_ia(analisis.get("tratamiento")) or principal["tratamiento"],
        "#### ✅ Validación",
        texto_ia(analisis.get("validacion")) or principal["validacion"],
    ]

    confianza = str(analisis.get("confianza", "")).lower()
    if confianza not in CONFIANZAS:
        confianza = principal["nivel"]
    bloques += ["---", f"**Confianza:** {confianza} · *Pipeline Doctor propone, tú decides.*"]

    notas = []
    if not ctx.get("modelo"):
        notas.append("Modo sin IA: el diagnóstico sale solo de la comparación automática.")
    elif ctx.get("ia_error"):
        notas.append(
            "No pude consultar el modelo (revisa permisos y el ID del modelo en el log del job); "
            "este diagnóstico sale de la comparación automática."
        )
    elif ctx.get("modelo"):
        modelo = str(ctx["modelo"]).replace("`", "")[:80]
        notas.append(
            f"🤖 Texto redactado con IA (`{modelo}` en Amazon Bedrock) a partir de la evidencia. "
            "La tabla de cambios sale de la comparación automática, no del modelo. "
            "La IA puede equivocarse: verifica antes de aplicar."
        )
    if ctx.get("modelo") and ctx.get("redacciones"):
        notas.append(f"Se ocultaron {ctx['redacciones']} posible(s) secreto(s) del log antes del análisis.")
    if notas:
        bloques.append("<sub>" + " ".join(notas) + "</sub>")
    return "\n\n".join(bloques)


# --- versión en texto plano para el log del job (el Markdown se ve feo ahí) ---------------

_TABLA_SEP = re.compile(r"^\|\s*:?-{3,}")
_ENLACE_MD = re.compile(r"!?\[([^\]]*)\]\(([^)]*)\)")
_CURSIVA = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])")


def texto_plano(md: str) -> str:
    """Convierte el informe a texto legible en una terminal: sin **, sin backticks, con tablas alineadas."""
    salida: List[str] = []
    tabla: List[List[str]] = []
    en_codigo = False

    def volcar():
        if not tabla:
            return
        ancho = [max(len(f[c]) for f in tabla) for c in range(len(tabla[0]))]
        for n, fila in enumerate(tabla):
            salida.append("  " + "   ".join(celda.ljust(ancho[c]) for c, celda in enumerate(fila)).rstrip())
            if n == 0:
                salida.append("  " + "   ".join("─" * a for a in ancho))
        tabla.clear()

    for linea in md.splitlines():
        if linea.strip() == MARCADOR:
            continue
        if linea.startswith("```"):
            en_codigo = not en_codigo
            continue
        if en_codigo:
            salida.append("    " + linea)
            continue
        if linea.startswith("|"):
            if _TABLA_SEP.match(linea):
                continue
            celdas = [c.strip().replace("\\|", "|").replace("`", "") for c in linea.strip().strip("|").split("|")]
            tabla.append(celdas)
            continue
        volcar()
        if linea.strip() == "---":
            salida.append("─" * 60)
            continue
        linea = _ENLACE_MD.sub(r"\1: \2", linea)
        linea = re.sub(r"</?sub>", "", linea)
        linea = linea.replace("**", "").replace("`", "")
        linea = _CURSIVA.sub(r"\1", linea)
        if linea.startswith("####"):
            salida += ["", linea.lstrip("# ").upper()]
        elif linea.startswith("###"):
            salida += [linea.lstrip("# ").strip(), "═" * 60]
        else:
            salida.append(linea)
    volcar()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip() + "\n"


def envolver(secciones: List[str]) -> str:
    return MARCADOR + "\n" + "\n\n---\n\n".join(secciones) + "\n"
