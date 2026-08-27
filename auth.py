"""
Módulo de autenticación reutilizable.
Detecta si hay login pendiente y usa credenciales de .env.
"""
import os
from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

load_dotenv()
UTP_USER = os.getenv("UTP_USER")
UTP_PASS = os.getenv("UTP_PASS")

LOGIN_INDICATORS = ["sso.utp.edu.pe", "login", "signin", "auth", "keycloak"]

def necesita_login(page) -> bool:
    url = page.url.lower()
    return any(ind in url for ind in LOGIN_INDICATORS)

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

    print(f"→ Sesión expirada. Logueando como {UTP_USER}...")

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

    # contraseña
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
    print(f"✓ Login completado → {page.url}")
    return True

def navegar(page, url: str):
    """Navega a URL y loguea automáticamente si es necesario."""
    page.goto(url)
    esperar_red(page)
    if necesita_login(page):
        login(page)
        esperar_red(page)
