"""
Login del portal UTP (Keycloak en auth.utp.edu.pe) con UTP_USER/UTP_PASS del .env o de ⚙.
Zoom usa otro login (SSO Microsoft): ver descargar_zoom._login_zoom.
"""

import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

load_dotenv()
UTP_USER = os.getenv("UTP_USER")
UTP_PASS = os.getenv("UTP_PASS")

# solo estos servidores pueden recibir la contraseña: se compara el hostname exacto (antes se buscaba
# "login"/"auth" en cualquier parte de la URL, y cualquier sitio con esa palabra calzaba)
HOSTS_LOGIN = {"auth.utp.edu.pe", "sso.utp.edu.pe"}


def _host_login(url: str) -> bool:
    u = urlparse(url)
    return u.scheme == "https" and (u.hostname or "") in HOSTS_LOGIN


def necesita_login(page) -> bool:
    return _host_login(page.url)


def esperar_red(page, timeout: int = 15000):
    """Espera a que la red se calme. El portal UTP nunca llega a 'networkidle'
    real (analytics/polling de fondo), así que un timeout aquí no es un error —
    seguimos igual, la página ya cargó lo que necesitamos."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeoutError:
        pass


def login(page):
    """Loguea si detecta página de autenticación. Retorna True si hizo login."""
    if not necesita_login(page):
        return False

    if not UTP_USER or not UTP_PASS:
        raise RuntimeError("UTP_USER y UTP_PASS deben estar en .env — configúralos en ⚙️ Settings")

    # Keycloak / formulario estándar
    try:
        page.wait_for_selector(
            "input[type='text'], input[type='email'], input[id='username']",
            timeout=10000,
        )
    except Exception:
        raise RuntimeError("No se encontró formulario de login — ¿el portal cambió su URL?")

    # usuario
    for sel in ["input[id='username']", "input[name='username']", "input[type='email']", "input[type='text']"]:
        if page.query_selector(sel):
            page.fill(sel, UTP_USER)
            break

    # contraseña: se vuelve a comprobar el servidor justo antes de escribirla
    if not _host_login(page.url):
        raise RuntimeError(f"El login llevó a un sitio inesperado ({urlparse(page.url).hostname})")
    try:
        page.fill("input[type='password']", UTP_PASS)
    except Exception:
        raise RuntimeError("No se encontró campo de contraseña en el formulario de login")

    # submit
    for sel in ["input[type='submit']", "button[type='submit']", "button#kc-login"]:
        if page.query_selector(sel):
            page.click(sel)
            break

    esperar_red(page)
    return True


def navegar(page, url: str):
    """Navega a URL y loguea automáticamente si es necesario."""
    page.goto(url)
    esperar_red(page)
    if necesita_login(page):
        login(page)
        esperar_red(page)
