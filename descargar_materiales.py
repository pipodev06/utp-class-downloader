"""
Descarga de materiales (PDF/PPTX/DOCX/... y los enlazados dentro de las lecturas) a partir de lo
que ya listó scrape.listar_todo — sin login ni nuevas consultas a la API (los archivos están en S3
y se bajan sin sesión). Guarda en:
  BASE_DIR/<ciclo>/<curso>/Semana NN/<archivo>   (semana 0 → General/)
  BASE_DIR/<ciclo>/<curso>/youtube.html   (enlaces de YouTube por semana, no se descargan)
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import requests.adapters

from scrape import carpeta_curso, escribir_indice_youtube


def _descargar_archivo(http: requests.Session, url: str, destino: Path) -> str | None:
    """Baja a .part y renombra al final: un corte a medias no deja un archivo "completo" falso.
    Devuelve None si salió bien, o el mensaje de error."""
    parcial = destino.with_name(destino.name + ".part")
    try:
        with http.get(url, stream=True, timeout=300) as res:
            res.raise_for_status()
            destino.parent.mkdir(parents=True, exist_ok=True)
            with open(parcial, "wb") as f:
                for chunk in res.iter_content(1024 * 1024):
                    f.write(chunk)
        parcial.replace(destino)
        return None
    except (requests.RequestException, OSError, ValueError) as e:
        try:
            parcial.unlink(missing_ok=True)
        except OSError:
            pass   # ruta inválida: no hay nada que borrar; el error real ya va en el mensaje
        return str(e)


def descargar_materiales(
    base_dir: str, cursos: list[dict], workers: int = 4,
    log=print, progreso=lambda actual, total: None,
) -> dict:
    pendientes = []
    for curso in cursos:
        carpeta = carpeta_curso(base_dir, curso)
        if escribir_indice_youtube(carpeta, curso["nombre"], curso.get("youtube") or []):
            log("INFO", "gray", f"{curso['nombre']}: youtube.html con {len(curso['youtube'])} video(s)")
        for m in curso["materiales"]:
            destino = carpeta / m["archivo"]   # 'Semana 05/Práctica.pdf'
            if not destino.exists():
                pendientes.append((curso["nombre"], m["url"], destino))

    total = len(pendientes)
    log("SUCCESS", "#22c55e", f"{total} archivo(s) por bajar de {len(cursos)} curso(s)")

    http = requests.Session()
    http.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=workers * 2))
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futuros = {pool.submit(_descargar_archivo, http, url, destino): (nombre, destino)
                   for nombre, url, destino in pendientes}
        for i, fut in enumerate(as_completed(futuros), start=1):
            nombre, destino = futuros[fut]
            try:
                error = fut.result()
            except Exception as e:   # un archivo raro nunca debe cortar los demás
                error = f"error inesperado: {e}"
            if error is None:
                ok += 1
                log("SUCCESS", "#22c55e", f"{nombre} — {destino.name}")
            else:
                fail += 1
                log("WARN", "#f59e0b", f"{destino.name}: {error}")
            progreso(i, total)

    log("SUCCESS", "#22c55e", f"Descarga de materiales completa — {ok} nuevos, {fail} fallidos")
    return {"ok": ok, "fail": fail}
