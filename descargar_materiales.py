"""
Descarga real de materiales (PDF/PPTX/DOCX/...) — flujo independiente del listado.
Hace su propio login + recorrido de cursos, y guarda los archivos en:
  BASE_DIR/<ciclo>/<curso>/archivos/
"""
from pathlib import Path

import requests

from scrape import (
    obtener_token, obtener_cursos, obtener_contenido,
    materiales_descargables, resolver_ciclo, sanitizar,
)


def _descargar_archivo(url: str, destino: Path, log=print) -> bool:
    try:
        with requests.get(url, stream=True, timeout=300) as res:
            res.raise_for_status()
            destino.parent.mkdir(parents=True, exist_ok=True)
            with open(destino, "wb") as f:
                for chunk in res.iter_content(1024 * 1024):
                    f.write(chunk)
        return True
    except Exception as e:
        log("WARN", "#f59e0b", f"{destino.name}: {e}")
        return False


def descargar_materiales(
    sesion_dir: str, base_dir: str,
    log=print, progreso=lambda actual, total: None,
    nombres: list[str] | None = None,
) -> dict:
    base = Path(base_dir).expanduser()

    _, student_id, headers = obtener_token(sesion_dir, log=log)

    log("INFO", "gray", "Consultando cursos...")
    cursos = obtener_cursos(student_id, headers)
    if nombres:
        cursos = [c for c in cursos if c["nombre"] in nombres]
    total = len(cursos)
    log("SUCCESS", "#22c55e", f"{len(cursos)} curso(s) a procesar")

    ok = 0
    fail = 0
    for i, curso in enumerate(cursos, start=1):
        ciclo = resolver_ciclo(curso["periodo"])
        carpeta = base / ciclo / sanitizar(curso["nombre"]) / "archivos"

        items = obtener_contenido(curso["courseId"], curso["sectionId"], headers)
        nuevos = 0
        for material in materiales_descargables(items):
            nombre_archivo = material["archivo"]
            destino = carpeta / nombre_archivo
            if destino.exists():
                continue

            if _descargar_archivo(material["url"], destino, log=log):
                ok += 1
                nuevos += 1
                log("SUCCESS", "#22c55e", f"{curso['nombre']} — {nombre_archivo}")
            else:
                fail += 1

        if nuevos:
            log("INFO", "gray", f"{curso['nombre']}: {nuevos} archivo(s) nuevo(s)")
        progreso(i, total)

    log("SUCCESS", "#22c55e", f"Descarga de materiales completa — {ok} nuevos, {fail} fallidos")
    return {"ok": ok, "fail": fail}
