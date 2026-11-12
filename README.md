# UTP Class Downloader

Aplicación de escritorio para estudiantes de la UTP: descarga en lote los materiales y las grabaciones Zoom de tus cursos en [class.utp.edu.pe](https://class.utp.edu.pe), sin entrar curso por curso.

## Qué hace
- Lista todos tus cursos (activos y de ciclos pasados) y muestra cuánto te falta bajar de cada uno.
- Descarga materiales (PDF, Office, videos de la UTP enlazados en las lecturas) y grabaciones Zoom, por curso, todo junto o por selección.
- Guarda todo en una carpeta por semana. Los videos de YouTube quedan listados en `youtube.html`.
- Descargas reanudables: nunca vuelve a bajar un archivo que ya tienes.
- Pestaña **Tareas** con el estado y la fecha límite de tus tareas y evaluaciones, y un botón para abrirlas en el portal.
- Zoom borra las grabaciones a los pocos meses: descarga las del ciclo en curso antes de que termine.

## Tecnologías
- Python + PySide6 (interfaz) + Playwright (navegador Chromium automatizado)

## Requisitos
- Para el `.exe`: Windows 10/11, sin nada más que instalar
- Desde el código: Python 3.10+ (probado solo en Windows; en macOS y Linux debería funcionar, pero no se ha probado)

## Cómo levantarlo
1. `git clone https://github.com/pipodev06/utp-class-downloader.git && cd utp-class-downloader`
2. `python -m venv venv`
3. Windows: `venv\Scripts\pip install -r requirements.txt` y `venv\Scripts\playwright install chromium` · Linux/macOS: igual con `venv/bin/`
4. `venv\Scripts\python main_ui.py` (o `venv/bin/python main_ui.py`)
5. En **⚙ Configuración** elige la carpeta de descargas y cuántas grabaciones bajar en paralelo (1 a 8), y pulsa **Iniciar**.

## Configuración
| Variable | Para qué | Ejemplo de formato |
|---|---|---|
| `UTP_USER` | Tu usuario del portal UTP | código de alumno |
| `UTP_PASS` | Tu contraseña del portal UTP | texto |

Son opcionales: puedes copiar `.env.example` a `.env`, o escribirlas en **⚙ Configuración** (ahí solo quedan en memoria). `config.json` guarda la carpeta y el paralelismo, nunca la contraseña. La sesión del navegador queda en `sesion/` (fuera de git): bórrala si cambias de cuenta. La app solo se conecta al portal de la UTP y a Zoom.

## Releases
Descarga `utp-class-downloader.exe` desde [Releases](https://github.com/pipodev06/utp-class-downloader/releases) y ábrelo. La primera vez instala Chromium sola (~190 MB, necesita internet). Las versiones siguen `vMAYOR.MENOR.PARCHE`.

## Licencia
[MIT](LICENSE).
