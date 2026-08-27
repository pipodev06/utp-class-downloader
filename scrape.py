"""
Lógica de scraping (sin Qt) — login + listar cursos/materiales/videos.
Reusa auth.py para el login; el resto está portado de scraper.py original.
"""
import base64
import json
import re
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

import auth

API = "https://api-pao.utpxpedition.com"
BASE_URL = "https://class.utp.edu.pe"

# la API de cursos solo trae el código crudo ("2263"), no una etiqueta legible —
# mismo patrón que config.py del proyecto original: "22" + último dígito del año + 2=I/3=II
_RE_PERIODO = re.compile(r"^22([0-9])([23])$")
_PERIODO_ROMANO = {"2": "I", "3": "II"}


def resolver_ciclo(periodo: str) -> str:
    m = _RE_PERIODO.match(periodo or "")
    if not m:
        return periodo or "sin_ciclo"
    anio = 2020 + int(m.group(1))
    return f"{anio}-{_PERIODO_ROMANO[m.group(2)]}"


def sanitizar(nombre: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", nombre).strip()[:120]

SKIP_TIPOS = {"HTML", "FORUM", "TASK", "QUIZ", "SURVEY", "URL",
              "TEXT", "LINK", "H5P", "HOMEWORK", "ZOOM", "EVALUATION"}

EXT_OK = {".pdf", ".pptx", ".ppt", ".docx", ".doc",
          ".xlsx", ".xls", ".zip", ".rar", ".7z",
          ".mp4", ".mp3", ".png", ".jpg", ".jpeg"}


def obtener_token(sesion_dir: str, log=print) -> tuple[str, str, dict]:
    capturado = {}

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(user_data_dir=sesion_dir, headless=False)
        page = context.pages[0] if context.pages else context.new_page()

        def on_request(req):
            if "api-pao.utpxpedition.com" in req.url and not capturado.get("token"):
                cabecera = req.headers.get("authorization", "")
                if cabecera.startswith("Bearer "):
                    capturado["token"] = cabecera.split(" ", 1)[1]
                    capturado["headers"] = dict(req.headers)

        page.on("request", on_request)
        log("INFO", "gray", "Navegando al portal...")
        auth.navegar(page, f"{BASE_URL}/student/courses")
        page.wait_for_timeout(2000)

        if not capturado.get("token"):
            page.reload()
            page.wait_for_timeout(3000)

        for _ in range(30):
            if capturado.get("token"):
                break
            page.wait_for_timeout(500)

        context.close()

    token = capturado.get("token", "")
    if not token:
        raise RuntimeError("No se capturó el token — verifica que el portal carga correctamente")

    payload = token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    decoded = json.loads(base64.b64decode(payload))
    student_id = decoded.get("sub", "")

    log("SUCCESS", "#22c55e", f"Sesión iniciada y guardada — Student ID: {student_id}")
    return token, student_id, capturado.get("headers", {})


def api_get(url: str, headers: dict):
    try:
        res = requests.get(url, headers=headers, timeout=30)
        if not res.ok:
            return None
        return res.json()
    except Exception:
        return None


def obtener_cursos(student_id: str, headers: dict) -> list[dict]:
    data = api_get(f"{API}/learning/student/{student_id}/dashboard-courses", headers)
    if not data:
        return []
    items = data if isinstance(data, list) else data.get("data", [])
    cursos = []
    for c in items:
        if c.get("courseId") and c.get("sectionId"):
            cursos.append({
                "nombre":    c.get("name", "sin_nombre"),
                "courseId":  c["courseId"],
                "sectionId": c["sectionId"],
                "periodo":   str(c.get("period", "")),
            })
    return cursos


def obtener_contenido(course_id: str, section_id: str, headers: dict) -> list[dict]:
    resp = api_get(f"{API}/course/student/courses/{course_id}/sections/{section_id}/full", headers)
    if not resp:
        return []
    items = []
    for unity in (resp.get("data") or {}).get("unities", []):
        for theme in unity.get("themes", []):
            week = theme.get("weekNumber", 0)
            for content in theme.get("contents", []):
                content["_week"] = week
                items.append(content)
    return items


def obtener_zoom(course_id: str, section_id: str, headers: dict) -> list[dict]:
    resp = api_get(
        f"{API}/course/student/video-conference/meeting"
        f"?courseId={course_id}&sectionId={section_id}", headers,
    )
    if not resp:
        return []
    return (resp.get("data") or {}).get("listVideoConferenceResponse", [])


def contar_materiales(items: list[dict]) -> int:
    total = 0
    for item in items:
        tipo = (item.get("type") or "").upper()
        meta = item.get("metadata") or {}
        if tipo in SKIP_TIPOS:
            continue
        url = (meta.get("url") or meta.get("videoUrl") or meta.get("fileUrl") or
               meta.get("src") or meta.get("link") or "")
        if not url or not url.startswith("http"):
            continue
        es_s3 = "s3.amazonaws.com" in url
        ext = Path(url.split("?")[0]).suffix.lower()
        if not es_s3 and ext not in EXT_OK:
            continue
        total += 1
    return total


def listar_todo(
    sesion_dir: str, log=print,
    progreso=lambda actual, total: None,
    curso_listo=lambda curso: None,
) -> list[dict]:
    """Login + token + recorre todos los cursos. Retorna [{nombre, periodo, materiales, videos}].
    Llama curso_listo(curso) apenas cada uno termina, para poder pintarlo en vivo."""
    _, student_id, headers = obtener_token(sesion_dir, log=log)

    log("INFO", "gray", "Consultando cursos...")
    cursos = obtener_cursos(student_id, headers)
    log("SUCCESS", "#22c55e", f"{len(cursos)} cursos encontrados")

    total = len(cursos)
    resultado = []
    for i, curso in enumerate(cursos, start=1):
        items = obtener_contenido(curso["courseId"], curso["sectionId"], headers)
        materiales = contar_materiales(items)
        zoom = obtener_zoom(curso["courseId"], curso["sectionId"], headers)
        videos = len([z for z in zoom if z.get("playUrl")])
        entrada = {
            "nombre": curso["nombre"], "periodo": resolver_ciclo(curso["periodo"]),
            "materiales": materiales, "videos": videos,
        }
        resultado.append(entrada)
        log("INFO", "gray", f"{curso['nombre']}: {materiales} materiales, {videos} videos")
        progreso(i, total)
        curso_listo(entrada)

    return resultado


def contar_archivos_locales(base_dir: str, ciclo: str, nombre_curso: str) -> dict:
    """Revisa si ya existen archivos/videos descargados en disco para este curso."""
    carpeta = Path(base_dir).expanduser() / ciclo / sanitizar(nombre_curso)
    archivos_dir = carpeta / "archivos"
    videos_dir = carpeta / "videos"

    n_archivos = len([f for f in archivos_dir.glob("*") if f.is_file()]) if archivos_dir.exists() else 0
    n_videos = len(list(videos_dir.glob("*.mp4"))) if videos_dir.exists() else 0

    return {"archivos_locales": n_archivos, "videos_locales": n_videos}
