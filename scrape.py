"""
Lógica de scraping (sin Qt) — login + listar cursos/materiales/videos.
Reusa auth.py para el login; el resto está portado de scraper.py original.
"""
import base64
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

import requests
import requests.adapters
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
    """Nombre válido en Windows. Los saltos de línea/tabs (vienen en algunos títulos del portal)
    pasan a espacio: un '\\n' en la ruta abortaba la descarga entera (WinError 123)."""
    nombre = re.sub(r"\s*[\x00-\x1f]+\s*", " ", nombre)
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

    student_id = _claims(token).get("sub", "")
    log("SUCCESS", "#22c55e", f"Sesión iniciada y guardada — Student ID: {student_id}")
    return token, student_id, capturado.get("headers", {})


def _claims(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))   # JWT usa base64 URL-safe


# El Bearer del portal dura 24 h: se guarda junto a la sesión de Playwright (sesion/, ignorada
# por git, ya contiene las cookies) y se reutiliza sin abrir Chromium mientras le queden > 10 min.
_MARGEN_TOKEN = 600
PARALELO_API = 8   # medido: 26 cursos en 2,1 s con 8 a la vez vs 27,8 s en serie


def _ruta_token(sesion_dir: str) -> Path:
    return Path(sesion_dir) / "token.json"


def token_vigente(sesion_dir: str) -> bool:
    try:
        datos = json.loads(_ruta_token(sesion_dir).read_text(encoding="utf-8"))
        return datos["exp"] - time.time() > _MARGEN_TOKEN
    except (OSError, ValueError, KeyError):
        return False


def invalidar_token(sesion_dir: str):
    _ruta_token(sesion_dir).unlink(missing_ok=True)


def sesion_api(sesion_dir: str, log=print) -> tuple[str, requests.Session]:
    """(student_id, Session HTTP con el Bearer). Reutiliza el token guardado si sigue vigente;
    si no, abre Chromium, se loguea y guarda el nuevo."""
    if token_vigente(sesion_dir):
        datos = json.loads(_ruta_token(sesion_dir).read_text(encoding="utf-8"))
        headers, student_id = datos["headers"], datos["student_id"]
        hasta = time.strftime("%d/%m %H:%M", time.localtime(datos["exp"]))
        log("INFO", "gray", f"Sesión reutilizada (vigente hasta {hasta}) — sin abrir el navegador")
    else:
        token, student_id, headers = obtener_token(sesion_dir, log=log)
        Path(sesion_dir).mkdir(exist_ok=True)
        _ruta_token(sesion_dir).write_text(
            json.dumps({"headers": headers, "student_id": student_id, "exp": _claims(token)["exp"]}),
            encoding="utf-8",
        )
    http = requests.Session()
    http.headers.update(headers)
    adaptador = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=PARALELO_API * 2)
    http.mount("https://", adaptador)
    return student_id, http


def api_get(url: str, http: requests.Session):
    """JSON de la API, o None si falla (red, 401/403 de token vencido, etc.)."""
    try:
        res = http.get(url, timeout=30)
        if not res.ok:
            return None
        return res.json()
    except (requests.RequestException, ValueError):
        return None


def obtener_cursos(student_id: str, http: requests.Session) -> list[dict]:
    data = api_get(f"{API}/learning/student/{student_id}/dashboard-courses", http)
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


def obtener_contenido(course_id: str, section_id: str, http: requests.Session) -> list[dict] | None:
    """Contenidos del curso con su semana en '_week'. None si la API falló (≠ curso vacío)."""
    resp = api_get(f"{API}/course/student/courses/{course_id}/sections/{section_id}/full", http)
    if resp is None:
        return None
    items = []
    for unity in (resp.get("data") or {}).get("unities", []):
        for theme in unity.get("themes", []):
            week = theme.get("weekNumber") or 0
            for content in theme.get("contents", []):
                content["_week"] = week
                items.append(content)
    return items


def obtener_zoom(course_id: str, section_id: str, http: requests.Session) -> list[dict] | None:
    resp = api_get(
        f"{API}/course/student/video-conference/meeting"
        f"?courseId={course_id}&sectionId={section_id}", http,
    )
    if resp is None:
        return None
    return (resp.get("data") or {}).get("listVideoConferenceResponse", [])


def _nombre_unico(base: str, usados: dict) -> str:
    """Si el nombre ya salió en este curso, agrega ' (2)', ' (3)'...
    La primera aparición conserva el nombre de siempre, así no se re-descarga lo que ya existe."""
    usados[base] = usados.get(base, 0) + 1
    return base if usados[base] == 1 else f"{base} ({usados[base]})"


# ── organización en disco: <periodo>/<curso>/Semana NN/<archivo> (semana 0 → General) ──

def carpeta_semana(semana: int) -> str:
    return f"Semana {semana:02d}" if semana else "General"


