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


def emoji(caracter):
    """Emoji a color como imagen (matplotlib no dibuja emojis a color como texto)."""
    from PIL import ImageDraw, ImageFont
    fuente = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)
    img = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((0, 0), caracter, font=fuente, embedded_color=True)
    return img


def icono(clase, blanco=False):
    raiz = os.path.dirname(os.path.dirname(diagrams.__file__))
    img = Image.open(os.path.join(raiz, clase._icon_dir, clase._icon)).convert("RGBA")
    if blanco:
        solido = Image.new("RGBA", img.size, (255, 255, 255, 255))
        solido.putalpha(img.getchannel("A"))
        img = solido
    return img


def dibujar(nombre: str, t: dict) -> None:
    # Unidades = pulgadas. El lienzo es compacto y las letras grandes, para que se lean
    # cuando GitHub muestra la imagen a unos 900 px de ancho.
    ancho, alto, base = 17.3, 8.5, 0.2
    fig = plt.figure(figsize=(ancho, alto), dpi=160, facecolor=t["fondo"])
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, ancho)
    ax.set_ylim(base, base + alto)
    ax.axis("off")
    TXT, ETQ = 15, 14

    def texto(x, y, s, size=TXT, color=None, weight="normal", ha="center", va="center_baseline"):
        ax.text(x, y, s, fontsize=size, color=color or t["texto"], ha=ha, va=va, weight=weight,
                linespacing=1.3, zorder=6)

    def cluster(x0, y0, x1, y1, titulo, c, emo=None):
        ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=0.18",
                                    fc=c["fondo"], ec=c["borde"], lw=2.2, zorder=1))
        sangria = 0.25
        if emo:
            ax.add_artist(AnnotationBbox(OffsetImage(emoji(emo), zoom=0.17), (x0 + 0.5, y1 - 0.33),
                                         frameon=False, zorder=6))
            sangria = 0.8
        texto(x0 + sangria, y1 - 0.33, titulo, ha="left", weight="bold", color=c["titulo"])

    def paso(x, y, s, c, w, ia=False, h=1.0):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.15",
                                    fc=t["paso"], ec=t["ia"] if ia else c["borde"], lw=2.2,
                                    ls="--" if ia else "-", zorder=3))
        texto(x, y, s)
        return dict(x=x, y=y, w=w / 2, h=h / 2)

    def nodo(x, y, clase, etiqueta, blanco=False, zoom=0.3):
        img = icono(clase, blanco)
        ax.add_artist(AnnotationBbox(OffsetImage(img, zoom=zoom * 0.72), (x, y), frameon=False, zorder=4))
        texto(x, y - 0.5, etiqueta, va="top")
        return dict(x=x, y=y, w=0.55, h=0.45)

    def flecha(a, b, lado_a, lado_b, color=None, estilo="-"):
        def punto(n, lado):
            dx = {"r": n["w"], "l": -n["w"]}.get(lado, 0)
            dy = {"t": n["h"], "b": -n["h"]}.get(lado, 0)
            return n["x"] + dx, n["y"] + dy
        (x0, y0), (x1, y1) = punto(a, lado_a), punto(b, lado_b)
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=20,
                                     color=color or t["suave"], lw=2.2, ls=estilo, shrinkA=3, shrinkB=3, zorder=2))
        return (x0 + x1) / 2, (y0 + y1) / 2

    def insignia(x, y, n, color):
        ax.add_patch(Circle((x, y), 0.3, fc=color, ec=t["fondo"], lw=2, zorder=7))
        ax.text(x, y - 0.01, str(n), fontsize=17, color=t["fondo"] if t["github_blanco"] else "#FFFFFF",
                ha="center", va="center", weight="bold", zorder=8)

    def etiqueta_h(x, y, n, s, color):
        insignia(x, y, n, color)
        texto(x, y + 0.85, s, size=ETQ, color=color)

    def etiqueta_v(x, y, n, s, color):
        insignia(x, y, n, color)
        texto(x + 0.5, y, s, size=ETQ, color=color, ha="left")

    yA, yB = 6.6, 3.0
    xS3, xRol = 9.4, 7.5
    texto(ancho / 2, base + alto - 0.4, "Tu código no cambió. Cambió esto.", size=22, weight="bold")

    # Fila A: push -> Job 1 -> AWS
    cluster(1.5, yA - 0.8, 5.45, yA + 1.1, "Job 1 · test", t["test"], "🧪")
    cluster(6.6, yA - 1.55, 12.95, yA + 1.1, "AWS Cloud · tu cuenta de AWS", t["aws"], "☁️")
    push = nodo(0.7, yA, Github, "push o PR", blanco=t["github_blanco"], zoom=0.26)
    instalar = paso(2.6, yA, "Instalar y\nprobar app", t["test"], 1.6)
    huella = paso(4.5, yA, "Acción\nhuella", t["test"], 1.4)
    rol = nodo(xRol, yA, IAMRole, "Rol por OIDC\nsin access keys")
    s3 = nodo(xS3, yA, S3, "S3 privado\nhuellas y último\nrun exitoso")
    bedrock = nodo(11.9, yA, Bedrock, "Amazon\nBedrock")

    # Fila B: Job 2
    cluster(5.6, yB - 0.8, 14.85, yB + 1.05, "Job 2 · doctor", t["doctor"], "🩺")
    leer = paso(6.9, yB - 0.1, "Leer log y\nocultar secretos", t["doctor"], 1.9)
    comparar = paso(xS3, yB - 0.1, "Comparar con\núltimo run exitoso", t["doctor"], 2.2)
    redactar = paso(11.9, yB - 0.1, "Redactar con IA\n(opcional)", t["doctor"], 1.9, ia=True)
    publicar = paso(13.95, yB - 0.1, "Publicar\ninforme", t["doctor"], 1.4)
    informe = nodo(16.5, yB - 0.1, Github, "Summary\ny comentario\ndel PR", blanco=t["github_blanco"], zoom=0.26)

    flecha(push, instalar, "r", "l")
    flecha(instalar, huella, "r", "l")
    flecha(rol, s3, "r", "l")
    flecha(leer, comparar, "r", "l")
    flecha(comparar, redactar, "r", "l")
    flecha(redactar, publicar, "r", "l")

    x, y = flecha(huella, rol, "r", "l", color=t["azul"])
    etiqueta_h(6.05, y, 1, "guarda\nla huella", t["azul"])

    origen = dict(x=xS3, y=yA - 1.55, w=0, h=0)
    flecha(origen, comparar, "b", "t", color=t["azul"])
    etiqueta_v(xS3, 4.55, 2, "último run\nexitoso", t["azul"])

    destino = dict(x=11.9, y=yA - 1.3, w=0, h=0)
    flecha(redactar, destino, "t", "b", color=t["ia"], estilo="--")
    etiqueta_v(11.9, 4.55, 3, "consulta\n(sin secretos)", t["ia"])

    x, y = flecha(publicar, informe, "r", "l", color=t["ok"])
    etiqueta_h(x, y, 4, "publica", t["ok"])

    # Conexión entre jobs: mismo workflow (needs: test, if: failure())
    xc, y0, y1 = 3.5, yA - 0.8, yB - 0.1
    ax.plot([xc, xc], [y0, y1], color=t["suave"], lw=2.2, zorder=2)
    ax.add_patch(FancyArrowPatch((xc, y1), (5.55, y1), arrowstyle="-|>", mutation_scale=20, color=t["suave"],
                                 lw=2.2, shrinkA=0, shrinkB=0, zorder=2))
    ax.add_patch(FancyBboxPatch((xc - 1.05, (y0 + y1) / 2 - 0.4), 2.1, 0.8,
                                boxstyle="round,pad=0,rounding_size=0.15", fc=t["fondo"], ec=t["suave"], lw=1.6,
                                zorder=5))
    texto(xc, (y0 + y1) / 2, "needs: test\nif: failure()", size=13, color=t["suave"])

    texto(0.6, 1.45, "Todo es código determinístico,\nsalvo el paso 3 (IA, opcional).", size=13,
          color=t["suave"], ha="left")
    texto(0.6, 0.65, "Los dos jobs son parte del mismo\nworkflow de GitHub Actions.", size=13,
          color=t["suave"], ha="left")

    fig.savefig(f"arquitectura-{nombre}.png", facecolor=t["fondo"])
    plt.close(fig)


if __name__ == "__main__":
    for nombre, tema in TEMAS.items():
        dibujar(nombre, tema)
        print("listo:", f"arquitectura-{nombre}.png")
