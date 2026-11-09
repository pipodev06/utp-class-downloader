"""
Descarga real de grabaciones Zoom a partir de lo que ya listó scrape.listar_todo.
Exporta la sesión de Playwright y descarga cada grabación en paralelo (headless) a:
  BASE_DIR/<ciclo>/<curso>/videos/
Portado de zoom_download.py del proyecto original.
"""
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from playwright.sync_api import TimeoutError as PwTimeout, sync_playwright

import auth
from scrape import sanitizar, sesion_api

ERRORES_ZOOM = [
    "esta grabación no existe", "this recording does not exist",
    "recording does not exist", "3.301", "3301",
    "no longer available", "ya no está disponible", "has been deleted",
]


_RE_BOTON_DESCARGA = re.compile(r"^(download|descargar)\s*\(", re.I)
ZOOM_SSO = "https://utpvirtual.zoom.us/web/sso/login?en=signin"


class ZoomPideLogin(Exception):
    """La grabación redirigió a 'Sign In | Zoom': la sesión no tiene cookies de Zoom (SSO UTP vía Microsoft)."""


def _pide_login(page) -> bool:
    return "zoom.us/signin" in page.url or "/web/sso/" in page.url


def _login_zoom(page, log=print):
    """SSO de Zoom de la UTP: Microsoft con <UTP_USER>@utp.edu.pe + UTP_PASS (sin MFA, probado 2026-11-09).
    Acepta "¿Mantener la sesión iniciada?" para que las cookies de Zoom duren entre corridas."""
    if not auth.UTP_USER or not auth.UTP_PASS:
        raise ZoomPideLogin("Faltan UTP_USER/UTP_PASS para iniciar sesión en Zoom")
    correo = auth.UTP_USER if "@" in auth.UTP_USER else f"{auth.UTP_USER}@utp.edu.pe"
    log("INFO", "gray", "Iniciando sesión en Zoom (SSO UTP / Microsoft)...")
    page.goto(ZOOM_SSO, wait_until="domcontentloaded", timeout=40000)
    page.get_by_role("button", name="Continue").click()
    page.wait_for_url("**login.microsoftonline.com/**", timeout=30000)
    page.locator("input[name=loginfmt]").fill(correo)
    page.locator("#idSIButton9").click()
    try:
        page.locator("input[name=passwd]").wait_for(state="visible", timeout=20000)
    except PwTimeout:
        raise ZoomPideLogin("Microsoft no aceptó el correo UTP para Zoom") from None
    page.locator("input[name=passwd]").fill(auth.UTP_PASS)
    page.locator("#idSIButton9").click()
    for _ in range(30):
        page.wait_for_timeout(1000)
        if "zoom.us" in page.url and not _pide_login(page):
            log("SUCCESS", "#22c55e", "Sesión de Zoom iniciada")
            return
        error = page.locator("#passwordError")
        if error.count() and error.is_visible():
            raise ZoomPideLogin("Microsoft rechazó la contraseña para Zoom")
        mantener = page.locator("#KmsiCheckboxField, #idBtn_Back")
        if mantener.count() and mantener.first.is_visible():
            page.locator("#idSIButton9").click()   # ¿Mantener la sesión iniciada? → Sí
    raise ZoomPideLogin("El login de Zoom no terminó (¿pide un código de verificación?)")


def exportar_sesion(sesion_dir: str, url_prueba: str, log=print) -> dict:
    """Cookies de la sesión para los navegadores de descarga. Antes comprueba con una grabación
    que Zoom la acepte; si redirige a Sign In, inicia sesión por SSO y vuelve a comprobar."""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(user_data_dir=sesion_dir, headless=True)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url_prueba, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(3000)
            if _pide_login(page):
                _login_zoom(page, log)
                page.goto(url_prueba, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(3000)
                if _pide_login(page):
                    raise ZoomPideLogin("Zoom sigue pidiendo iniciar sesión después del SSO")
            return ctx.storage_state()
        finally:
            ctx.close()


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

            if _pide_login(page):
                raise ZoomPideLogin()   # sin cookies de Zoom: no tiene sentido esperar ni marcar .fail

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
                # el botón real dice "Download (182 MB)"; hay otros con "Download" (Download Center,
                # Download the Zoom app) que sacan de la página, por eso se exige el tamaño entre paréntesis
                for btn in page.query_selector_all("a, button"):
                    try:
                        txt = (btn.text_content() or "").strip()
                        if _RE_BOTON_DESCARGA.match(txt) and btn.is_visible():
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

        except ZoomPideLogin:
            raise
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

    log("INFO", "gray", "Comprobando sesión de Zoom...")
    try:
        storage = exportar_sesion(sesion_dir, pendientes[0]["grabacion"], log)
    except ZoomPideLogin as e:
        log("WARN", "#f59e0b", f"Zoom: {e}")
        return {"ok": 0, "fail": 0, "zoom_login": True}

    ok = 0
    fail = 0
    procesados = 0
    pide_login = False
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
            except ZoomPideLogin:
                if not pide_login:   # se corta todo: las demás grabaciones darían lo mismo
                    pide_login = True
                    pool.shutdown(wait=False, cancel_futures=True)
            except Exception as e:
                fail += 1
                log("WARN", "#f59e0b", f"excepción: {e}")
            progreso(procesados, total)

    if pide_login:
        log("WARN", "#f59e0b", "Zoom pide iniciar sesión (SSO UTP con Microsoft) — descarga detenida, "
            "no se marcó ninguna grabación como fallida")
        return {"ok": ok, "fail": fail, "zoom_login": True}
    log("SUCCESS", "#22c55e", f"Descarga Zoom completa — {ok} ok, {fail} fallidas")
    return {"ok": ok, "fail": fail}