def _ruta_material(semana: int, base_con_prefijo: str, ext: str) -> str:
    """'S05_Práctica (2)' → 'Semana 05/Práctica (2).pdf'.
    Es el nombre histórico (con prefijo, ya recortado a 120) sin 'S05_': así cada archivo
    descargado con el esquema viejo (archivos/S05_...) tiene un único destino al migrar."""
    return f"{carpeta_semana(semana)}/{base_con_prefijo[4:].strip()}{ext}"


_RE_SEMANA = re.compile(r"semana\s*(\d{1,2})", re.I)


def semana_de_texto(texto: str) -> int:
    """'Semana 1' / 'CÁLCULO II (21180) ( Semana 12 ) -Lunes' → 1 / 12; 0 si no dice."""
    m = _RE_SEMANA.search(texto or "")
    return int(m.group(1)) if m else 0


# archivos enlazados DENTRO de las lecturas (contenido HTML): documentos y videos de la UTP.
# mp3 (audios de Inglés) e imágenes (banners) se dejan fuera a propósito.
EXT_INCRUSTADOS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".mp4", ".m4v"}
# href/src con comillas dobles, simples o SIN comillas (el contenido migrado de Canvas trae
# href=https://...pdf sin comillas y se perdía). Grupos: 1 = "...", 2 = '...', 3 = sin comillas.
_VALOR_URL = r"""\s*=\s*(?:"(https?://[^"]+)"|'(https?://[^']+)'|(https?://[^\s"'<>]+))"""
_RE_ENLACE_HTML = re.compile(r"<(?:a|source|video|embed)\b[^>]*?\b(?:href|src)" + _VALOR_URL, re.I)
_RE_YOUTUBE_HTML = re.compile(r"\b(?:href|src)" + _VALOR_URL, re.I)
_ES_YOUTUBE = re.compile(r"^https?://(?:www\.)?(?:youtube\.com|youtu\.be)/", re.I)


def _urls(patron: re.Pattern, texto: str) -> list[str]:
    return [next(g for g in grupos if g) for grupos in patron.findall(texto)]


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
    urls += _urls(_RE_ENLACE_HTML, meta.get("contentHtml") or "")
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
        semana = item.get("_week") or 0
        base = _nombre_unico(sanitizar(f"S{semana:02d}_{titulo}"), usados)
        resultado.append({"archivo": _ruta_material(semana, base, ext or ".bin"), "url": url})

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
            semana = item.get("_week") or 0
            base = _nombre_unico(sanitizar(f"S{semana:02d}_{titulo} - {original}"), usados)
            resultado.append({"archivo": _ruta_material(semana, base, ext), "url": url})
    return resultado


