"""
Descarga real de materiales (PDF/PPTX/DOCX/... y los enlazados dentro de las lecturas)
— flujo independiente del listado. Hace su propio login + recorrido de cursos, y guarda en:
  BASE_DIR/<ciclo>/<curso>/archivos/
  BASE_DIR/<ciclo>/<curso>/youtube.html   (enlaces de YouTube por semana, no se descargan)
"""
from pathlib import Path

import requests

from scrape import (
    obtener_token, obtener_cursos, obtener_contenido,
    materiales_descargables, enlaces_youtube, escribir_indice_youtube,
    resolver_ciclo, sanitizar,
)


def _descargar_archivo(url: str, destino: Path, log=print) -> bool:
    # se baja a .part y se renombra al final: un corte a medias no deja un archivo "completo" falso
    parcial = destino.with_name(destino.name + ".part")
    try:
        with requests.get(url, stream=True, timeout=300) as res:
            res.raise_for_status()
            destino.parent.mkdir(parents=True, exist_ok=True)
            with open(parcial, "wb") as f:
                for chunk in res.iter_content(1024 * 1024):
                    f.write(chunk)
        parcial.replace(destino)
        return True
    except Exception as e:
        parcial.unlink(missing_ok=True)
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
        enlaces = enlaces_youtube(items)
        if escribir_indice_youtube(carpeta.parent, curso["nombre"], enlaces):
            log("INFO", "gray", f"{curso['nombre']}: youtube.html con {len(enlaces)} video(s)")
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
