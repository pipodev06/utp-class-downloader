"""
Descarga real de grabaciones Zoom a partir de lo que ya listó scrape.listar_todo.
Exporta la sesión de Playwright y descarga cada grabación en paralelo (headless) a:
  BASE_DIR/<ciclo>/<curso>/videos/
Portado de zoom_download.py del proyecto original.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from playwright.sync_api import sync_playwright

from scrape import sanitizar, sesion_api

ERRORES_ZOOM = [
    "esta grabación no existe", "this recording does not exist",
    "recording does not exist", "3.301", "3301",
    "no longer available", "ya no está disponible", "has been deleted",
]


def exportar_sesion(sesion_dir: str) -> dict:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(user_data_dir=sesion_dir, headless=True)
        state = ctx.storage_state()
        ctx.close()
    return state


def _descargar_uno(rec: dict, storage_state: dict, base_dir: Path) -> tuple[bool, str]:
    titulo = rec["titulo"]
    curso = rec["curso"]
    play_url = rec["grabacion"]
    ciclo = rec["periodo"]

    carpeta = base_dir / ciclo / sanitizar(curso) / "videos"
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{rec['archivo']}.mp4"
    marca_skip = destino.with_suffix(".skip")
    marca_fail = destino.with_suffix(".fail")

    if destino.exists():
        return True, f"[ya existe] {titulo[:55]}"
    if marca_skip.exists():
        return True, f"[no existe en Zoom] {titulo[:50]}"

    descargado = {"ok": False}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            storage_state=storage_state, accept_downloads=True,
            viewport={"width": 1024, "height": 768},
        )
        page = ctx.new_page()

        def on_dl(dl):
            if not descargado["ok"]:
                try:
                    dl.save_as(str(destino))
                    descargado["ok"] = True
                except Exception:
                    pass

        ctx.on("download", on_dl)

        try:
            page.goto(play_url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(3000)

            body = (page.inner_text("body") or "").lower()
            for err in ERRORES_ZOOM:
                if err in body:
                    marca_skip.touch()
                    marca_fail.unlink(missing_ok=True)
                    return False, f"no existe (omitida): {titulo[:50]}"

            clicked = False
            for sel in ["a[download]", "[data-testid='download-btn']",
                        ".recording-download-btn", "button[aria-label*='Download']"]:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click(timeout=5000)
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                for btn in page.query_selector_all("a, button"):
                    try:
                        txt = (btn.text_content() or "").lower().strip()
                        if ("descargar" in txt or "download" in txt) and btn.is_visible():
                            btn.click(timeout=5000)
                            break
                    except Exception:
                        continue

            for i in range(600):
                if descargado["ok"]:
                    break
                if i % 5 == 0:
                    body = (page.inner_text("body") or "").lower()
                    for err in ERRORES_ZOOM:
                        if err in body:
                            marca_skip.touch()
                            marca_fail.unlink(missing_ok=True)
                            return False, f"no existe (omitida): {titulo[:50]}"
                page.wait_for_timeout(1000)

        except Exception:
            pass
        finally:
            try:
                ctx.close()
                browser.close()
            except Exception:
                pass

    if destino.exists():
        marca_fail.unlink(missing_ok=True)
        mb = destino.stat().st_size / 1024 / 1024
        return True, f"{titulo[:55]} ({mb:.0f} MB)"
    marca_fail.touch()
    return False, f"no descargó: {titulo[:55]}"


def descargar_zoom(
    sesion_dir: str, base_dir: str, cursos: list[dict], workers: int = 4,
    log=print, progreso=lambda actual, total: None,
) -> dict:
    """Descarga las grabaciones de 'cursos' (entradas de scrape.listar_todo, sin re-consultar la API).
    Solo lanza navegador para las que faltan: las ya bajadas o marcadas .skip se saltan antes."""
    base = Path(base_dir).expanduser()

    pendientes = []
    ya = 0
    for curso in cursos:
        carpeta = base / curso["periodo"] / sanitizar(curso["nombre"]) / "videos"
        for g in curso["videos"]:
            if (carpeta / f"{g['archivo']}.mp4").exists() or (carpeta / f"{g['archivo']}.skip").exists():
                ya += 1
                continue
            pendientes.append({
                "titulo": g["titulo"],
                "archivo": g["archivo"],
                "curso": curso["nombre"],
                "periodo": curso["periodo"],
                "grabacion": g["url"],
            })

    total = len(pendientes)
    log("SUCCESS", "#22c55e", f"{total} grabaciones por bajar ({ya} ya descargadas o no disponibles)")
    if not pendientes:
        return {"ok": 0, "fail": 0}

    sesion_api(sesion_dir, log=log)   # asegura sesión UTP vigente (login solo si el token venció)

    log("INFO", "gray", "Exportando sesión...")
    storage = exportar_sesion(sesion_dir)

    ok = 0
    fail = 0
    procesados = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futuros = {pool.submit(_descargar_uno, r, storage, base): r for r in pendientes}
        for fut in as_completed(futuros):
            procesados += 1
            try:
                exito, msg = fut.result()
                if exito:
                    ok += 1
                    log("SUCCESS", "#22c55e", msg)
                else:
                    fail += 1
                    log("WARN", "#f59e0b", msg)
            except Exception as e:
                fail += 1
                log("WARN", "#f59e0b", f"excepción: {e}")
            progreso(procesados, total)

    log("SUCCESS", "#22c55e", f"Descarga Zoom completa — {ok} ok, {fail} fallidas")
    return {"ok": ok, "fail": fail}
