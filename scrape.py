"""
Lógica de scraping (sin Qt) — login + listar cursos/materiales/videos.
Reusa auth.py para el login; el resto está portado de scraper.py original.
"""
import base64
import html
import json
import re
from pathlib import Path
from urllib.parse import unquote

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


# archivos enlazados DENTRO de las lecturas (contenido HTML): documentos y videos de la UTP.
# mp3 (audios de Inglés) e imágenes (banners) se dejan fuera a propósito.
EXT_INCRUSTADOS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".mp4", ".m4v"}
_RE_ENLACE_HTML = re.compile(r'<(?:a|source|video|embed)\b[^>]*?(?:href|src)="(https?://[^"]+)"', re.I)
_RE_YOUTUBE = re.compile(r'(?:href|src)="(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^"]+)"', re.I)
_RE_YOUTUBE_ID = re.compile(r"(?:embed/|watch\?v=|youtu\.be/|shorts/)([\w-]{11})")


_RE_PREFIJO_EMOJI = re.compile(r"^[^\w(¿¡]+")       # '📺 Video...' → 'Video...'
_RE_SUFIJO_S3 = re.compile(r"(?:_[A-Z0-9]{6})+$")    # 'Lectura_WGZAGL_ISVGIB' → 'Lectura'


def limpiar_titulo(titulo: str) -> str:
    """Quita emojis/símbolos del inicio ('📝', '🔴 ') que el portal pone en los títulos."""
    return _RE_PREFIJO_EMOJI.sub("", titulo or "").strip()


def _nombre_original(url: str) -> str:
    """'.../Semana%2B01%2B-%2BLectura_WGZAGL.pdf' → 'Semana 01 - Lectura' (sin extensión)."""
    base = unquote(unquote(url.split("?")[0].rsplit("/", 1)[-1])).replace("+", " ")
    return _RE_SUFIJO_S3.sub("", Path(base).stem).strip()


def _incrustados(item: dict) -> list[tuple[str, str]]:
    """[(url, nombre_original)] de archivos útiles dentro de una lectura HTML o MULTIMEDIA."""
    meta = item.get("metadata") or {}
    urls = [f.get("url") or "" for f in meta.get("formats") or []]
    urls += _RE_ENLACE_HTML.findall(meta.get("contentHtml") or "")
    resultado = []
    for url in urls:
        url = html.unescape(url)
        if "upload-file-storage" in url and Path(unquote(url.split("?")[0])).suffix.lower() in EXT_INCRUSTADOS:
            resultado.append((url, _nombre_original(url)))
    return resultado


def materiales_descargables(items: list[dict]) -> list[dict]:
    """Archivos descargables del curso: [{archivo, url}]. Única fuente del nombre en disco.
    Incluye los archivos sueltos (FILE) y los enlazados dentro de las lecturas; cada URL una sola vez."""
    resultado = []
    usados: dict = {}
    vistos: set = set()
    # 1ª pasada: archivos sueltos (nombres históricos, no deben cambiar)
    for item in items:
        tipo = (item.get("type") or "").upper()
        meta = item.get("metadata") or {}
        if tipo in SKIP_TIPOS or tipo == "MULTIMEDIA":
            continue
        url = (meta.get("url") or meta.get("videoUrl") or meta.get("fileUrl") or
               meta.get("src") or meta.get("link") or "")
        if not url or not url.startswith("http"):
            continue
        es_s3 = "s3.amazonaws.com" in url
        ext = Path(url.split("?")[0]).suffix.lower()
        if not es_s3 and ext not in EXT_OK:
            continue
        if url in vistos:
            continue
        vistos.add(url)
        titulo = item.get("title") or item.get("name") or "archivo"
        base = sanitizar(f"S{item.get('_week') or 0:02d}_{titulo}")
        resultado.append({"archivo": _nombre_unico(base, usados) + (ext or ".bin"), "url": url})

    # 2ª pasada: archivos enlazados dentro de las lecturas (si no salieron ya como sueltos)
    for item in items:
        if (item.get("type") or "").upper() not in ("HTML", "MULTIMEDIA"):
            continue
        titulo = limpiar_titulo(item.get("title")) or "lectura"
        for url, original in _incrustados(item):
            if url in vistos:
                continue
            vistos.add(url)
            ext = Path(unquote(url.split("?")[0])).suffix.lower()
            base = sanitizar(f"S{item.get('_week') or 0:02d}_{titulo} - {original}")
            resultado.append({"archivo": _nombre_unico(base, usados) + ext, "url": url})
    return resultado


def enlaces_youtube(items: list[dict]) -> list[dict]:
    """Videos de YouTube citados en el curso (lecturas HTML y enlaces URL): [{semana, titulo, url}].
    No se descargan (términos de YouTube): solo se guardan para abrirlos rápido."""
    resultado = []
    vistos: set = set()
    for item in items:
        meta = item.get("metadata") or {}
        texto = (meta.get("contentHtml") or "") + f' href="{meta.get("url") or ""}"'
        for url in _RE_YOUTUBE.findall(texto):
            m = _RE_YOUTUBE_ID.search(html.unescape(url))
            if not m or m.group(1) in vistos:
                continue
            vistos.add(m.group(1))
            resultado.append({
                "semana": item.get("_week") or 0,
                "titulo": (item.get("title") or "").strip(),
                "url": f"https://www.youtube.com/watch?v={m.group(1)}",
            })
    return resultado


def escribir_indice_youtube(carpeta: Path, nombre_curso: str, enlaces: list[dict]) -> bool:
    """Guarda <curso>/youtube.html con los enlaces agrupados por semana (doble clic → navegador).
    Devuelve True si el archivo cambió."""
    if not enlaces:
        return False
    filas = []
    semana_actual = None
    for e in sorted(enlaces, key=lambda e: e["semana"]):
        if e["semana"] != semana_actual:
            semana_actual = e["semana"]
            filas.append(f"<h2>{'Semana ' + str(semana_actual) if semana_actual else 'General'}</h2>")
        filas.append(f'<p><a href="{e["url"]}" target="_blank">{html.escape(e["titulo"] or e["url"])}</a></p>')
    contenido = (
        '<!doctype html><meta charset="utf-8">'
        f"<title>YouTube — {html.escape(nombre_curso)}</title>"
        "<style>body{font:15px Segoe UI,sans-serif;max-width:760px;margin:32px auto;padding:0 16px;"
        "background:#0e1013;color:#e5e7eb}h1{font-size:20px}h2{font-size:15px;color:#9aa1ac;"
        "margin-top:24px}a{color:#3b82f6;text-decoration:none}a:hover{text-decoration:underline}</style>"
        f"<h1>{html.escape(nombre_curso)} — videos de YouTube</h1>" + "".join(filas)
    )
    destino = carpeta / "youtube.html"
    if destino.exists() and destino.read_text(encoding="utf-8") == contenido:
        return False
    carpeta.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")
    return True


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
