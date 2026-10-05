"""Acceso a la API de GitHub usando `gh` (ya viene instalado en los runners hospedados)."""
from __future__ import annotations

import json
import os
from typing import List, Optional

from .util import ejecutar


class GitHub:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token

    def _api(self, ruta: str, metodo: str = "GET", cuerpo: Optional[dict] = None, crudo: bool = False):
        cmd = ["gh", "api", ruta]
        entrada = None
        if metodo != "GET":
            cmd += ["--method", metodo]
        if cuerpo is not None:
            cmd += ["--input", "-"]
            entrada = json.dumps(cuerpo)
        env = dict(os.environ)
        env["GH_TOKEN"] = self.token
        r = ejecutar(cmd, entrada=entrada, timeout=180, env=env)
        if crudo:
            return r.stdout
        return json.loads(r.stdout) if r.stdout.strip() else None

    def jobs_del_run(self, run_id: str, intento: str) -> List[dict]:
        datos = self._api(
            f"repos/{self.repo}/actions/runs/{run_id}/attempts/{intento}/jobs?per_page=100"
        )
        return (datos or {}).get("jobs", [])

    def log_del_job(self, job_id) -> str:
        return self._api(f"repos/{self.repo}/actions/jobs/{job_id}/logs", crudo=True)

    def archivos_entre(self, base: str, cabeza: str) -> List[str]:
        datos = self._api(f"repos/{self.repo}/compare/{base}...{cabeza}") or {}
        return [f["filename"] for f in datos.get("files", [])]

    def comentar(self, numero, cuerpo: str, marcador: str) -> str:
        """Crea el comentario o actualiza el anterior de Pipeline Doctor. Devuelve la acción."""
        comentarios = self._api(f"repos/{self.repo}/issues/{numero}/comments?per_page=100") or []
        previo = next(
            (
                c
                for c in comentarios
                if marcador in (c.get("body") or "")
                and (c.get("user") or {}).get("type") == "Bot"
            ),
            None,
        )
        if previo:
            self._api(f"repos/{self.repo}/issues/comments/{previo['id']}", "PATCH", {"body": cuerpo})
            return "actualizado"
        self._api(f"repos/{self.repo}/issues/{numero}/comments", "POST", {"body": cuerpo})
        return "creado"
