import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QDialog, QFormLayout, QSpinBox,
    QFileDialog, QTextEdit, QFrame, QMessageBox, QSpacerItem, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QComboBox, QCheckBox, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont
import qtawesome as qta

import auth
import scrape
import descargar_materiales
import descargar_zoom

SESION_DIR = str(Path(__file__).parent / "sesion")
BASE_URL = "https://class.utp.edu.pe"

DARK_BG = "#0e1013"
PANEL_BG = "#15181d"
BORDER = "#262a31"
BLUE = "#3b82f6"
GREEN = "#22c55e"
ORANGE = "#f59e0b"
TEXT_MUTED = "#9aa1ac"
TEXT_MAIN = "#e5e7eb"

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
QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_MUTED};
    margin-right: 8px;
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
"""

class ScraperWorker(QThread):
    log = Signal(str, str, str)   # nivel, color, mensaje
    progreso = Signal(int, int)   # actual, total
    curso = Signal(dict)          # {nombre, periodo, materiales, videos} — uno a uno
    terminado = Signal(bool)      # éxito

    def __init__(self, utp_user: str, utp_pass: str):
        super().__init__()
        self.utp_user = utp_user
        self.utp_pass = utp_pass

    def run(self):
        if not self.utp_user or not self.utp_pass:
            self.log.emit("WARN", ORANGE, "Falta UTP USER/UTP PASS — configúralos en ⚙")
            self.terminado.emit(False)
            return

        # auth.py lee credenciales de módulo — se las inyectamos desde la config de la UI
        auth.UTP_USER = self.utp_user
        auth.UTP_PASS = self.utp_pass

        try:
            self.log.emit("INFO", "gray", "Abriendo navegador...")
            emitir_log = lambda nivel, color, msg: self.log.emit(nivel, color, msg)
            emitir_progreso = lambda actual, total: self.progreso.emit(actual, total)
            emitir_curso = lambda curso: self.curso.emit(curso)
            scrape.listar_todo(
                SESION_DIR, log=emitir_log,
                progreso=emitir_progreso, curso_listo=emitir_curso,
            )
            self.terminado.emit(True)
        except Exception as e:
            self.log.emit("WARN", ORANGE, f"Error: {e}")
            self.terminado.emit(False)


class MaterialesWorker(QThread):
    log = Signal(str, str, str)
    progreso = Signal(int, int)
    terminado = Signal(dict)   # {"ok": int, "fail": int}

    def __init__(self, utp_user: str, utp_pass: str, base_dir: str, nombres: list[str] | None = None):
        super().__init__()
        self.utp_user = utp_user
        self.utp_pass = utp_pass
        self.base_dir = base_dir
        self.nombres = nombres

    def run(self):
        if not self.utp_user or not self.utp_pass:
            self.log.emit("WARN", ORANGE, "Falta UTP USER/UTP PASS — configúralos en ⚙")
            self.terminado.emit({"ok": 0, "fail": 0})
            return

        auth.UTP_USER = self.utp_user
        auth.UTP_PASS = self.utp_pass

        try:
            resumen = descargar_materiales.descargar_materiales(
                SESION_DIR, self.base_dir,
                log=lambda n, c, m: self.log.emit(n, c, m),
                progreso=lambda a, t: self.progreso.emit(a, t),
                nombres=self.nombres,
            )
            self.terminado.emit(resumen)
        except Exception as e:
            self.log.emit("WARN", ORANGE, f"Error: {e}")
            self.terminado.emit({"ok": 0, "fail": 0})


class ZoomWorker(QThread):
    log = Signal(str, str, str)
    progreso = Signal(int, int)
    terminado = Signal(dict)   # {"ok": int, "fail": int}

    def __init__(self, utp_user: str, utp_pass: str, base_dir: str, workers: int,
                 nombres: list[str] | None = None):
        super().__init__()
        self.utp_user = utp_user
        self.utp_pass = utp_pass
        self.base_dir = base_dir
        self.workers = workers
        self.nombres = nombres

    def run(self):
        if not self.utp_user or not self.utp_pass:
            self.log.emit("WARN", ORANGE, "Falta UTP USER/UTP PASS — configúralos en ⚙")
            self.terminado.emit({"ok": 0, "fail": 0})
            return

        auth.UTP_USER = self.utp_user
        auth.UTP_PASS = self.utp_pass

        try:
            resumen = descargar_zoom.descargar_zoom(
                SESION_DIR, self.base_dir, workers=self.workers,
                log=lambda n, c, m: self.log.emit(n, c, m),
                progreso=lambda a, t: self.progreso.emit(a, t),
                nombres=self.nombres,
            )
            self.terminado.emit(resumen)
        except Exception as e:
            self.log.emit("WARN", ORANGE, f"Error: {e}")
            self.terminado.emit({"ok": 0, "fail": 0})


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
        hint = QLabel("1-8, default 4")
        hint.setProperty("muted", "true")
        form.addRow("ZOOM WORKERS", fila_zoom)
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

        self.config = {
            "utp_user": "",
            "utp_pass": "",
            "base_dir": str(Path.home() / "Documents" / "utp-class-downloader"),
            "zoom_workers": 4,
        }

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

        # ── panel de resultados: cursos / materiales / videos ──
        panel = QFrame()
        panel.setObjectName("resultadosPanel")
        panel_layout = QVBoxLayout(panel)
        fila_titulo = QHBoxLayout()
        label_resultados = QLabel("Cursos")
        label_resultados.setProperty("muted", "true")
        self.label_estado = QLabel("")
        self.label_estado.setProperty("muted", "true")
        self.progreso_bar = QProgressBar()
        self.progreso_bar.setFixedWidth(160)
        self.progreso_bar.setFixedHeight(18)
        self.progreso_bar.setTextVisible(True)
        self.progreso_bar.setVisible(False)
        fila_titulo.addWidget(label_resultados)
        fila_titulo.addStretch()
        fila_titulo.addWidget(self.progreso_bar)
        fila_titulo.addWidget(self.label_estado)

        fila_filtro = QHBoxLayout()
        label_periodo = QLabel("Periodo")
        label_periodo.setProperty("muted", "true")
        self.filtro_periodo = QComboBox()
        self.filtro_periodo.addItem("Todos")
        self.filtro_periodo.currentTextChanged.connect(self._filtrar)
        fila_filtro.addWidget(label_periodo)
        fila_filtro.addWidget(self.filtro_periodo)
        fila_filtro.addStretch()

        self.btn_detectar = QPushButton("Analizar Carpeta")
        self.btn_detectar.setObjectName("seleccionar")
        self.btn_detectar.setIcon(qta.icon("ph.magnifying-glass", color=TEXT_MAIN))
        self.btn_detectar.setIconSize(QSize(14, 14))
        self.btn_detectar.setToolTip("Buscar qué materiales/videos ya están descargados en disco")
        self.btn_detectar.clicked.connect(self.detectar_descargas)
        fila_filtro.addWidget(self.btn_detectar)

        self.btn_seleccionar = QPushButton("Seleccionar")
        self.btn_seleccionar.setObjectName("seleccionar")
        self.btn_seleccionar.setCheckable(True)
        self.btn_seleccionar.toggled.connect(self._toggle_modo_seleccion)
        fila_filtro.addWidget(self.btn_seleccionar)

        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabels(["Curso", "Periodo", "Materiales", "Videos", "Acciones", "En disco"])
        self.arbol.setRootIsDecorated(False)
        self.arbol.setColumnWidth(0, 280)
        self.arbol.setColumnWidth(1, 100)
        self.arbol.setColumnWidth(2, 100)
        self.arbol.setColumnWidth(3, 100)
        self.arbol.setColumnWidth(4, 300)
        self.arbol.setColumnWidth(5, 160)
        self.arbol.headerItem().setTextAlignment(4, Qt.AlignmentFlag.AlignCenter)
        self.arbol.headerItem().setTextAlignment(5, Qt.AlignmentFlag.AlignCenter)
        panel_layout.addLayout(fila_titulo)
        panel_layout.addLayout(fila_filtro)
        panel_layout.addWidget(self.arbol)
        root.addWidget(panel, stretch=1)

        self.setCentralWidget(central)
        self.setStyleSheet(STYLE)

        self.worker = None
        self._todos_cursos = []
        self._widgets_fila = []
        self._sel_materiales = set()
        self._sel_videos = set()
        self._modo_seleccion = False
        self._cola_seleccionados = []
        self._labels_estado = {}
        self._detectado = {}

    def _abrir_logs(self):
        self.logs_window.show()
        self.logs_window.raise_()
        self.logs_window.activateWindow()

    def abrir_configuracion(self):
        dialogo = ConfiguracionDialog(self, valores=self.config)
        if dialogo.exec():
            self.config = dialogo.obtener_valores()
            self._log("OK", "#3b82f6", "Configuración guardada")

    def _set_ocupado(self, ocupado: bool):
        # los 3 flujos abren Playwright sobre el mismo sesion/ — no pueden correr a la vez
        self.btn_iniciar.setEnabled(not ocupado)
        self.btn_descargar_materiales.setEnabled(not ocupado)
        self.btn_descargar_zoom.setEnabled(not ocupado)
        self.btn_descargar_seleccionados.setEnabled(not ocupado)
        for widget in self._widgets_fila:
            widget.setEnabled(not ocupado)

    def iniciar(self):
        self.logs_window.texto.clear()
        self.arbol.clear()
        self._todos_cursos = []
        self._widgets_fila = []
        self._sel_materiales = set()
        self._sel_videos = set()
        self._labels_estado = {}
        self._detectado = {}
        self.btn_seleccionar.blockSignals(True)
        self.btn_seleccionar.setChecked(False)
        self.btn_seleccionar.blockSignals(False)
        self._modo_seleccion = False
        self.btn_descargar_seleccionados.setVisible(False)
        self.btn_descargar_materiales.setVisible(False)
        self.btn_descargar_zoom.setVisible(False)
        self.filtro_periodo.blockSignals(True)
        self.filtro_periodo.clear()
        self.filtro_periodo.addItem("Todos")
        self.filtro_periodo.blockSignals(False)
        self.label_estado.setText("Iniciando...")
        self._set_ocupado(True)

        self.worker = ScraperWorker(self.config["utp_user"], self.config["utp_pass"])
        self.worker.log.connect(self._log)
        self.worker.progreso.connect(self._actualizar_progreso)
        self.worker.curso.connect(self._agregar_curso)
        self.worker.terminado.connect(self._login_terminado)
        self.worker.start()

    def descargar_materiales(self, nombres: list[str] | None = None):
        self.logs_window.texto.clear()
        self.label_estado.setText(
            f"Descargando materiales de {len(nombres)} curso(s)..." if nombres
            else "Descargando materiales de todos los cursos..."
        )
        self._set_ocupado(True)

        self.worker_materiales = MaterialesWorker(
            self.config["utp_user"], self.config["utp_pass"], self.config["base_dir"],
            nombres=nombres,
        )
        self.worker_materiales.log.connect(self._log)
        self.worker_materiales.progreso.connect(self._actualizar_progreso)
        self.worker_materiales.terminado.connect(self._descarga_terminada)
        self.worker_materiales.start()

    def descargar_zoom_clases(self, nombres: list[str] | None = None):
        self.logs_window.texto.clear()
        self.label_estado.setText(
            f"Descargando grabaciones de {len(nombres)} curso(s)..." if nombres
            else "Descargando grabaciones de todos los cursos..."
        )
        self._set_ocupado(True)

        self.worker_zoom = ZoomWorker(
            self.config["utp_user"], self.config["utp_pass"],
            self.config["base_dir"], self.config["zoom_workers"],
            nombres=nombres,
        )
        self.worker_zoom.log.connect(self._log)
        self.worker_zoom.progreso.connect(self._actualizar_progreso)
        self.worker_zoom.terminado.connect(self._descarga_terminada)
        self.worker_zoom.start()

    def _toggle_modo_seleccion(self, activo: bool):
        self._modo_seleccion = activo
        self._filtrar(self.filtro_periodo.currentText())

    def detectar_descargas(self):
        if not self._todos_cursos:
            self._log("WARN", "#f59e0b", "Primero corre Iniciar para tener la lista de cursos")
            return

        base_dir = self.config["base_dir"]
        for c in self._todos_cursos:
            nombre = c["nombre"]
            local = scrape.contar_archivos_locales(base_dir, c["periodo"], nombre)
            mat_local, mat_total = local["archivos_locales"], c["materiales"]
            vid_local, vid_total = local["videos_locales"], c["videos"]

            if mat_local == 0 and vid_local == 0:
                texto = "— Pendiente"
            else:
                texto = f"📄 {mat_local}/{mat_total} · 🎥 {vid_local}/{vid_total}"
            self._detectado[nombre] = texto

            label = self._labels_estado.get(nombre)
            if label:
                label.setText(texto)

        self._log("OK", "#3b82f6", "Detección de archivos en disco completa")

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

    def _descarga_terminada(self, resumen: dict):
        if self._cola_seleccionados:
            self._procesar_siguiente_seleccionado()
            return
        self._set_ocupado(False)
        self.progreso_bar.setVisible(False)
        self.label_estado.setText(f"Listo — {resumen.get('ok', 0)} ok, {resumen.get('fail', 0)} fallidos")

    def _actualizar_progreso(self, actual: int, total: int):
        self.progreso_bar.setVisible(True)
        self.progreso_bar.setMaximum(total)
        self.progreso_bar.setValue(actual)
        self.label_estado.setText(f"Procesando {actual}/{total} cursos...")

    def _agregar_curso(self, c: dict):
        self._todos_cursos.append(c)
        if self.filtro_periodo.findText(c["periodo"]) == -1:
            self.filtro_periodo.addItem(c["periodo"])

        filtro_actual = self.filtro_periodo.currentText()
        if filtro_actual in ("Todos", c["periodo"]):
            self._agregar_fila(c)

    def _agregar_fila(self, c: dict):
        nombre_curso = c["nombre"]
        item = QTreeWidgetItem([nombre_curso, c["periodo"], "", "", "", ""])
        self.arbol.addTopLevelItem(item)

        celda_mat = self._crear_celda_conteo(
            nombre_curso, c["materiales"], self._sel_materiales, self._toggle_sel_materiales,
        )
        celda_vid = self._crear_celda_conteo(
            nombre_curso, c["videos"], self._sel_videos, self._toggle_sel_videos,
        )
        widget_acciones = self._crear_widget_acciones(nombre_curso)

        label_estado_disco = QLabel(self._detectado.get(nombre_curso, "—"))
        label_estado_disco.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_estado_disco.setProperty("muted", "true")
        self._labels_estado[nombre_curso] = label_estado_disco

        self.arbol.setItemWidget(item, 2, celda_mat)
        self.arbol.setItemWidget(item, 3, celda_vid)
        self.arbol.setItemWidget(item, 4, widget_acciones)
        self.arbol.setItemWidget(item, 5, label_estado_disco)

    def _crear_celda_conteo(self, nombre_curso: str, cantidad: int, conjunto: set, on_toggle):
        if not self._modo_seleccion:
            label = QLabel(str(cantidad))
            label.setContentsMargins(8, 0, 0, 0)
            return label

        chk = QCheckBox(str(cantidad))
        chk.setChecked(nombre_curso in conjunto)
        chk.toggled.connect(lambda marcado, n=nombre_curso: on_toggle(n, marcado))
        self._widgets_fila.append(chk)
        return chk

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

    def _crear_widget_acciones(self, nombre_curso: str) -> QWidget:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(4)

        btn_mat = QPushButton("Descargar Materiales")
        btn_mat.setObjectName("accionFila")
        btn_mat.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_mat.setIcon(qta.icon("ph.file-text", color=TEXT_MAIN))
        btn_mat.setIconSize(QSize(14, 14))
        btn_mat.setToolTip(f"Descargar materiales de {nombre_curso}")
        btn_mat.clicked.connect(lambda: self.descargar_materiales(nombres=[nombre_curso]))

        btn_vid = QPushButton("Descargar Clases")
        btn_vid.setObjectName("accionFila")
        btn_vid.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_vid.setIcon(qta.icon("ph.video-camera", color=TEXT_MAIN))
        btn_vid.setIconSize(QSize(14, 14))
        btn_vid.setToolTip(f"Descargar clases grabadas de {nombre_curso}")
        btn_vid.clicked.connect(lambda: self.descargar_zoom_clases(nombres=[nombre_curso]))

        fila.addWidget(btn_mat)
        fila.addWidget(btn_vid)
        self._widgets_fila.extend([btn_mat, btn_vid])
        return contenedor

    def _actualizar_boton_seleccionados(self):
        hay_alguno = bool(self._sel_materiales) or bool(self._sel_videos)
        self.btn_descargar_seleccionados.setVisible(hay_alguno)

    def _filtrar(self, periodo: str):
        self.arbol.clear()
        self._widgets_fila = []
        self._labels_estado = {}
        self._actualizar_boton_seleccionados()
        for c in self._todos_cursos:
            if periodo == "Todos" or c["periodo"] == periodo:
                self._agregar_fila(c)

    def _login_terminado(self, exito: bool):
        self._set_ocupado(False)
        self.progreso_bar.setVisible(False)
        total = self.arbol.topLevelItemCount()
        self.label_estado.setText(f"Listo — {total} cursos" if exito else "Falló")
        if exito:
            self.btn_descargar_materiales.setVisible(True)
            self.btn_descargar_zoom.setVisible(True)
            self.detectar_descargas()

    def _log(self, nivel: str, color: str, mensaje: str):
        self.logs_window.agregar(nivel, color, mensaje)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())
