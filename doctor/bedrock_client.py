"""Llamada a Amazon Bedrock (API Converse) usando el AWS CLI."""
from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Optional, Tuple

from .util import ejecutar


def consultar(
    modelo: str,
    region: Optional[str],
    sistema: str,
    usuario: str,
    max_tokens: int = 1500,
) -> Tuple[str, dict]:
    """Devuelve (texto de la respuesta, uso de tokens)."""
    with tempfile.TemporaryDirectory() as carpeta:
        rutas = {}
        contenidos = {
            "sistema": [{"text": sistema}],
            "mensajes": [{"role": "user", "content": [{"text": usuario}]}],
            "config": {"maxTokens": max_tokens, "temperature": 0.2},
        }
        for nombre, contenido in contenidos.items():
            rutas[nombre] = os.path.join(carpeta, f"{nombre}.json")
            with open(rutas[nombre], "w", encoding="utf-8") as f:
                json.dump(contenido, f, ensure_ascii=False)

        cmd = [
            "aws", "bedrock-runtime", "converse",
            "--model-id", modelo,
            "--system", f"file://{rutas['sistema']}",
            "--messages", f"file://{rutas['mensajes']}",
            "--inference-config", f"file://{rutas['config']}",
            "--output", "json",
        ]
        if region:
            cmd += ["--region", region]
        r = ejecutar(cmd, timeout=120)

    datos = json.loads(r.stdout)
    bloques = datos["output"]["message"]["content"]
    texto = "".join(b.get("text", "") for b in bloques)
    return texto, datos.get("usage", {})


def parsear_json(texto: str) -> Optional[dict]:
    """Extrae el primer objeto JSON de la respuesta (tolera ```json ... ```)."""
    limpio = re.sub(r"```(?:json)?", "", texto or "").strip()
    ini, fin = limpio.find("{"), limpio.rfind("}")
    if ini == -1 or fin <= ini:
        return None
    try:
        datos = json.loads(limpio[ini : fin + 1])
    except ValueError:
        return None
    return datos if isinstance(datos, dict) else None
