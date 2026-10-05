"""Genera los diagramas de arquitectura de Pipeline Doctor (tema claro y oscuro).

Dibuja con matplotlib y usa los íconos oficiales de AWS y GitHub de la librería `diagrams`,
así cada flecha sale exactamente del paso que corresponde y queda recta.

Requisitos:  pip install matplotlib pillow diagrams
Uso, desde la carpeta docs/:   python generar_diagrama.py
Salida: arquitectura-claro.png y arquitectura-oscuro.png
"""
import os

import diagrams
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from diagrams.aws.ml import Bedrock
from diagrams.aws.security import IAMRole
from diagrams.aws.storage import S3
from diagrams.onprem.vcs import Github
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
from PIL import Image

TEMAS = {
    "claro": dict(fondo="#FFFFFF", texto="#1F2937", suave="#6B7280", caja="#F8FAFC", borde="#CBD5E1",
                  paso="#FFFFFF", test=dict(fondo="#EFF6FF", borde="#93C5FD", titulo="#1D4ED8"),
                  doctor=dict(fondo="#F0FDFA", borde="#5EEAD4", titulo="#0F766E"),
                  aws=dict(fondo="#FFFBF2", borde="#FF9900", titulo="#B45309"), ia="#7C3AED", ok="#16A34A", azul="#2563EB", github_blanco=False),
    "oscuro": dict(fondo="#0D1117", texto="#E6EDF3", suave="#8B949E", caja="#161B22", borde="#30363D",
                   paso="#0D1117", test=dict(fondo="#0F1B2D", borde="#1F4E8C", titulo="#58A6FF"),
                   doctor=dict(fondo="#0B2420", borde="#1F6B63", titulo="#4FD1C5"),
                   aws=dict(fondo="#241A08", borde="#B36B00", titulo="#FFB84D"), ia="#A78BFA", ok="#3FB950", azul="#58A6FF", github_blanco=True),
}


def icono(clase, blanco=False):
    raiz = os.path.dirname(os.path.dirname(diagrams.__file__))
    img = Image.open(os.path.join(raiz, clase._icon_dir, clase._icon)).convert("RGBA")
    if blanco:
        solido = Image.new("RGBA", img.size, (255, 255, 255, 255))
        solido.putalpha(img.getchannel("A"))
        img = solido
    return img


