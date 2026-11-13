<div align="center">

# UTP Class Downloader

Aplicación de escritorio para estudiantes de la UTP: descarga en lote los materiales y las grabaciones Zoom de tus cursos en [class.utp.edu.pe](https://class.utp.edu.pe), sin entrar curso por curso.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
![PySide6](https://img.shields.io/badge/PySide6-Qt-41cd52)
![Playwright](https://img.shields.io/badge/Playwright-Chromium-2ead33)
![Windows](https://img.shields.io/badge/Windows-10%2F11-0078d4)
![Licencia](https://img.shields.io/badge/licencia-MIT-2da44e)

[Descargar](https://github.com/pipodev06/utp-class-downloader/releases) · [Funciones](#funciones) · [Instalación](#instalación) · [Configuración](#configuración) · [Releases](#releases)

</div>

## Funciones

| Cursos | Descargas |
|---|---|
| Activos y de ciclos pasados · cuánto te falta bajar de cada uno | Materiales (PDF, Office, videos de la UTP enlazados en las lecturas) y grabaciones Zoom · por curso, todo junto o por selección · de 1 a 8 grabaciones en paralelo |
| **Orden** | **Tareas** |
| Una carpeta por semana · videos de YouTube listados en `youtube.html` · reanudable: nunca vuelve a bajar un archivo que ya tienes | Estado y fecha límite de tus tareas y evaluaciones · botón para abrirlas en el portal |

## Tecnologías

| Pieza | Tecnología |
|---|---|
| Lenguaje | Python |
| Interfaz | PySide6 |
| Navegador automatizado | Playwright (Chromium) |

## Instalación

Sin instalar nada: descarga `utp-class-downloader.exe` desde [Releases](#releases) (Windows 10/11). Desde el código necesitas Python 3.10+ (probado solo en Windows; en macOS y Linux debería funcionar, pero no se ha probado).

```bash
git clone https://github.com/pipodev06/utp-class-downloader.git && cd utp-class-downloader
python -m venv venv
venv\Scripts\pip install -r requirements.txt       # Linux/macOS: venv/bin/pip
venv\Scripts\playwright install chromium            # Linux/macOS: venv/bin/playwright
venv\Scripts\python main_ui.py                      # Linux/macOS: venv/bin/python
```

1. En **⚙ Configuración**, elige la carpeta de descargas y cuántas grabaciones bajar en paralelo (1 a 8).
2. Pulsa **Iniciar**.

## Configuración

| Variable | Para qué |
|---|---|
| `UTP_USER` | Tu usuario del portal UTP (código de alumno) |
| `UTP_PASS` | Tu contraseña del portal UTP |

Son opcionales: puedes copiar `.env.example` a `.env`, o escribirlas en **⚙ Configuración** (ahí solo quedan en memoria). `config.json` guarda la carpeta y el paralelismo, nunca la contraseña. La app solo se conecta al portal de la UTP y a Zoom.

> [!WARNING]
> - Zoom borra las grabaciones a los pocos meses: descarga las del ciclo en curso antes de que termine.
> - Al cambiar de cuenta, la sesión anterior sigue en `sesion/`: bórrala antes de entrar con otra cuenta.

## Releases

Descarga `utp-class-downloader.exe` desde [Releases](https://github.com/pipodev06/utp-class-downloader/releases) y ábrelo. La primera vez instala Chromium sola (~190 MB, necesita internet). Las versiones siguen `vMAYOR.MENOR.PARCHE`.

## Licencia

[MIT](LICENSE).
