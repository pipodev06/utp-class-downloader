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

1. Abre **⚙ Configuración** y pon tu usuario/contraseña de UTP, la carpeta donde quieres guardar los materiales, y cuántas grabaciones Zoom descargar en paralelo (1-8).
2. Dale a **Iniciar** — abre Chromium, loguea solo, y lista todos tus cursos (activos y de ciclos pasados) con cuántos materiales y videos tiene cada uno.
3. Al terminar, aparecen dos botones: **Todos los materiales** y **Todas las clases** (descarga masiva), y la app analiza sola qué ya tienes en disco (columna **En disco**).
4. Por curso, en la columna **Acciones**, puedes descargar materiales o clases de ese curso puntual.
5. Con **Seleccionar** activado, marca Materiales/Videos de varios cursos a la vez y usa **Descargar Seleccionados** para bajarlos todos juntos.
6. El botón **❯_** abre una ventana aparte con el log técnico completo de lo que está pasando.

Las descargas son reanudables: si ya bajaste la mitad de un curso, la próxima corrida solo baja lo que falta — nunca vuelve a descargar un archivo que ya existe.

## Estructura de archivos descargados

```
BASE_DIR/
├── 2025-I/
│   ├── MATEMÁTICA II/
│   │   ├── archivos/
│   │   │   ├── S01_Introducción.pdf
│   │   │   └── S02_Vectores.pptx
│   │   └── videos/
│   │       └── Semana 1 - Clase.mp4
│   └── ...
└── 2025-II/
    └── ...
```

## Archivos de marcador (grabaciones Zoom)

| Extensión | Significado |
|-----------|-------------|
| `.mp4` | Grabación descargada OK |
| `.skip` | Grabación eliminada por el profesor — no se reintenta |
| `.fail` | Falló el último intento (red, timeout) — se reintenta en la próxima corrida |

## Seguridad

- Tu usuario/contraseña de UTP se guardan solo en memoria mientras la app está abierta (no hay `.env` ni base de datos) — se piden de nuevo cada vez que abres el programa.
- Nada se envía a ningún servidor externo aparte del propio portal de UTP y Zoom.
- La sesión de Playwright (cookies de login) se guarda localmente en `sesion/` — no se sube al repositorio (ver `.gitignore`). Bórrala si cambias de cuenta.

## Compatibilidad

Probado en Windows 10/11. Debería funcionar en macOS/Linux (Playwright y PySide6 son multiplataforma) pero no se ha probado ahí todavía.