def dibujar(nombre: str, t: dict) -> None:
    ancho, alto = 26.0, 11.0
    fig = plt.figure(figsize=(ancho, alto - 0.2), dpi=100, facecolor=t["fondo"])
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, ancho)
    ax.set_ylim(0.2, alto)
    ax.axis("off")

    def texto(x, y, s, size=13, color=None, weight="normal", ha="center", va="center_baseline"):
        ax.text(x, y, s, fontsize=size, color=color or t["texto"], ha=ha, va=va, weight=weight,
                linespacing=1.35, zorder=6)

    def cluster(x0, y0, x1, y1, titulo, c):
        ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=0.25",
                                    fc=c["fondo"], ec=c["borde"], lw=2, zorder=1))
        texto(x0 + 0.3, y1 - 0.38, titulo, size=14, ha="left", weight="bold", color=c["titulo"])

    def paso(x, y, s, c, ia=False, w=2.7, h=1.2):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.2",
                                    fc=t["paso"], ec=t["ia"] if ia else c["borde"], lw=2,
                                    ls="--" if ia else "-", zorder=3))
        texto(x, y, s, size=13)
        return dict(x=x, y=y, w=w / 2, h=h / 2)

    def nodo(x, y, clase, etiqueta, blanco=False, zoom=0.4):
        img = icono(clase, blanco)
        ax.add_artist(AnnotationBbox(OffsetImage(img, zoom=zoom), (x, y + 0.2), frameon=False, zorder=4))
        texto(x, y - 0.65, etiqueta, size=13, va="top")
        return dict(x=x, y=y + 0.2, w=0.75, h=0.62)

    def flecha(a, b, lado_a, lado_b, color=None, estilo="-"):
        """Flecha recta entre el borde de dos nodos. lado: 'r', 'l', 't', 'b'."""
        def punto(n, lado):
            dx = {"r": n["w"], "l": -n["w"]}.get(lado, 0)
            dy = {"t": n["h"], "b": -n["h"]}.get(lado, 0)
            return n["x"] + dx, n["y"] + dy
        (x0, y0), (x1, y1) = punto(a, lado_a), punto(b, lado_b)
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=18,
                                     color=color or t["suave"], lw=2, ls=estilo, shrinkA=4, shrinkB=4, zorder=2))
        return (x0 + x1) / 2, (y0 + y1) / 2

    def insignia(x, y, n, color):
        ax.add_patch(Circle((x, y), 0.27, fc=color, ec=t["fondo"], lw=2, zorder=7))
        ax.text(x, y - 0.01, str(n), fontsize=15, color=t["fondo"] if t["github_blanco"] else "#FFFFFF", ha="center", va="center", weight="bold",
                zorder=8)

    texto(ancho / 2, alto - 0.55, "Tu código no cambió. Cambió esto.", size=24, weight="bold")

    yA, yB = 8.2, 3.9  # fila del job test y fila del job doctor
    xS3 = 15.2         # S3 y "Comparar" comparten columna: la flecha 2 baja derecha

    cluster(2.2, yA - 1.5, 8.9, yA + 1.5, "Job 1 · test", t["test"])
    cluster(9.9, yB - 1.35, 22.7, yB + 1.45, "Job 2 · doctor (solo si el job 1 falla)", t["doctor"])
    cluster(10.9, yA - 2.05, 20.0, yA + 1.5, "AWS Cloud · tu cuenta de AWS", t["aws"])
    push = nodo(1.0, yA - 0.2, Github, "push o PR", blanco=t["github_blanco"], zoom=0.34)
    instalar = paso(3.7, yA, "Instalar y\nprobar tu app", t["test"], w=2.5)
    huella = paso(7.0, yA, "Acción huella\n(siempre, aunque falle)", t["test"], w=3.2)
    rol = nodo(11.8, yA - 0.2, IAMRole, "Rol por OIDC\nsin access keys")
    s3 = nodo(xS3, yA - 0.2, S3, "S3 privado\nhuellas y último\nrun exitoso")

    leer = paso(11.5, yB, "Leer el log y\nocultar secretos", t["doctor"], w=2.6)
    comparar = paso(xS3, yB, "Comparar con el\núltimo run exitoso", t["doctor"], w=2.8)
    redactar = paso(18.6, yB, "Redactar el informe\ncon IA (opcional)", t["doctor"], ia=True, w=3.0)
    publicar = paso(21.4, yB, "Publicar\nel informe", t["doctor"], w=2.1)
    informe = nodo(24.5, yB - 0.2, Github, "Summary del run\ny comentario del PR",
                   blanco=t["github_blanco"], zoom=0.34)
    bedrock = nodo(18.6, yA - 0.2, Bedrock, "Amazon Bedrock", zoom=0.34)

    flecha(push, instalar, "r", "l")
    flecha(instalar, huella, "r", "l")
    flecha(rol, s3, "r", "l")
    flecha(leer, comparar, "r", "l")
    flecha(comparar, redactar, "r", "l")
    flecha(redactar, publicar, "r", "l")

    def etiqueta_h(x, y, n, s, color):
        """Flecha horizontal numerada: la insignia va sobre la línea y el texto, centrado, arriba."""
        insignia(x, y, n, color)
        texto(x, y + 0.6, s, size=13, color=color, va="center_baseline")

    def etiqueta_v(x, y, n, s, color):
        """Flecha vertical numerada: la insignia va sobre la línea y el texto, a la derecha."""
        insignia(x, y, n, color)
        texto(x + 0.5, y, s, size=13, color=color, ha="left", va="center_baseline")

    # Paso 1: Acción huella -> rol
    x, y = flecha(huella, rol, "r", "l", color=t["azul"])
    etiqueta_h(x, y, 1, "guarda la huella", t["azul"])

    # Paso 2: S3 -> Comparar (vertical, empieza bajo la etiqueta de S3)
    origen = dict(x=xS3, y=yA - 2.05, w=0, h=0)
    x, y = flecha(origen, comparar, "b", "t", color=t["azul"])
    etiqueta_v(x, 5.75, 2, "último run exitoso", t["azul"])

    # Paso 3: Redactar -> Bedrock (vertical)
    destino = dict(x=18.6, y=yA - 1.25, w=0, h=0)
    x, y = flecha(redactar, destino, "t", "b", color=t["ia"], estilo="--")
    etiqueta_v(x, 5.75, 3, "consulta (logs sin secretos)", t["ia"])

    # Paso 4: Publicar -> informe
    x, y = flecha(publicar, informe, "r", "l", color=t["ok"])
    etiqueta_h(x, y, 4, "publica", t["ok"])

    # Conexión entre los dos jobs: son parte del mismo workflow (needs: test, if: failure())
    xc, y0, y1 = 5.5, yA - 1.5, yB
    ax.plot([xc, xc], [y0, y1], color=t["suave"], lw=2, zorder=2)
    ax.add_patch(FancyArrowPatch((xc, y1), (9.85, y1), arrowstyle="-|>", mutation_scale=18, color=t["suave"],
                                 lw=2, shrinkA=0, shrinkB=0, zorder=2))
    ax.add_patch(FancyBboxPatch((xc - 1.55, (y0 + y1) / 2 - 0.5), 3.1, 1.0,
                                boxstyle="round,pad=0,rounding_size=0.2", fc=t["fondo"], ec=t["suave"], lw=1.5,
                                zorder=5))
    texto(xc, (y0 + y1) / 2, "needs: test\nif: failure()", size=12, color=t["suave"])
    texto(1.0, 0.9, "Los dos jobs son parte del mismo workflow de GitHub Actions.", size=13,
          color=t["suave"], ha="left")

    # Nota en el hueco de la izquierda
    texto(1.0, 1.9, "Todo es código determinístico,\nsalvo el paso 3 (IA, opcional).", size=13,
          color=t["suave"], ha="left")

    fig.savefig(f"arquitectura-{nombre}.png", facecolor=t["fondo"])
    plt.close(fig)


if __name__ == "__main__":
    for nombre, tema in TEMAS.items():
        dibujar(nombre, tema)
        print("listo:", f"arquitectura-{nombre}.png")
