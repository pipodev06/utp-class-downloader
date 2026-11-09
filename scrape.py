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
        return "Otros" if periodo == "9999" else (periodo or "sin_ciclo")
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
            week = theme.get("weekNumber") or 0
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


def _nombre_unico(base: str, usados: dict) -> str:
    """Si el nombre ya salió en este curso, agrega ' (2)', ' (3)'...
    La primera aparición conserva el nombre de siempre, así no se re-descarga lo que ya existe."""
    usados[base] = usados.get(base, 0) + 1
    return base if usados[base] == 1 else f"{base} ({usados[base]})"


def materiales_descargables(items: list[dict]) -> list[dict]:
    """Archivos descargables del curso: [{archivo, url}]. Única fuente del nombre en disco."""
    resultado = []
    usados: dict = {}
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
        titulo = item.get("title") or item.get("name") or "archivo"
        base = sanitizar(f"S{item.get('_week') or 0:02d}_{titulo}")
        resultado.append({"archivo": _nombre_unico(base, usados) + (ext or ".bin"), "url": url})
    return resultado


def grabaciones(zoom: list[dict]) -> list[dict]:
    """Grabaciones con URL: [{titulo, archivo (sin extensión), url}].
    Varias clases comparten título (ej. 'CURSO - 19591'), por eso el nombre se desambigua."""
    resultado = []
    usados: dict = {}
    for clase in zoom:
        url = clase.get("playUrl") or ""
        if not url:
            continue
        titulo = clase.get("title") or "sin_titulo"
        resultado.append({
            "titulo": titulo,
            "archivo": _nombre_unico(sanitizar(titulo), usados),
            "url": url,
        })
    return resultado


TIPOS_TAREA = {"HOMEWORK": "Tarea", "EVALUATION": "Evaluación", "FORUM": "Foro"}


def extraer_tareas(items: list[dict], curso: dict) -> list[dict]:
    """Tareas y evaluaciones del curso con su estado de entrega y enlace directo.
    Los foros solo entran si son calificados (los de consultas no cuentan)."""
    tareas = []
    for item in items:
        tipo = (item.get("type") or "").upper()
        meta = item.get("metadata") or {}
        if tipo not in TIPOS_TAREA or (tipo == "FORUM" and not meta.get("isQualified")):
            continue
        semana = item.get("_week") or 0
        tareas.append({
            "curso": curso["nombre"],
            "tipo": TIPOS_TAREA[tipo],
            "titulo": (item.get("title") or "").strip(),
            "estado": meta.get("status") or "",   # DELIVERED / NOT_DELIVERED / OUT_OF_DATE / SCHEDULED
            "calificada": bool(meta.get("isQualified")),
            "desde": item.get("visibleFrom") or "",
            "vence": item.get("visibleTo") or "",
            "url": (
                f"{BASE_URL}/student/courses/{curso['courseId']}/section/{curso['sectionId']}"
                f"/learnv2/week/{semana}/unit/{curso['sectionId']}/theme/{item.get('themeId')}"
                f"/content/{item.get('contentId')}/{tipo.lower()}/{item.get('contentId')}"
            ),
        })
    return tareas


def listar_todo(
    sesion_dir: str, log=print,
    progreso=lambda actual, total: None,
    curso_listo=lambda curso: None,
) -> list[dict]:
    """Login + token + recorre todos los cursos. Retorna una entrada por curso con los
    nombres de archivo esperados (para comparar con el disco) y sus tareas.
    Llama curso_listo(curso) apenas cada uno termina, para poder pintarlo en vivo."""
    _, student_id, headers = obtener_token(sesion_dir, log=log)

    log("INFO", "gray", "Consultando cursos...")
    cursos = obtener_cursos(student_id, headers)
    log("SUCCESS", "#22c55e", f"{len(cursos)} cursos encontrados")

    total = len(cursos)
    resultado = []
    for i, curso in enumerate(cursos, start=1):
        items = obtener_contenido(curso["courseId"], curso["sectionId"], headers)
        materiales = [m["archivo"] for m in materiales_descargables(items)]
        videos = [g["archivo"] for g in grabaciones(obtener_zoom(curso["courseId"], curso["sectionId"], headers))]
        tareas = extraer_tareas(items, curso)
        entrada = {
            "nombre": curso["nombre"], "periodo": resolver_ciclo(curso["periodo"]),
            "materiales": materiales, "videos": videos, "tareas": tareas,
        }
        resultado.append(entrada)
        log("INFO", "gray", f"{curso['nombre']}: {len(materiales)} materiales, {len(videos)} videos, {len(tareas)} tareas")
        progreso(i, total)
        curso_listo(entrada)

    return resultado


def estado_en_disco(base_dir: str, curso: dict) -> dict:
    """Compara archivo por archivo lo esperado del curso con lo que hay en disco.
    'videos_no_disp' = grabaciones marcadas .skip (Zoom ya las borró)."""
    carpeta = Path(base_dir).expanduser() / curso["periodo"] / sanitizar(curso["nombre"])
    archivos_dir = carpeta / "archivos"
    videos_dir = carpeta / "videos"
    return {
        "materiales_ok": sum((archivos_dir / a).exists() for a in curso["materiales"]),
        "videos_ok": sum((videos_dir / f"{v}.mp4").exists() for v in curso["videos"]),
        "videos_no_disp": sum(
            (videos_dir / f"{v}.skip").exists() and not (videos_dir / f"{v}.mp4").exists()
            for v in curso["videos"]
        ),
    }
