# UTP Class Downloader

Aplicación de escritorio (PySide6) para descargar materiales y grabaciones Zoom de tus cursos en [class.utp.edu.pe](https://class.utp.edu.pe) — sin entrar curso por curso a mano.

## Requisitos

- Python 3.10+
- Google Chrome / Chromium (lo instala Playwright automáticamente)

## Instalación

```bash
git clone <url> utp-class-downloader
cd utp-class-downloader
python -m venv venv
```

**Windows (PowerShell):**
```powershell
venv\Scripts\pip install -r requirements.txt
venv\Scripts\playwright install chromium
venv\Scripts\python main_ui.py
```

**Linux / Mac:**
```bash
venv/bin/pip install -r requirements.txt
venv/bin/playwright install chromium
venv/bin/python main_ui.py
```

## Uso

1. Credenciales: copia `.env.example` a `.env` y completa `UTP_USER`/`UTP_PASS`, o escríbelas en **⚙ Configuración** (ahí no se guardan).
2. En **⚙** elige la carpeta donde guardas las descargas y cuántas grabaciones Zoom bajar en paralelo (1-8). Esto sí se recuerda (`config.json`).
3. Dale a **Iniciar** — abre Chromium, loguea solo, y lista todos tus cursos (activos y de ciclos pasados).
4. Pestaña **Cursos**: las columnas **Materiales** y **Clases** muestran `descargados / total`, comparando archivo por archivo con tu carpeta. Verde = nada más por bajar, ámbar = faltan (el tooltip dice cuántos y cuántas grabaciones ya no existen en Zoom). El resumen de arriba suma lo que falta del periodo elegido.
5. Descarga por curso con los botones **Materiales** / **Clases**, todo junto con **Todos los materiales** / **Todas las clases**, o activa **Seleccionar** para marcar varios cursos y usar **Descargar Seleccionados**. Al terminar, los conteos se actualizan solos.
6. Pestaña **Tareas**: tareas y evaluaciones del periodo con su estado (Pendiente, Entregada, Vencida, Programada), fecha límite, tiempo restante y botón **Abrir** que te lleva directo a la tarea en el portal. En rojo las pendientes que vencen en menos de 48 h; ★ = calificada.
7. El botón **❯_** abre el log técnico; también queda guardado en `logs/app.log`.

Los materiales incluyen también los PDF, Word, PowerPoint, Excel y videos de la UTP que vienen enlazados dentro de las lecturas de cada semana. Los videos de YouTube no se descargan: quedan en `youtube.html` dentro de la carpeta del curso, ordenados por semana.

Las descargas son reanudables: la próxima corrida solo baja lo que falta — nunca vuelve a descargar un archivo que ya existe.

> **Zoom borra las grabaciones a los pocos meses.** Descarga las clases del ciclo en curso antes de que terminen; las de ciclos viejos suelen salir como `.skip`.

## Estructura de archivos descargados

Cada curso tiene una carpeta por semana con todo lo de esa semana junto: lecturas, PDF, Office, videos de la UTP y la grabación de Zoom. Si tienes descargas hechas con versiones anteriores (`archivos\S05_…`, `videos\…`), la app las mueve sola a esta estructura la primera vez que lista tus cursos; no borra nada que sea distinto.

```
BASE_DIR/
├── 2025-I/
│   ├── MATEMÁTICA II/
│   │   ├── General/                 (material sin semana: sílabo, guías del curso)
│   │   ├── Semana 01/
│   │   │   ├── Introducción.pdf
│   │   │   └── MATEMÁTICA II (30978) ( Semana 1 ) -Martes.mp4
│   │   ├── Semana 02/
│   │   │   └── Vectores.pptx
│   │   └── youtube.html
│   └── ...
└── 2025-II/
    └── ...
```

## Archivos de marcador (grabaciones Zoom)

| Extensión | Significado |
|-----------|-------------|
| `.mp4` | Grabación descargada OK |
| `.skip` | Grabación que ya no existe en Zoom (expiró o la borró el profesor) — no se reintenta |
| `.fail` | Falló el último intento (red, timeout) — se reintenta en la próxima corrida |

## Seguridad

- Tu usuario/contraseña de UTP viven en tu `.env` local (ignorado por git) o solo en memoria si los escribes en ⚙. `config.json` nunca guarda la contraseña.
- Nada se envía a ningún servidor externo aparte del propio portal de UTP y Zoom.
- La sesión de Playwright (cookies de login) se guarda localmente en `sesion/` — no se sube al repositorio (ver `.gitignore`). Bórrala si cambias de cuenta.

## Compatibilidad

Probado en Windows 10/11. Debería funcionar en macOS/Linux (Playwright y PySide6 son multiplataforma) pero no se ha probado ahí todavía.
