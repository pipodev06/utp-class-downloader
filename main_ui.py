import sys
import json
import logging
import re
import subprocess
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QDialog, QFormLayout, QSpinBox,
    QFileDialog, QTextEdit, QFrame, QMessageBox, QSpacerItem, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QComboBox, QCheckBox, QProgressBar, QTabWidget,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl
from PySide6.QtGui import QFont, QColor, QDesktopServices
import qtawesome as qta

import auth
import scrape
import descargar_materiales
import descargar_zoom

SESION_DIR = str(Path(__file__).parent / "sesion")

# log persistente en logs/app.log (rota a 1 MB, guarda 3 copias)
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
_handler = RotatingFileHandler(LOGS_DIR / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger = logging.getLogger("utp")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
sys.excepthook = lambda tipo, valor, tb: logger.critical("Excepción no capturada", exc_info=(tipo, valor, tb))

# paleta (congelada en AGENTS.md)
DARK_BG = "#0e1013"
PANEL_BG = "#15181d"
BORDER = "#262a31"
BLUE = "#3b82f6"
GREEN = "#22c55e"
ORANGE = "#f59e0b"
RED = "#ef4444"
TEXT_MUTED = "#9aa1ac"
TEXT_MAIN = "#e5e7eb"

# config local (carpeta y nº de descargas en paralelo). La contraseña NUNCA se guarda aquí:
# usuario/clave vienen del .env (UTP_USER/UTP_PASS, que carga auth.py) o se escriben en ⚙.
CONFIG_PATH = Path(__file__).parent / "config.json"
CACHE_PATH = Path(__file__).parent / "cache" / "listado.json"   # último listado (se muestra al abrir)
CONFIG_GUARDABLE = ("base_dir", "zoom_workers")


def cargar_config() -> dict:
    config = {
        "utp_user": auth.UTP_USER or "",
        "utp_pass": auth.UTP_PASS or "",
        "base_dir": str(Path.home() / "Documents" / "utp-class-downloader"),
        "zoom_workers": 4,
    }
    try:
        guardado = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        config.update({k: guardado[k] for k in CONFIG_GUARDABLE if k in guardado})
    except (OSError, ValueError):
        pass
    return config


def guardar_config(config: dict):
    datos = {k: config[k] for k in CONFIG_GUARDABLE}
    CONFIG_PATH.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def resumir_carpeta(ruta: str) -> dict | None:
    """Conteo rápido de una carpeta de descargas. None si no existe."""
    base = Path(ruta).expanduser()
    if not base.is_dir():
        return None
    periodos = sorted((p.name for p in base.iterdir() if p.is_dir() and re.match(r"^\d{4}-I{1,2}$", p.name)),
                      reverse=True)
    archivos = videos = 0
    for p in periodos:
        for f in (base / p).rglob("*"):
            if f.is_file() and f.suffix not in (".skip", ".fail", ".part"):
                archivos += 1
                videos += f.suffix == ".mp4"
    return {"periodos": periodos, "archivos": archivos, "videos": videos}


def ordenar_periodos(combo: QComboBox):
    """Deja 'Todos' primero y los periodos del más reciente al más antiguo ('Otros' al final)."""
    actual = combo.currentText()
    periodos = sorted(
        (combo.itemText(i) for i in range(1, combo.count())),
        key=lambda p: (p[:1].isdigit(), p), reverse=True,
    )
    combo.blockSignals(True)
    combo.clear()
    combo.addItems(["Todos", *periodos])
    combo.setCurrentText(actual)
    combo.blockSignals(False)


# ── tareas ──
ESTADOS_TAREA = {   # metadata.status del portal → (etiqueta, color)
    "NOT_DELIVERED": ("Pendiente", ORANGE),
    "DELIVERED": ("Entregada", GREEN),
    "OUT_OF_DATE": ("Vencida", RED),
    "SCHEDULED": ("Programada", TEXT_MUTED),
}
ORDEN_ESTADO = {"NOT_DELIVERED": 0, "SCHEDULED": 1, "OUT_OF_DATE": 2, "DELIVERED": 3}
FILTROS_TAREA = {   # texto del combo → estados que muestra (None = todos)
    "Pendientes": {"NOT_DELIVERED"},
    "Nuevas": "NUEVAS",   # aparecidas en los últimos días (scrape.es_nueva)
    "Próximas": {"NOT_DELIVERED", "SCHEDULED"},
    "Vencidas sin entregar": {"OUT_OF_DATE"},
    "Entregadas": {"DELIVERED"},
    "Todas": None,
}


def estilo_flecha_combo() -> str:
    """QSS solo acepta imágenes de archivo: se guarda el ícono caret una vez en logs/.
    Requiere QApplication creada (por eso no va dentro de STYLE)."""
    ruta = LOGS_DIR / "caret-down.png"
    if not ruta.exists():
        qta.icon("ph.caret-down", color=TEXT_MUTED).pixmap(12, 12).save(str(ruta))
    return f"QComboBox::down-arrow {{ image: url({ruta.as_posix()}); width: 12px; height: 12px; margin-right: 8px; }}"


def _fecha(texto: str) -> datetime:
    try:
        return datetime.strptime(texto[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.max


def _fecha_corta(iso: str) -> str:
    """'2026-11-09T17:24' → '09/11 17:24'."""
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m %H:%M")
    except ValueError:
        return iso


def _tiempo_restante(vence: datetime, ahora: datetime) -> str:
    if vence == datetime.max:
        return "sin fecha"
    dias = (vence.date() - ahora.date()).days
    if vence < ahora:
        return "vencida"
    if dias == 0:
        return "hoy"
    if dias == 1:
        return "mañana"
    return f"en {dias} días"


STYLE = f"""
QMainWindow, QDialog {{
    background-color: {DARK_BG};
}}
QLabel {{
    color: {TEXT_MAIN};
}}
QLabel[muted="true"] {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}
QLineEdit {{
    background-color: #1c2027;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT_MAIN};
}}
QSpinBox {{
    background-color: #1c2027;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT_MAIN};
}}
QComboBox {{
    background-color: #1c2027;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT_MAIN};
    min-width: 120px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: #1c2027;
    border: 1px solid {BORDER};
    color: {TEXT_MAIN};
    selection-background-color: {BLUE};
}}
QPushButton#spinBtn {{
    background-color: #1c2027;
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_MAIN};
    padding: 4px;
}}
QPushButton#spinBtn:hover {{
    background-color: #232730;
}}
QPushButton#spinBtn:pressed {{
    background-color: {BLUE};
    color: white;
}}
QPushButton#accionFila {{
    background-color: #1c2027;
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_MAIN};
    padding: 6px 12px;
}}
QPushButton#accionFila:hover {{
    background-color: #232730;
    border: 1px solid {BLUE};
}}
QPushButton#accionFila:disabled {{
    color: {TEXT_MUTED};
}}
QPushButton#accionFila:focus {{
    outline: none;
    border: 1px solid {BLUE};
}}
QPushButton#iniciar {{
    background-color: {BLUE};
    color: white;
    font-weight: bold;
    font-size: 14px;
    border-radius: 8px;
    padding: 6px 40px;
}}
QPushButton#iniciar:disabled {{
    background-color: #274268;
    color: #8ea3c2;
}}
QPushButton#guardar {{
    background-color: {BLUE};
    color: white;
    font-weight: bold;
    border-radius: 6px;
    padding: 10px;
}}
QPushButton#cambiarRuta {{
    background-color: transparent;
    color: {BLUE};
    border: 1px solid {BLUE};
    border-radius: 6px;
    padding: 6px 10px;
}}
QPushButton#gear {{
    background-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_MAIN};
    font-size: 16px;
}}
QFrame#logsPanel {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QTextEdit#logs {{
    background-color: transparent;
    border: none;
    color: {TEXT_MAIN};
    font-family: Consolas, monospace;
    font-size: 12px;
}}
QFrame#resultadosPanel {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QTreeWidget {{
    background-color: transparent;
    border: none;
    color: {TEXT_MAIN};
}}
QTreeWidget::item {{
    padding: 4px;
    height: 36px;
}}
QHeaderView::section {{
    background-color: {PANEL_BG};
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 4px;
    font-size: 13px;
}}
QPushButton#terminal {{
    background-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_MAIN};
    font-size: 16px;
}}
QPushButton#terminal:hover {{
    background-color: #1c2027;
}}
QPushButton#accion {{
    background-color: #1c2027;
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_MAIN};
    padding: 8px 12px;
    text-align: center;
}}
QPushButton#accion:hover {{
    background-color: #232730;
    border-color: {BLUE};
}}
QPushButton#accion:disabled {{
    color: {TEXT_MUTED};
}}
QPushButton#seleccionados {{
    background-color: {GREEN};
    color: white;
    font-weight: bold;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: center;
}}
QPushButton#seleccionados:hover {{
    background-color: #1ea854;
}}
QPushButton#seleccionados:disabled {{
    background-color: #1c3f2b;
    color: #7fa892;
}}
QCheckBox {{
    color: {TEXT_MAIN};
    spacing: 6px;
}}
QPushButton#seleccionar {{
    background-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_MAIN};
    padding: 6px 12px;
}}
QPushButton#seleccionar:hover {{
    border-color: {BLUE};
}}
QPushButton#seleccionar:checked {{
    background-color: {BLUE};
    color: white;
    border-color: {BLUE};
}}
QProgressBar {{
    background-color: #1c2027;
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_MAIN};
    text-align: center;
    font-size: 11px;
}}
QProgressBar::chunk {{
    background-color: {BLUE};
    border-radius: 5px;
}}
QTabWidget::pane {{
    border: none;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 18px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {TEXT_MAIN};
    border-bottom: 2px solid {BLUE};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT_MAIN};
}}
QToolTip {{
    background-color: #1c2027;
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    padding: 4px 6px;
}}
"""

class ChromiumWorker(QThread):
    """Verifica/instala el Chromium de Playwright al abrir la app.
    Funciona tanto corriendo como script como empaquetado en .exe (PyInstaller) —
    invoca el driver interno de Playwright directo, sin depender de 'python -m'."""
    log = Signal(str, str, str)
    terminado = Signal(bool)

    def run(self):
        try:
            from playwright._impl._driver import compute_driver_executable, get_driver_env
            driver_executable, driver_cli = compute_driver_executable()
            self.log.emit("INFO", "gray", "Verificando Chromium (primera vez puede tardar unos minutos)...")
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            resultado = subprocess.run(
                [str(driver_executable), str(driver_cli), "install", "chromium"],
                env=get_driver_env(), capture_output=True, text=True,
                creationflags=flags,
            )
            if resultado.returncode == 0:
                self.log.emit("SUCCESS", "#22c55e", "Chromium listo")
                self.terminado.emit(True)
            else:
                self.log.emit("WARN", ORANGE, f"No se pudo preparar Chromium: {resultado.stderr[:300]}")
                self.terminado.emit(False)
        except Exception as e:
            self.log.emit("WARN", ORANGE, f"Error verificando Chromium: {e}")
            self.terminado.emit(False)


class Trabajo(QThread):
    """Corre en segundo plano cualquier flujo (listar, materiales, Zoom) sin congelar la UI.
    fn(log, progreso, curso_listo) -> resultado. 'terminado' emite el resultado, o None si falló."""
    log = Signal(str, str, str)   # nivel, color, mensaje
    progreso = Signal(int, int)   # actual, total
    curso = Signal(dict)          # una entrada de curso apenas está lista (solo el listado)
    terminado = Signal(object)

    def __init__(self, fn, utp_user: str = "", utp_pass: str = ""):
        super().__init__()
        self.fn = fn
        self.utp_user = utp_user
        self.utp_pass = utp_pass

    def run(self):
        # auth.py lee credenciales de módulo; solo hacen falta si el token guardado venció
        if self.utp_user and self.utp_pass:
            auth.UTP_USER = self.utp_user
            auth.UTP_PASS = self.utp_pass
        try:
            resultado = self.fn(
                lambda n, c, m: self.log.emit(n, c, m),
                lambda a, t: self.progreso.emit(a, t),
                lambda curso: self.curso.emit(curso),
            )
            self.terminado.emit(resultado)
        except Exception as e:
            logger.exception("Falló un trabajo en segundo plano")
            self.log.emit("WARN", ORANGE, f"Error: {e}")
            self.terminado.emit(None)


class LogsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logs")
        self.resize(832, 546)

        layout = QVBoxLayout(self)
        panel = QFrame()
        panel.setObjectName("logsPanel")
        panel_layout = QVBoxLayout(panel)
        label = QLabel("Logs")
        label.setProperty("muted", "true")
        self.texto = QTextEdit()
        self.texto.setObjectName("logs")
        self.texto.setReadOnly(True)
        panel_layout.addWidget(label)
        panel_layout.addWidget(self.texto)
        layout.addWidget(panel)

    def agregar(self, nivel: str, color: str, mensaje: str):
        self.texto.append(
            f'<span style="color:{TEXT_MUTED}">[{nivel}]</span> '
            f'<span style="color:{TEXT_MAIN}">{mensaje}</span>'
        )


class ConfiguracionDialog(QDialog):
    def __init__(self, parent=None, valores: dict | None = None):
        super().__init__(parent)
        valores = valores or {}
        self.setWindowTitle("Configuración")
        self.setFixedWidth(540)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        fila_titulo_dialogo = QHBoxLayout()
        icono_titulo = QLabel()
        icono_titulo.setPixmap(qta.icon("ph.gear", color=TEXT_MAIN).pixmap(20, 20))
        titulo = QLabel("Configuración")
        titulo.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        fila_titulo_dialogo.addWidget(icono_titulo)
        fila_titulo_dialogo.addWidget(titulo)
        fila_titulo_dialogo.addStretch()
        layout.addLayout(fila_titulo_dialogo)

        form = QFormLayout()
        form.setSpacing(10)

        ALTO_CAMPO = 34

        self.utp_user = QLineEdit(valores.get("utp_user", ""))
        self.utp_user.setPlaceholderText("tu_usuario_aqui")
        self.utp_user.setFixedHeight(ALTO_CAMPO)

        fila_pass = QHBoxLayout()
        fila_pass.setSpacing(6)
        self.utp_pass = QLineEdit(valores.get("utp_pass", ""))
        self.utp_pass.setPlaceholderText("tu_contraseña_aqui")
        self.utp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.utp_pass.setFixedHeight(ALTO_CAMPO)
        self.btn_ojo = QPushButton()
        self.btn_ojo.setObjectName("spinBtn")
        self.btn_ojo.setFixedSize(32, ALTO_CAMPO)
        self.btn_ojo.setIcon(qta.icon("ph.eye", color=TEXT_MAIN))
        self.btn_ojo.setIconSize(QSize(16, 16))
        self.btn_ojo.setCheckable(True)
        self.btn_ojo.toggled.connect(self._toggle_pass)
        fila_pass.addWidget(self.utp_pass, stretch=1)
        fila_pass.addWidget(self.btn_ojo)

        fila_ruta = QHBoxLayout()
        self.base_dir = QLineEdit(
            valores.get("base_dir", str(Path.home() / "Documents" / "utp-class-downloader"))
        )
        self.base_dir.setReadOnly(True)
        self.base_dir.setFixedHeight(ALTO_CAMPO)
        btn_ruta = QPushButton()
        btn_ruta.setObjectName("cambiarRuta")
        btn_ruta.setFixedSize(32, ALTO_CAMPO)
        btn_ruta.setIcon(qta.icon("ph.folder-open", color=BLUE))
        btn_ruta.setIconSize(QSize(16, 16))
        btn_ruta.clicked.connect(self.elegir_ruta)
        fila_ruta.addWidget(self.base_dir, stretch=1)
        fila_ruta.addWidget(btn_ruta)

        fila_zoom = QHBoxLayout()
        fila_zoom.setSpacing(6)
        self.zoom_workers = QSpinBox()
        self.zoom_workers.setRange(1, 8)
        self.zoom_workers.setValue(valores.get("zoom_workers", 4))
        self.zoom_workers.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.zoom_workers.setFixedHeight(ALTO_CAMPO)
        btn_zoom_arriba = QPushButton()
        btn_zoom_arriba.setObjectName("spinBtn")
        btn_zoom_arriba.setFixedSize(28, ALTO_CAMPO)
        btn_zoom_arriba.setIcon(qta.icon("ph.caret-up", color=TEXT_MAIN))
        btn_zoom_arriba.setIconSize(QSize(14, 14))
        btn_zoom_arriba.clicked.connect(self.zoom_workers.stepUp)
        btn_zoom_abajo = QPushButton()
        btn_zoom_abajo.setObjectName("spinBtn")
        btn_zoom_abajo.setFixedSize(28, ALTO_CAMPO)
        btn_zoom_abajo.setIcon(qta.icon("ph.caret-down", color=TEXT_MAIN))
        btn_zoom_abajo.setIconSize(QSize(14, 14))
        btn_zoom_abajo.clicked.connect(self.zoom_workers.stepDown)
        fila_zoom.addWidget(self.zoom_workers, stretch=1)
        fila_zoom.addWidget(btn_zoom_arriba)
        fila_zoom.addWidget(btn_zoom_abajo)

        form.addRow("UTP USER", self.utp_user)
        form.addRow("UTP PASS", fila_pass)
        form.addRow("BASE DIR", fila_ruta)
        self.resumen_carpeta = QLabel()
        self.resumen_carpeta.setProperty("muted", "true")
        form.addRow("", self.resumen_carpeta)
        self._actualizar_resumen_carpeta()
        hint = QLabel("1-8 a la vez, para materiales y clases (default 4)")
        hint.setProperty("muted", "true")
        form.addRow("EN PARALELO", fila_zoom)
        form.addRow("", hint)

        layout.addLayout(form)

        btn_guardar = QPushButton("Guardar Configuración")
        btn_guardar.setObjectName("guardar")
        btn_guardar.clicked.connect(self.guardar)
        layout.addWidget(btn_guardar)

    def _toggle_pass(self, visible: bool):
        self.utp_pass.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        icono = "ph.eye-slash" if visible else "ph.eye"
        self.btn_ojo.setIcon(qta.icon(icono, color=TEXT_MAIN))

    def elegir_ruta(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Elegir carpeta", self.base_dir.text())
        if carpeta:
            self.base_dir.setText(carpeta)
            self._actualizar_resumen_carpeta()

    def _actualizar_resumen_carpeta(self):
        """Muestra qué hay en la carpeta elegida, para notar al tiro si es la equivocada."""
        resumen = resumir_carpeta(self.base_dir.text())
        if resumen is None:
            texto, color = "La carpeta no existe", ORANGE
        elif not resumen["periodos"]:
            texto, color = "Sin descargas aquí (no hay carpetas de periodo como 2026-II)", ORANGE
        else:
            texto = (f"{resumen['archivos']} archivos · {resumen['videos']} videos · "
                     f"periodos {', '.join(resumen['periodos'])}")
            color = TEXT_MUTED
        self.resumen_carpeta.setText(texto)
        self.resumen_carpeta.setStyleSheet(f"color: {color};")

    def obtener_valores(self) -> dict:
        return {
            "utp_user": self.utp_user.text(),
            "utp_pass": self.utp_pass.text(),
            "base_dir": self.base_dir.text(),
            "zoom_workers": self.zoom_workers.value(),
        }

    def guardar(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Configuración")
        msg.setText("Guardado")
        espaciador = QSpacerItem(280, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        msg_layout = msg.layout()
        msg_layout.addItem(espaciador, msg_layout.rowCount(), 0, 1, msg_layout.columnCount())

        etiqueta = msg.findChild(QLabel, "qt_msgbox_label")
        if etiqueta:
            etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)

        msg.adjustSize()
        rect_msg = msg.frameGeometry()
        rect_msg.moveCenter(self.frameGeometry().center())
        msg.move(rect_msg.topLeft())

        msg.exec()
        self.accept()


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UTP Class Downloader")
        self.resize(1500, 750)

        self.config = cargar_config()

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(16)

        # ── header ──
        header = QHBoxLayout()
        titulo = QLabel("UTP CLASS DOWNLOADER")
        titulo.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.addWidget(titulo)
        header.addStretch()
        btn_gear = QPushButton()
        btn_gear.setObjectName("gear")
        btn_gear.setFixedSize(34, 34)
        btn_gear.setIcon(qta.icon("ph.gear", color=TEXT_MAIN))
        btn_gear.setIconSize(QSize(18, 18))
        btn_gear.setToolTip("Configuración")
        btn_gear.clicked.connect(self.abrir_configuracion)
        header.addWidget(btn_gear)
        root.addLayout(header)

        # ── barra de herramientas: Iniciar + Descargar + Logs ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.btn_iniciar = QPushButton("Iniciar")
        self.btn_iniciar.setObjectName("iniciar")
        self.btn_iniciar.clicked.connect(self.iniciar)
        toolbar.addWidget(self.btn_iniciar)

        toolbar.addStretch()

        self.btn_descargar_materiales = QPushButton("Todos los materiales")
        self.btn_descargar_materiales.setObjectName("accion")
        self.btn_descargar_materiales.setIcon(qta.icon("ph.download-simple", color=TEXT_MAIN))
        self.btn_descargar_materiales.setIconSize(QSize(16, 16))
        self.btn_descargar_materiales.clicked.connect(lambda: self.descargar_materiales())
        self.btn_descargar_materiales.setVisible(False)
        toolbar.addWidget(self.btn_descargar_materiales)

        self.btn_descargar_zoom = QPushButton("Todas las clases")
        self.btn_descargar_zoom.setObjectName("accion")
        self.btn_descargar_zoom.setIcon(qta.icon("ph.download-simple", color=TEXT_MAIN))
        self.btn_descargar_zoom.setIconSize(QSize(16, 16))
        self.btn_descargar_zoom.clicked.connect(lambda: self.descargar_zoom_clases())
        self.btn_descargar_zoom.setVisible(False)
        toolbar.addWidget(self.btn_descargar_zoom)

        self.btn_descargar_seleccionados = QPushButton("Descargar Seleccionados")
        self.btn_descargar_seleccionados.setObjectName("seleccionados")
        self.btn_descargar_seleccionados.setIcon(qta.icon("ph.download-simple", color="white"))
        self.btn_descargar_seleccionados.setIconSize(QSize(16, 16))
        self.btn_descargar_seleccionados.clicked.connect(self.descargar_seleccionados)
        self.btn_descargar_seleccionados.setVisible(False)
        toolbar.addWidget(self.btn_descargar_seleccionados)

        self.logs_window = LogsWindow(self)
        btn_terminal = QPushButton()
        btn_terminal.setObjectName("terminal")
        btn_terminal.setFixedSize(34, 34)
        btn_terminal.setIcon(qta.icon("ph.terminal", color=TEXT_MAIN))
        btn_terminal.setIconSize(QSize(18, 18))
        btn_terminal.setToolTip("Ver logs")
        btn_terminal.clicked.connect(self._abrir_logs)
        toolbar.addWidget(btn_terminal)

        root.addLayout(toolbar)

        # ── pestañas: Cursos / Tareas ──
        self.tabs = QTabWidget()
        self.tabs.addTab(self._crear_panel_cursos(), "Cursos")
        self.tabs.addTab(self._crear_panel_tareas(), "Tareas")
        root.addWidget(self.tabs, stretch=1)

        self.setCentralWidget(central)
        self.setStyleSheet(STYLE + estilo_flecha_combo())

        self.worker = None
        self._todos_cursos = []
        self._widgets_fila = []
        self._sel_materiales = set()
        self._sel_videos = set()
        self._modo_seleccion = False
        self._cola_seleccionados = []
        self._fecha_listado = ""      # ISO del último listado mostrado (caché o recién hecho)
        self._unidad_progreso = "cursos"

        # lo último que se listó aparece al instante; el refresco llega en segundo plano
        cache = scrape.cargar_cache(CACHE_PATH)
        if cache:
            self._fecha_listado, cursos = cache
            self._mostrar_cursos(cursos)
        self._preparar_chromium()

    # ───────────────────────── construcción de paneles ─────────────────────────

    def _crear_panel_cursos(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("resultadosPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 12, 14, 8)
        panel_layout.setSpacing(10)

        fila = QHBoxLayout()
        label_periodo = QLabel("Periodo")
        label_periodo.setProperty("muted", "true")
        self.filtro_periodo = QComboBox()
        self.filtro_periodo.addItem("Todos")
        self.filtro_periodo.currentTextChanged.connect(self._filtrar)
        fila.addWidget(label_periodo)
        fila.addWidget(self.filtro_periodo)
        fila.addSpacing(12)
        self.label_estado = QLabel("")
        self.label_estado.setProperty("muted", "true")
        fila.addWidget(self.label_estado)
        fila.addStretch()
        self.progreso_bar = QProgressBar()
        self.progreso_bar.setFixedWidth(160)
        self.progreso_bar.setFixedHeight(18)
        self.progreso_bar.setVisible(False)
        fila.addWidget(self.progreso_bar)
        self.btn_seleccionar = QPushButton("Seleccionar")
        self.btn_seleccionar.setObjectName("seleccionar")
        self.btn_seleccionar.setCheckable(True)
        self.btn_seleccionar.setToolTip("Marcar materiales/clases de varios cursos y bajarlos juntos")
        self.btn_seleccionar.toggled.connect(self._toggle_modo_seleccion)
        fila.addWidget(self.btn_seleccionar)

        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabels(["Curso", "Periodo", "Materiales", "Clases", "Descargar"])
        self.arbol.setRootIsDecorated(False)
        self.arbol.setColumnWidth(0, 420)
        self.arbol.setColumnWidth(1, 110)
        self.arbol.setColumnWidth(2, 130)
        self.arbol.setColumnWidth(3, 130)
        for col in (1, 2, 3, 4):
            self.arbol.headerItem().setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

        panel_layout.addLayout(fila)
        panel_layout.addWidget(self.arbol)
        return panel

    def _crear_panel_tareas(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("resultadosPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 12, 14, 8)
        panel_layout.setSpacing(10)

        fila = QHBoxLayout()
        label_mostrar = QLabel("Mostrar")
        label_mostrar.setProperty("muted", "true")
        self.filtro_estado_tarea = QComboBox()
        self.filtro_estado_tarea.addItems(FILTROS_TAREA)
        self.filtro_estado_tarea.currentTextChanged.connect(lambda _: self._pintar_tareas())
        label_periodo = QLabel("Periodo")
        label_periodo.setProperty("muted", "true")
        self.filtro_periodo_tarea = QComboBox()
        self.filtro_periodo_tarea.addItem("Todos")
        self.filtro_periodo_tarea.currentTextChanged.connect(lambda _: self._pintar_tareas())
        fila.addWidget(label_mostrar)
        fila.addWidget(self.filtro_estado_tarea)
        fila.addSpacing(12)
        fila.addWidget(label_periodo)
        fila.addWidget(self.filtro_periodo_tarea)
        fila.addSpacing(12)
        self.label_resumen_tareas = QLabel("Corre Iniciar para ver tus tareas")
        self.label_resumen_tareas.setProperty("muted", "true")
        fila.addWidget(self.label_resumen_tareas)
        fila.addStretch()

        self.arbol_tareas = QTreeWidget()
        self.arbol_tareas.setHeaderLabels(["Estado", "Vence", "Curso", "Actividad", "Tipo", ""])
        self.arbol_tareas.setRootIsDecorated(False)
        self.arbol_tareas.setColumnWidth(0, 170)
        self.arbol_tareas.setColumnWidth(1, 170)
        self.arbol_tareas.setColumnWidth(2, 260)
        self.arbol_tareas.setColumnWidth(3, 520)
        self.arbol_tareas.setColumnWidth(4, 110)
        self.arbol_tareas.itemDoubleClicked.connect(self._abrir_tarea_item)

        panel_layout.addLayout(fila)
        panel_layout.addWidget(self.arbol_tareas)
        return panel

    # ───────────────────────── flujo general ─────────────────────────

    def _preparar_chromium(self):
        self.btn_iniciar.setEnabled(False)
        if not self._todos_cursos:
            self.label_estado.setText("Preparando Chromium...")
        self.chromium_worker = ChromiumWorker()
        self.chromium_worker.log.connect(self._log)
        self.chromium_worker.terminado.connect(self._chromium_listo)
        self.chromium_worker.start()

    def _chromium_listo(self, exito: bool):
        self.btn_iniciar.setEnabled(True)
        if not exito:
            self.label_estado.setText("Chromium no disponible — revisa los logs")
        elif self._todos_cursos and scrape.token_vigente(SESION_DIR):
            self.iniciar()   # refresco automático: con token vigente no abre ninguna ventana
        elif not self._todos_cursos:
            self.label_estado.setText("")

    def _abrir_logs(self):
        self.logs_window.show()
        self.logs_window.raise_()
        self.logs_window.activateWindow()

    def abrir_configuracion(self):
        dialogo = ConfiguracionDialog(self, valores=self.config)
        if dialogo.exec():
            self.config = dialogo.obtener_valores()
            guardar_config(self.config)
            self._log("OK", BLUE, "Configuración guardada")
            if self._todos_cursos:
                self.detectar_descargas()

    def _set_ocupado(self, ocupado: bool):
        # los 3 flujos abren Playwright sobre el mismo sesion/ — no pueden correr a la vez
        self.btn_iniciar.setEnabled(not ocupado)
        self.btn_descargar_materiales.setEnabled(not ocupado)
        self.btn_descargar_zoom.setEnabled(not ocupado)
        self.btn_descargar_seleccionados.setEnabled(not ocupado)
        for widget in self._widgets_fila:
            widget.setEnabled(not ocupado)

    def _reiniciar_vista(self):
        """Deja tablas, filtros y selección vacíos (antes de pintar un listado)."""
        self.arbol.clear()
        self.arbol_tareas.clear()
        self._todos_cursos = []
        self._widgets_fila = []
        self._sel_materiales = set()
        self._sel_videos = set()
        self.btn_seleccionar.blockSignals(True)
        self.btn_seleccionar.setChecked(False)
        self.btn_seleccionar.blockSignals(False)
        self._modo_seleccion = False
        self.btn_descargar_seleccionados.setVisible(False)
        for combo in (self.filtro_periodo, self.filtro_periodo_tarea):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Todos")
            combo.blockSignals(False)

    def _mostrar_cursos(self, cursos: list[dict]):
        """Pinta un listado completo (de la caché o recién traído) y recalcula disco y tareas."""
        periodo_tareas = self.filtro_periodo_tarea.currentText()
        self._reiniciar_vista()
        for c in cursos:
            self._agregar_curso(c)
        for combo in (self.filtro_periodo, self.filtro_periodo_tarea):
            ordenar_periodos(combo)
        # en Tareas lo útil es el ciclo en curso: el periodo más reciente (o el que ya estaba)
        if self.filtro_periodo_tarea.findText(periodo_tareas) > 0:
            self.filtro_periodo_tarea.setCurrentText(periodo_tareas)
        elif self.filtro_periodo_tarea.count() > 1:
            self.filtro_periodo_tarea.setCurrentIndex(1)
        self.btn_descargar_materiales.setVisible(bool(self._todos_cursos))
        self.btn_descargar_zoom.setVisible(bool(self._todos_cursos))
        self._pintar_tareas()
        self.detectar_descargas()

    def _lanzar(self, fn, al_terminar, unidad: str, con_credenciales: bool = False, en_vivo=None):
        """Arranca un Trabajo en segundo plano con log y progreso conectados."""
        self._unidad_progreso = unidad
        self._set_ocupado(True)
        cred = (self.config["utp_user"], self.config["utp_pass"]) if con_credenciales else ()
        self.worker = Trabajo(fn, *cred)
        self.worker.log.connect(self._log)
        self.worker.progreso.connect(self._actualizar_progreso)
        if en_vivo:
            self.worker.curso.connect(en_vivo)
        self.worker.terminado.connect(al_terminar)
        self.worker.start()

    def iniciar(self):
        self.logs_window.texto.clear()
        previos = list(self._todos_cursos)   # para detectar tareas nuevas y cubrir fallos de la API
        self._previos = previos              # se restauran si el refresco falla
        self._reiniciar_vista()
        self.label_resumen_tareas.setText("Actualizando...")
        self.label_estado.setText("Actualizando...")
        self._lanzar(
            lambda log, prog, curso: scrape.listar_todo(SESION_DIR, log, prog, curso, previos=previos),
            self._login_terminado, "cursos", con_credenciales=True, en_vivo=self._agregar_curso,
        )

    def _cursos_para(self, nombres: list[str] | None) -> list[dict]:
        return [c for c in self._todos_cursos if not nombres or c["nombre"] in nombres]

    def descargar_materiales(self, nombres: list[str] | None = None):
        self.logs_window.texto.clear()
        self.label_estado.setText(
            f"Descargando materiales de {len(nombres)} curso(s)..." if nombres
            else "Descargando materiales de todos los cursos..."
        )
        cursos, base_dir, paralelo = self._cursos_para(nombres), self.config["base_dir"], self.config["zoom_workers"]
        self._lanzar(
            lambda log, prog, _: descargar_materiales.descargar_materiales(base_dir, cursos, paralelo, log, prog),
            self._descarga_terminada, "archivos",
        )

    def descargar_zoom_clases(self, nombres: list[str] | None = None):
        self.logs_window.texto.clear()
        self.label_estado.setText(
            f"Descargando grabaciones de {len(nombres)} curso(s)..." if nombres
            else "Descargando grabaciones de todos los cursos..."
        )
        cursos, base_dir, paralelo = self._cursos_para(nombres), self.config["base_dir"], self.config["zoom_workers"]
        self._lanzar(
            lambda log, prog, _: descargar_zoom.descargar_zoom(SESION_DIR, base_dir, cursos, paralelo, log, prog),
            self._descarga_terminada, "clases", con_credenciales=True,
        )

    def _toggle_modo_seleccion(self, activo: bool):
        self._modo_seleccion = activo
        self._filtrar(self.filtro_periodo.currentText())

    # ───────────────────────── disco ─────────────────────────

    def detectar_descargas(self):
        base_dir = self.config["base_dir"]
        if not Path(base_dir).expanduser().is_dir():
            self.label_estado.setText("No encuentro la carpeta de descargas — elígela en ⚙")
            self._log("WARN", ORANGE, f"Carpeta de descargas no existe: {base_dir}")
            return

        for c in self._todos_cursos:
            c["disco"] = scrape.estado_en_disco(base_dir, c)
        self._filtrar(self.filtro_periodo.currentText())
        self._actualizar_resumen_cursos()
        self._log("OK", BLUE, "Detección de archivos en disco completa")

    def _actualizar_resumen_cursos(self):
        visibles = self._cursos_visibles()
        faltan_mat = sum(len(c["materiales"]) - c["disco"]["materiales_ok"] for c in visibles if "disco" in c)
        faltan_vid = sum(
            len(c["videos"]) - c["disco"]["videos_ok"] - c["disco"]["videos_no_disp"]
            for c in visibles if "disco" in c
        )
        partes = [f"{len(visibles)} cursos"]
        if faltan_mat or faltan_vid:
            partes.append(f"faltan {faltan_mat} materiales y {faltan_vid} clases")
        elif any("disco" in c for c in visibles):
            partes.append("todo descargado")
        if self._fecha_listado:
            partes.append(f"actualizado {_fecha_corta(self._fecha_listado)}")
        self.label_estado.setText(" · ".join(partes))

    # ───────────────────────── selección y descargas ─────────────────────────

    def descargar_seleccionados(self):
        materiales_sel = list(self._sel_materiales)
        videos_sel = list(self._sel_videos)
        if not materiales_sel and not videos_sel:
            return

        self._cola_seleccionados = []
        if materiales_sel:
            self._cola_seleccionados.append(("materiales", materiales_sel))
        if videos_sel:
            self._cola_seleccionados.append(("videos", videos_sel))
        self._procesar_siguiente_seleccionado()

    def _procesar_siguiente_seleccionado(self):
        if not self._cola_seleccionados:
            return
        tipo, nombres = self._cola_seleccionados.pop(0)
        if tipo == "materiales":
            self.descargar_materiales(nombres=nombres)
        else:
            self.descargar_zoom_clases(nombres=nombres)

    def _descarga_terminada(self, resumen: dict | None):
        if self._cola_seleccionados:
            self._procesar_siguiente_seleccionado()
            return
        resumen = resumen or {}
        self._set_ocupado(False)
        self.progreso_bar.setVisible(False)
        self._log("SUCCESS", GREEN, f"Descarga terminada — {resumen.get('ok', 0)} ok, {resumen.get('fail', 0)} fallidos")
        self.detectar_descargas()
        if resumen.get("zoom_login"):
            self.label_estado.setText("Zoom pide iniciar sesión — las clases no se pudieron bajar (revisa los logs)")

    def _actualizar_progreso(self, actual: int, total: int):
        self.progreso_bar.setVisible(True)
        self.progreso_bar.setMaximum(total)
        self.progreso_bar.setValue(actual)
        self.label_estado.setText(f"Procesando {actual}/{total} {self._unidad_progreso}...")

    # ───────────────────────── tabla de cursos ─────────────────────────

    def _agregar_curso(self, c: dict):
        if not (c["materiales"] or c["videos"] or c["tareas"]):
            return   # cursos vacíos (ej. "Inducción", periodo 9999) solo meten ruido
        self._todos_cursos.append(c)
        for combo in (self.filtro_periodo, self.filtro_periodo_tarea):
            if combo.findText(c["periodo"]) == -1:
                combo.addItem(c["periodo"])

        if self.filtro_periodo.currentText() in ("Todos", c["periodo"]):
            self._agregar_fila(c)

    def _cursos_visibles(self) -> list[dict]:
        periodo = self.filtro_periodo.currentText()
        return [c for c in self._todos_cursos if periodo in ("Todos", c["periodo"])]

    def _agregar_fila(self, c: dict):
        nombre_curso = c["nombre"]
        item = QTreeWidgetItem([nombre_curso, c["periodo"], "", "", ""])
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
        item.setForeground(1, QColor(TEXT_MUTED))
        self.arbol.addTopLevelItem(item)

        disco = c.get("disco")
        mat_total, vid_total = len(c["materiales"]), len(c["videos"])
        if disco:
            mat = (disco["materiales_ok"], mat_total, 0)
            vid = (disco["videos_ok"], vid_total, disco["videos_no_disp"])
        else:
            mat, vid = (None, mat_total, 0), (None, vid_total, 0)

        self.arbol.setItemWidget(item, 2, self._crear_celda_conteo(
            nombre_curso, *mat, self._sel_materiales, self._toggle_sel_materiales, "materiales"))
        self.arbol.setItemWidget(item, 3, self._crear_celda_conteo(
            nombre_curso, *vid, self._sel_videos, self._toggle_sel_videos, "clases"))
        self.arbol.setItemWidget(item, 4, self._crear_widget_acciones(nombre_curso, mat_total, vid_total))

    def _crear_celda_conteo(self, nombre_curso: str, ok: int | None, total: int, no_disp: int,
                            conjunto: set, on_toggle, que: str) -> QWidget:
        """Celda 'descargados / total'. Verde = nada más por bajar; ámbar = faltan; gris = sin datos."""
        if total == 0:
            texto, color, tip = "—", TEXT_MUTED, f"Sin {que}"
        elif ok is None:
            texto, color, tip = str(total), TEXT_MAIN, f"{total} {que} en el portal"
        else:
            faltan = total - ok - no_disp
            texto = f"{ok} / {total}"
            color = GREEN if faltan == 0 else ORANGE
            tip = f"{ok} descargados" + (f", faltan {faltan}" if faltan else "")
            if no_disp:
                tip += f"\n{no_disp} ya no están disponibles en Zoom"

        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self._modo_seleccion and total:
            widget = QCheckBox(texto)
            widget.setChecked(nombre_curso in conjunto)
            widget.toggled.connect(lambda marcado, n=nombre_curso: on_toggle(n, marcado))
            self._widgets_fila.append(widget)
        else:
            widget = QLabel(texto)
        widget.setStyleSheet(f"color: {color};")
        widget.setToolTip(tip)
        fila.addWidget(widget)
        return contenedor

    def _toggle_sel_materiales(self, nombre_curso: str, marcado: bool):
        if marcado:
            self._sel_materiales.add(nombre_curso)
        else:
            self._sel_materiales.discard(nombre_curso)
        self._actualizar_boton_seleccionados()

    def _toggle_sel_videos(self, nombre_curso: str, marcado: bool):
        if marcado:
            self._sel_videos.add(nombre_curso)
        else:
            self._sel_videos.discard(nombre_curso)
        self._actualizar_boton_seleccionados()

    def _crear_widget_acciones(self, nombre_curso: str, mat_total: int, vid_total: int) -> QWidget:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(6)
        fila.setAlignment(Qt.AlignmentFlag.AlignCenter)

        botones = [
            ("Materiales", "ph.file-text", mat_total, lambda: self.descargar_materiales(nombres=[nombre_curso])),
            ("Clases", "ph.video-camera", vid_total, lambda: self.descargar_zoom_clases(nombres=[nombre_curso])),
        ]
        for texto, icono, total, accion in botones:
            btn = QPushButton(texto)
            btn.setObjectName("accionFila")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setIcon(qta.icon(icono, color=TEXT_MAIN))
            btn.setIconSize(QSize(14, 14))
            btn.setFixedWidth(120)
            btn.setToolTip(f"Descargar {texto.lower()} de {nombre_curso}")
            btn.clicked.connect(accion)
            if total:
                self._widgets_fila.append(btn)
            else:
                btn.setEnabled(False)
            fila.addWidget(btn)
        return contenedor

    def _actualizar_boton_seleccionados(self):
        hay_alguno = bool(self._sel_materiales) or bool(self._sel_videos)
        self.btn_descargar_seleccionados.setVisible(hay_alguno)

    def _filtrar(self, periodo: str):
        self.arbol.clear()
        self._widgets_fila = []
        self._actualizar_boton_seleccionados()
        for c in self._todos_cursos:
            if periodo == "Todos" or c["periodo"] == periodo:
                self._agregar_fila(c)
        listando = self.worker is not None and self.worker.isRunning()
        if self._todos_cursos and not listando:
            self._actualizar_resumen_cursos()

    def _login_terminado(self, cursos: list[dict] | None):
        self._set_ocupado(False)
        self.progreso_bar.setVisible(False)
        if cursos is None:
            if self._previos:   # no perder lo que se veía: vuelve el último listado
                self._mostrar_cursos(self._previos)
                self.label_estado.setText(f"No se pudo actualizar — se muestra el listado de "
                                          f"{_fecha_corta(self._fecha_listado)} · revisa los logs")
            else:
                self.label_estado.setText("Falló — revisa los logs")
                self.label_resumen_tareas.setText("Sin datos")
            return
        scrape.guardar_cache(CACHE_PATH, cursos)
        self._fecha_listado = datetime.now().isoformat(timespec="minutes")
        # se repinta desde el resultado final: trae 'visto' (tareas nuevas) que se calcula al terminar
        self._mostrar_cursos(cursos)
        nuevas = sum(scrape.es_nueva(t) for c in cursos for t in c["tareas"])
        if nuevas:
            self._log("SUCCESS", GREEN, f"{nuevas} tarea(s) nueva(s) desde el último listado")

    # ───────────────────────── tareas ─────────────────────────

    def _pintar_tareas(self):
        self.arbol_tareas.clear()
        if not self._todos_cursos:
            return
        periodo = self.filtro_periodo_tarea.currentText()
        filtro = FILTROS_TAREA[self.filtro_estado_tarea.currentText()]
        ahora = datetime.now()

        tareas = [
            t for c in self._todos_cursos if periodo in ("Todos", c["periodo"])
            for t in c["tareas"]
        ]
        pendientes = [t for t in tareas if t["estado"] == "NOT_DELIVERED"]
        urgentes = [t for t in pendientes if (_fecha(t["vence"]) - ahora).total_seconds() < 48 * 3600]
        nuevas = [t for t in tareas if scrape.es_nueva(t)]
        self.tabs.setTabText(1, f"Tareas ({len(pendientes)})" if pendientes else "Tareas")

        partes = [f"{len(nuevas)} nuevas"] if nuevas else []
        partes.append(f"{len(pendientes)} pendientes")
        if urgentes:
            partes.append(f"{len(urgentes)} vencen en menos de 48 h")
        vencidas = sum(t["estado"] == "OUT_OF_DATE" for t in tareas)
        if vencidas:
            partes.append(f"{vencidas} vencidas sin entregar")
        self.label_resumen_tareas.setText(" · ".join(partes))

        if filtro == "NUEVAS":
            visibles = nuevas
        else:
            visibles = [t for t in tareas if filtro is None or t["estado"] in filtro]
        visibles.sort(key=lambda t: (ORDEN_ESTADO.get(t["estado"], 9), not scrape.es_nueva(t), t["vence"]))
        for t in visibles:
            self._agregar_fila_tarea(t, ahora)
        if not visibles:
            vacio = QTreeWidgetItem(["", "", "", "Nada que mostrar con este filtro"])
            vacio.setForeground(3, QColor(TEXT_MUTED))
            self.arbol_tareas.addTopLevelItem(vacio)

    def _agregar_fila_tarea(self, t: dict, ahora: datetime):
        vence = _fecha(t["vence"])
        etiqueta, color = ESTADOS_TAREA.get(t["estado"], (t["estado"] or "—", TEXT_MUTED))
        if t["estado"] == "NOT_DELIVERED" and (vence - ahora).total_seconds() < 48 * 3600:
            color = RED

        texto_vence = vence.strftime("%d/%m %H:%M") if t["vence"] else "—"
        if t["estado"] in ("NOT_DELIVERED", "SCHEDULED"):
            texto_vence += f"  ·  {_tiempo_restante(vence, ahora)}"

        titulo = scrape.limpiar_titulo(t["titulo"])
        tipo = t["tipo"] + (" ★" if t["calificada"] else "")
        item = QTreeWidgetItem([f"●  {etiqueta}", texto_vence, t["curso"], titulo, tipo, ""])
        item.setForeground(0, QColor(color))
        item.setForeground(1, QColor(TEXT_MAIN if t["estado"] == "NOT_DELIVERED" else TEXT_MUTED))
        item.setForeground(2, QColor(TEXT_MUTED))
        item.setForeground(4, QColor(TEXT_MUTED))
        item.setToolTip(3, t["titulo"])
        item.setToolTip(4, "★ = calificada" if t["calificada"] else "")
        if scrape.es_nueva(t):   # nueva: título en azul con un rótulo, sin agregar columnas
            item.setText(3, f"Nueva  ·  {titulo}")
            item.setForeground(3, QColor(BLUE))
            item.setToolTip(3, f"Apareció el {_fecha_corta(t['visto'])}\n{t['titulo']}")
        item.setData(0, Qt.ItemDataRole.UserRole, t["url"])
        self.arbol_tareas.addTopLevelItem(item)

        btn = QPushButton("Abrir")
        btn.setObjectName("accionFila")
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setIcon(qta.icon("ph.arrow-square-out", color=TEXT_MAIN))
        btn.setIconSize(QSize(14, 14))
        btn.setFixedWidth(90)
        btn.setToolTip("Abrir en el portal UTP")
        btn.clicked.connect(lambda _=False, url=t["url"]: QDesktopServices.openUrl(QUrl(url)))
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.addWidget(btn)
        fila.addStretch()
        self.arbol_tareas.setItemWidget(item, 5, contenedor)

    def _abrir_tarea_item(self, item: QTreeWidgetItem, _columna: int):
        url = item.data(0, Qt.ItemDataRole.UserRole)
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _log(self, nivel: str, color: str, mensaje: str):
        self.logs_window.agregar(nivel, color, mensaje)
        logger.log(logging.WARNING if nivel == "WARN" else logging.INFO, "%s | %s", nivel, mensaje)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())