def enlaces_youtube(items: list[dict]) -> list[dict]:
    """Videos de YouTube citados en el curso (lecturas HTML y enlaces URL): [{semana, titulo, url}].
    No se descargan (términos de YouTube): solo se guardan para abrirlos rápido."""
    resultado = []
    vistos: set = set()
    for item in items:
        meta = item.get("metadata") or {}
        texto = (meta.get("contentHtml") or "") + f' href="{meta.get("url") or ""}"'
        for url in (u for u in _urls(_RE_YOUTUBE_HTML, texto) if _ES_YOUTUBE.match(u)):
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
    """Grabaciones con URL: [{titulo, archivo ('Semana NN/<nombre>', sin extensión), url}].
    Varias clases comparten título (ej. 'CURSO - 19591'), por eso el nombre se desambigua
    (por curso, igual que antes: el nombre de archivo no cambió, solo la carpeta)."""
    resultado = []
    usados: dict = {}
    for clase in zoom:
        url = clase.get("playUrl") or ""
        if not url:
            continue
        titulo = clase.get("title") or "sin_titulo"
        semana = semana_de_texto(clase.get("weekNumber")) or semana_de_texto(titulo)
        resultado.append({
            "titulo": titulo,
            "archivo": f"{carpeta_semana(semana)}/{_nombre_unico(sanitizar(titulo), usados)}",
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
            "id": item.get("contentId") or "",
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


def _armar_entrada(curso: dict, http: requests.Session) -> dict:
    """Una entrada por curso con TODO lo necesario para descargar sin volver a consultar la API."""
    items = obtener_contenido(curso["courseId"], curso["sectionId"], http)
    zoom = obtener_zoom(curso["courseId"], curso["sectionId"], http)
    return {
        "nombre": curso["nombre"], "periodo": resolver_ciclo(curso["periodo"]),
        "courseId": curso["courseId"], "sectionId": curso["sectionId"],
        "materiales": materiales_descargables(items or []),   # [{archivo, url}]
        "videos": grabaciones(zoom or []),                     # [{titulo, archivo, url}]
        "youtube": enlaces_youtube(items or []),
        "tareas": extraer_tareas(items or [], curso),
        "error": items is None or zoom is None,
    }


def listar_todo(
    sesion_dir: str, log=print,
    progreso=lambda actual, total: None,
    curso_listo=lambda curso: None,
    previos: list[dict] | None = None,
) -> list[dict]:
    """Recorre todos los cursos en paralelo (orden original). Si un curso falla en la API,
    se usa su versión de 'previos' (último listado) para no perder datos.
    Llama curso_listo(curso) apenas cada uno está listo, para pintarlo en vivo."""
    student_id, http = sesion_api(sesion_dir, log=log)

    log("INFO", "gray", "Consultando cursos...")
    cursos = obtener_cursos(student_id, http)
    if not cursos:   # el token guardado pudo ser revocado: un reintento con login nuevo
        invalidar_token(sesion_dir)
        student_id, http = sesion_api(sesion_dir, log=log)
        cursos = obtener_cursos(student_id, http)
    if not cursos:
        raise RuntimeError("La API no devolvió cursos — revisa tu conexión o vuelve a intentar")
    log("SUCCESS", "#22c55e", f"{len(cursos)} cursos encontrados")

    por_nombre = {c["nombre"]: c for c in previos or []}
    total = len(cursos)
    resultado = []
    with ThreadPoolExecutor(PARALELO_API) as pool:
        for i, entrada in enumerate(pool.map(lambda c: _armar_entrada(c, http), cursos), start=1):
            if entrada["error"]:
                previo = por_nombre.get(entrada["nombre"])
                log("WARN", "#f59e0b", f"{entrada['nombre']}: la API falló"
                    + (" — se muestra el último listado" if previo else ""))
                entrada = previo or entrada
            resultado.append(entrada)
            log("INFO", "gray", f"{entrada['nombre']}: {len(entrada['materiales'])} materiales, "
                f"{len(entrada['videos'])} videos, {len(entrada['tareas'])} tareas")
            progreso(i, total)
            curso_listo(entrada)

    fusionar_vistos(resultado, previos)
    return resultado


# ── caché del último listado + detección de tareas nuevas ──

DIAS_NUEVA = 3   # una tarea se marca "Nueva" los primeros 3 días desde que apareció


def fusionar_vistos(cursos: list[dict], previos: list[dict] | None):
    """Pone en cada tarea 'visto' = cuándo apareció por primera vez.
    Sin listado previo (primera vez) todas quedan como ya conocidas ('visto' vacío)."""
    if not previos:
        for c in cursos:
            for t in c["tareas"]:
                t.setdefault("visto", "")
        return
    vistos = {t["id"]: t.get("visto", "") for c in previos for t in c["tareas"]}
    ahora = datetime.now().isoformat(timespec="minutes")
    for c in cursos:
        for t in c["tareas"]:
            t["visto"] = vistos.get(t["id"], ahora)


def es_nueva(tarea: dict) -> bool:
    visto = tarea.get("visto")
    if not visto:
        return False
    return datetime.now() - datetime.fromisoformat(visto) < timedelta(days=DIAS_NUEVA)


VERSION_CACHE = 2   # subir si cambia la forma de las entradas: la caché vieja se ignora
# v2: 'archivo' pasó a ser ruta relativa al curso ('Semana 05/...') en materiales y videos


def guardar_cache(ruta: Path, cursos: list[dict]):
    ruta.parent.mkdir(exist_ok=True)
    datos = {"version": VERSION_CACHE, "fecha": datetime.now().isoformat(timespec="minutes"),
             "cursos": [{k: v for k, v in c.items() if k != "disco"} for c in cursos]}
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    temporal.replace(ruta)   # escritura atómica: un cierre a medias no corrompe la caché


def cargar_cache(ruta: Path) -> tuple[str, list[dict]] | None:
    """(fecha, cursos) del último listado, o None si no hay caché o es de otra versión."""
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if datos.get("version") != VERSION_CACHE:
            return None
        return datos["fecha"], datos["cursos"]
    except (OSError, ValueError, KeyError):
        return None


def estado_en_disco(base_dir: str, curso: dict) -> dict:
    """Compara archivo por archivo lo esperado del curso con lo que hay en disco.
    'videos_no_disp' = grabaciones marcadas .skip (Zoom ya las borró)."""
    carpeta = carpeta_curso(base_dir, curso)
    return {
        "materiales_ok": sum((carpeta / m["archivo"]).exists() for m in curso["materiales"]),
        "videos_ok": sum((carpeta / f"{v['archivo']}.mp4").exists() for v in curso["videos"]),
        "videos_no_disp": sum(
            (carpeta / f"{v['archivo']}.skip").exists() and not (carpeta / f"{v['archivo']}.mp4").exists()
            for v in curso["videos"]
        ),
    }


def carpeta_curso(base_dir: str, curso: dict) -> Path:
    """<base>/<periodo>/<curso>: aquí cuelgan 'Semana NN/', 'General/' y youtube.html."""
    return Path(base_dir).expanduser() / curso["periodo"] / sanitizar(curso["nombre"])
