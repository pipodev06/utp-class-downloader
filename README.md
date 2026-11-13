# UTP Class Downloader

**UTP Class Downloader** es una aplicación de escritorio para estudiantes de la UTP: descarga en lote los materiales y las grabaciones Zoom de tus cursos en [class.utp.edu.pe](https://class.utp.edu.pe), sin entrar curso por curso. Software libre bajo [MIT](LICENSE).

> 🚀 **Sin instalar nada:** descarga `utp-class-downloader.exe` desde [Releases](https://github.com/pipodev06/utp-class-downloader/releases), ábrelo y pulsa **Iniciar** (desde el código: [Cómo levantarlo](#-cómo-levantarlo)).

```
Inicias sesión en el portal ─▶ lista de cursos con lo que falta bajar
                            ─▶ materiales y grabaciones Zoom ─▶ una carpeta por semana
```

## ✨ Qué hace

- 📚 **Todos tus cursos:** activos y de ciclos pasados, con cuánto te falta bajar de cada uno.
- ⬇️ **Descarga en lote:** materiales (PDF, Office, videos de la UTP enlazados en las lecturas) y grabaciones Zoom, por curso, todo junto o por selección.
- 🗂️ **Ordenado por semana:** una carpeta por semana; los videos de YouTube quedan listados en `youtube.html`.
- 🔁 **Reanudable:** nunca vuelve a bajar un archivo que ya tienes.

<details>
<summary>➕ <b>Todas las funciones</b></summary>

- 📝 **Pestaña Tareas:** estado y fecha límite de tus tareas y evaluaciones, con un botón para abrirlas en el portal.
- ⚡ **Grabaciones en paralelo:** de 1 a 8 a la vez, según elijas en **⚙ Configuración**.

</details>

## 🧱 Tecnologías

| Pieza | Tecnología |
|---|---|
| 🐍 Lenguaje | Python |
| 🖥️ Interfaz | PySide6 |
| 🌐 Navegador automatizado | Playwright (Chromium) |

## 📋 Requisitos

| Necesitas | Detalle |
|---|---|
| 🪟 Para el `.exe` | Windows 10/11, sin nada más que instalar |
| 🐍 Desde el código | Python 3.10+ (probado solo en Windows; en macOS y Linux debería funcionar, pero no se ha probado) |

## 🚀 Cómo levantarlo

```bash
git clone https://github.com/pipodev06/utp-class-downloader.git && cd utp-class-downloader
python -m venv venv
venv\Scripts\pip install -r requirements.txt       # Linux/macOS: venv/bin/pip
venv\Scripts\playwright install chromium            # Linux/macOS: venv/bin/playwright
venv\Scripts\python main_ui.py                      # Linux/macOS: venv/bin/python
```

1. En **⚙ Configuración**, elige la carpeta de descargas y cuántas grabaciones bajar en paralelo (1 a 8).
2. Pulsa **Iniciar**. ✅

## ⚙️ Configuración

| Variable | Para qué | Ejemplo de formato |
|---|---|---|
| `UTP_USER` | Tu usuario del portal UTP | código de alumno |
| `UTP_PASS` | Tu contraseña del portal UTP | texto |

Son opcionales: puedes copiar `.env.example` a `.env`, o escribirlas en **⚙ Configuración** (ahí solo quedan en memoria). `config.json` guarda la carpeta y el paralelismo, nunca la contraseña. La app solo se conecta al portal de la UTP y a Zoom.

**⚠️ Ojo con esto:**

| Si haces esto | Qué pasa |
|---|---|
| Esperar al final del ciclo | Zoom borra las grabaciones a los pocos meses: descarga las del ciclo en curso antes de que termine |
| Cambiar de cuenta | La sesión anterior sigue en `sesion/`: bórrala antes de entrar con otra cuenta |

## 📦 Releases

Descarga `utp-class-downloader.exe` desde [Releases](https://github.com/pipodev06/utp-class-downloader/releases) y ábrelo. La primera vez instala Chromium sola (~190 MB, necesita internet). Las versiones siguen `vMAYOR.MENOR.PARCHE`.

## 📜 Licencia

[MIT](LICENSE).
