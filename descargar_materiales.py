"""
Descarga de materiales (PDF/PPTX/DOCX/... y los enlazados dentro de las lecturas) a partir de lo
que ya listó scrape.listar_todo — sin login ni nuevas consultas a la API (los archivos están en S3
y se bajan sin sesión). Guarda en:
  BASE_DIR/<ciclo>/<curso>/Semana NN/<archivo>   (semana 0 → General/)
  BASE_DIR/<ciclo>/<curso>/youtube.html   (enlaces de YouTube por semana, no se descargan)
"""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import requests.adapters

from scrape import DETENIDA, carpeta_curso, descargado, escribir_indice_youtube, marcar_de_internet


def _descargar_archivo(http: requests.Session, url: str, destino: Path, cancelar: threading.Event) -> str | None:
    """Baja a .part y renombra al final: un corte a medias no deja un archivo "completo" falso.
    Devuelve None si salió bien, DETENIDA si se canceló, o el mensaje de error."""
    if cancelar.is_set():
        return DETENIDA
    parcial = destino.with_name(destino.name + ".part")
    try:
        with http.get(url, stream=True, timeout=300) as res:
            res.raise_for_status()
            destino.parent.mkdir(parents=True, exist_ok=True)
            with open(parcial, "wb") as f:
                for chunk in res.iter_content(1024 * 1024):
                    if cancelar.is_set():   # también a mitad de un video grande
                        break
                    f.write(chunk)
        if cancelar.is_set():
            parcial.unlink(missing_ok=True)
            return DETENIDA
        parcial.replace(destino)
        marcar_de_internet(destino, url)
        return None
    except requests.HTTPError as e:   # solo el código: str(e) trae la URL (puede ir firmada)
        _borrar(parcial)
        return f"HTTP {e.response.status_code}"
    except requests.RequestException as e:
        _borrar(parcial)
        return type(e).__name__
    except (OSError, ValueError) as e:
        _borrar(parcial)
        return str(e)


def _borrar(parcial: Path):
    try:
        parcial.unlink(missing_ok=True)
    except OSError:
        pass   # ruta inválida: no hay nada que borrar; el error real ya va en el mensaje


def descargar_materiales(
    base_dir: str, cursos: list[dict], workers: int = 4,
    log=print, progreso=lambda actual, total: None, cancelar: threading.Event | None = None,
) -> dict:
    cancelar = cancelar or threading.Event()
    pendientes = []
    for curso in cursos:
        carpeta = carpeta_curso(base_dir, curso)
        if escribir_indice_youtube(carpeta, curso["nombre"], curso.get("youtube") or []):
            log("INFO", "gray", f"{curso['nombre']}: youtube.html con {len(curso['youtube'])} video(s)")
        for m in curso["materiales"]:
            destino = carpeta / m["archivo"]   # 'Semana 05/Práctica.pdf'
            if not descargado(destino):
                pendientes.append((curso["nombre"], m["url"], destino))

    total = len(pendientes)
    log("SUCCESS", "#22c55e", f"{total} archivo(s) por bajar de {len(cursos)} curso(s)")

    http = requests.Session()
    http.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=workers * 2))
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futuros = {pool.submit(_descargar_archivo, http, url, destino, cancelar): (nombre, destino)
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
            elif error != DETENIDA:
                fail += 1
                log("WARN", "#f59e0b", f"{destino.name}: {error}")
            progreso(i, total)

    if cancelar.is_set():
        log("WARN", "#f59e0b", f"Descarga de materiales detenida — {ok} nuevos, {total - ok - fail} sin bajar")
        return {"ok": ok, "fail": fail, "detenido": True}
    log("SUCCESS", "#22c55e", f"Descarga de materiales completa — {ok} nuevos, {fail} fallidos")
    return {"ok": ok, "fail": fail}
