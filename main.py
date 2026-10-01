from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

PROGRAM_NAME = "dotDesktop"
PROGRAM_TITLE = "dotDesktop"
PROGRAM_VERSION = "0.2.0"
PROGRAM_DESCRIPTION = "Programa que registra en los menús de Gnome/Xfce Aplicaciones descargadas"
PROGRAM_CREDITS = "Idea y programación: @Edfasano70"

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
ICONS_DIR = RESOURCES_DIR / "icons"
LOGO_FILE = RESOURCES_DIR / "logo.png"

CONFIG_DIR = Path.home() / ".config" / "dotdesktop"
CONFIG_FILE = CONFIG_DIR / "config.xml"
REGISTRY_FILE = Path(__file__).resolve().parent / "launchers.json"

APPLICATIONS_DIR = Path.home() / ".local" / "share" / "applications"

CATEGORIES = (
    "AudioVideo",
    "Audio",
    "Video",
    "Development",
    "Education",
    "Game",
    "Graphics",
    "Network",
    "Office",
    "Science",
    "Settings",
    "System",
    "Utility",
)
DEFAULT_CATEGORY = "Utility"
DEFAULT_CATEGORIES = f"{DEFAULT_CATEGORY};"

DARK_STYLE = """
    QMainWindow, QWidget, QDialog { background-color: #1e1e1e; color: #e0e0e0; }
    QMenuBar { background-color: #2d2d2d; color: #e0e0e0; }
    QMenuBar::item { padding: 4px 8px; }
    QMenuBar::item:selected { background-color: #3d3d3d; }
    QMenu { background-color: #2d2d2d; color: #e0e0e0; }
    QMenu::item:selected { background-color: #FF9800; color: #1e1e1e; }
    QLabel { color: #e0e0e0; }
    QPushButton { background-color: #3d3d3d; border: 1px solid #555;
        border-radius: 3px; padding: 4px 8px; color: #e0e0e0; }
    QPushButton:hover { background-color: #4d4d4d; }
    #launcherCard { background-color: #2d2d2d; border: 1px solid #444;
        border-radius: 6px; }
"""


def _icon(name: str) -> QIcon:
    path = ICONS_DIR / f"{name}.svg"
    if path.is_file():
        return QIcon(str(path))
    return QIcon()


def _logo_icon() -> QIcon:
    if LOGO_FILE.is_file():
        return QIcon(str(LOGO_FILE))
    return QIcon()


_EXEC_RESERVED = set(" \t\n\"'\\><~|&;$*?#()`")


def _escape_desktop_value(value: str) -> str:
    """Escape newlines, tabs and backslashes in a desktop entry string field."""
    return (
        value.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    )


def _escape_exec_arg(value: str) -> str:
    """Quote a single Exec argument following the Desktop Entry Specification."""
    if not value:
        return '""'
    if not any(char in _EXEC_RESERVED for char in value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("$", "\\$").replace("`", "\\`")
    return f'"{escaped}"'


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower()).strip("-")
    return slug or "aplicacion"


def _normalize_categories(categories: str) -> str:
    categories = categories.strip()
    if not categories:
        return ""
    return categories if categories.endswith(";") else f"{categories};"


def build_desktop_entry(
    name: str,
    exec_path: str,
    icon_path: str = "",
    categories: str = DEFAULT_CATEGORIES,
) -> str:
    """Return the contents of a .desktop launcher for the given program."""
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={_escape_desktop_value(name)}",
        f"Exec={_escape_exec_arg(exec_path)}",
        "Terminal=false",
    ]
    normalized = _normalize_categories(categories)
    if normalized:
        lines.append(f"Categories={normalized}")
    if icon_path:
        lines.append(f"Icon={icon_path}")
    return "\n".join(lines) + "\n"


def refresh_desktop_database() -> None:
    """Refresh the application menu database so a new launcher shows up."""
    if shutil.which("update-desktop-database") is None:
        return
    try:
        subprocess.run(
            ["update-desktop-database", str(APPLICATIONS_DIR)],
            check=False,
            capture_output=True,
        )
    except OSError:
        pass


def load_registry() -> dict[str, dict]:
    """Return the launchers created by this program, dropping deleted ones."""
    if not REGISTRY_FILE.exists():
        return {}
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}

    existing = {
        filename: info
        for filename, info in data.items()
        if isinstance(info, dict) and (APPLICATIONS_DIR / filename).is_file()
    }
    if existing != data:
        save_registry(existing)
    return existing


def save_registry(registry: dict[str, dict]) -> None:
    REGISTRY_FILE.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def delete_desktop_entry(filename: str) -> None:
    """Remove a launcher file and its registry entry."""
    path = APPLICATIONS_DIR / filename
    if path.exists():
        path.unlink()
    registry = load_registry()
    registry.pop(filename, None)
    save_registry(registry)
    refresh_desktop_database()


def create_desktop_entry(
    name: str,
    exec_path: str,
    icon_path: str = "",
    categories: str = DEFAULT_CATEGORIES,
    overwrite: bool = False,
) -> Path:
    """Write a .desktop launcher under APPLICATIONS_DIR and return its path."""
    name = name.strip()
    if not name:
        raise ValueError("El nombre no puede estar vacío")

    exec_path = os.path.expanduser(exec_path.strip())
    if not exec_path:
        raise ValueError("La ruta del ejecutable no puede estar vacía")

    icon_path = os.path.expanduser(icon_path.strip())

    APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    dest = APPLICATIONS_DIR / f"{_slugify(name)}.desktop"
    if dest.exists() and not overwrite:
        raise FileExistsError(dest)

    dest.write_text(build_desktop_entry(name, exec_path, icon_path, categories), encoding="utf-8")
    os.chmod(dest, 0o644)
    refresh_desktop_database()

    registry = load_registry()
    registry[dest.name] = {
        "name": name,
        "exec": exec_path,
        "icon": icon_path,
        "categories": _normalize_categories(categories),
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    save_registry(registry)
    return dest


class AboutDialog(QDialog):
    """Diálogo modal 'Acerca de'."""

    def __init__(self, parent=None, dark_mode: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Acerca de")
        self.setWindowIcon(_logo_icon())
        self.setFixedSize(300, 350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(15, 15, 15, 15)

        pixmap = QPixmap(str(LOGO_FILE))
        if not pixmap.isNull():
            logo_label = QLabel()
            logo_label.setPixmap(
                pixmap.scaled(
                    120,
                    120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo_label)

        name_label = QLabel(PROGRAM_TITLE)
        name_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        version_label = QLabel(f"v{PROGRAM_VERSION}")
        version_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        desc_label = QLabel(PROGRAM_DESCRIPTION)
        desc_label.setFont(QFont("Arial", 9))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        credits_label = QLabel(PROGRAM_CREDITS)
        credits_label.setFont(QFont("Arial", 8))
        credits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(credits_label)

        close_btn = QPushButton("Cerrar")
        close_btn.setFixedWidth(90)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        if dark_mode:
            self.setStyleSheet(DARK_STYLE)


class HelpDialog(QDialog):
    """Diálogo modal con las instrucciones de uso."""

    def __init__(self, parent=None, dark_mode: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Instrucciones")
        self.setWindowIcon(_logo_icon())
        self.setFixedSize(390, 260)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel(f"Cómo usar {PROGRAM_TITLE}")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)

        instructions = (
            "1. Usa <b>Archivo &rarr; Nuevo acceso directo...</b> para registrar "
            "una aplicación en el menú.<br>"
            "2. Usa <b>Ver &rarr; Alternar modo oscuro/claro</b> para cambiar el tema.<br>"
            "3. Consulta <b>Ayuda &rarr; Acerca de...</b> para ver la versión.<br>"
            "4. Usa <b>Archivo &rarr; Salir</b> para cerrar la aplicación."
        )
        text_label = QLabel(instructions)
        text_label.setFont(QFont("Arial", 9))
        text_label.setWordWrap(True)
        layout.addWidget(text_label)

        layout.addStretch()

        close_btn = QPushButton("Cerrar")
        close_btn.setFixedWidth(90)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        if dark_mode:
            self.setStyleSheet(DARK_STYLE)


class LauncherDialog(QDialog):
    """Formulario para crear un acceso directo .desktop."""

    def __init__(self, parent=None, dark_mode: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuevo acceso directo")
        self.setWindowIcon(_logo_icon())
        self.setMinimumWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Mi Editor")
        form.addRow("Nombre del programa:", self.name_edit)

        self.exec_edit = QLineEdit()
        self.exec_edit.setPlaceholderText("/home/usuario/app/app")
        form.addRow("Ejecutable:", self._with_browse(self.exec_edit, self._browse_exec))

        self.icon_edit = QLineEdit()
        self.icon_edit.setPlaceholderText("(opcional)")
        form.addRow("Ícono (PNG o SVG):", self._with_browse(self.icon_edit, self._browse_icon))

        self.category_checks: dict[str, QCheckBox] = {}
        form.addRow("Categorías:", self._build_categories())
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        create_btn = QPushButton("Crear")
        create_btn.setFixedWidth(90)
        create_btn.setDefault(True)
        create_btn.clicked.connect(self._create)
        buttons.addWidget(create_btn)
        layout.addLayout(buttons)

        if dark_mode:
            self.setStyleSheet(DARK_STYLE)

    def _with_browse(self, field: QLineEdit, handler) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(field)
        browse = QPushButton("Examinar...")
        browse.clicked.connect(handler)
        row.addWidget(browse)
        return container

    def _build_categories(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        for index, category in enumerate(CATEGORIES):
            check = QCheckBox(category)
            check.setChecked(category == DEFAULT_CATEGORY)
            self.category_checks[category] = check
            grid.addWidget(check, index // 3, index % 3)
        return container

    def _selected_categories(self) -> str:
        selected = [name for name, check in self.category_checks.items() if check.isChecked()]
        return ";".join(selected) + ";" if selected else ""

    def _browse_exec(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona el ejecutable")
        if path:
            self.exec_edit.setText(path)

    def _browse_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecciona el ícono",
            filter="Imágenes (*.png *.svg *.xpm)",
        )
        if path:
            self.icon_edit.setText(path)

    def _create(self) -> None:
        name = self.name_edit.text().strip()
        exec_path = self.exec_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Datos incompletos", "El nombre no puede estar vacío.")
            return
        if not exec_path:
            QMessageBox.warning(self, "Datos incompletos", "Indica la ruta del ejecutable.")
            return

        if not os.path.isfile(os.path.expanduser(exec_path)):
            confirm = QMessageBox.question(
                self,
                "Ejecutable no encontrado",
                f"El archivo '{exec_path}' no existe.\n"
                "¿Quieres crear el acceso directo igualmente?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        dest = APPLICATIONS_DIR / f"{_slugify(name)}.desktop"
        overwrite = False
        if dest.exists():
            confirm = QMessageBox.question(
                self,
                "Ya existe",
                f"'{dest.name}' ya existe.\n¿Quieres sobrescribirlo?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            overwrite = True

        try:
            created = create_desktop_entry(
                name,
                exec_path,
                self.icon_edit.text(),
                self._selected_categories(),
                overwrite=overwrite,
            )
        except (ValueError, OSError) as error:
            QMessageBox.critical(self, "Error", f"No se pudo crear el acceso directo:\n{error}")
            return

        QMessageBox.information(
            self,
            "Acceso directo creado",
            f"Se creó '{created.name}' en:\n{created.parent}",
        )
        self.accept()


class LauncherCard(QFrame):
    """Tarjeta que representa un acceso directo creado por el programa."""

    def __init__(self, filename: str, info: dict, on_delete) -> None:
        super().__init__()
        self.filename = filename
        self.setObjectName("launcherCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        icon_path = info.get("icon", "")
        icon = QIcon(icon_path) if icon_path and Path(icon_path).is_file() else _logo_icon()
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(48, 48))
        icon_label.setFixedSize(48, 48)
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        name_label = QLabel(info.get("name", filename))
        name_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        text_layout.addWidget(name_label)

        exec_label = QLabel(info.get("exec", ""))
        exec_label.setFont(QFont("Arial", 9))
        text_layout.addWidget(exec_label)

        categories = info.get("categories", "")
        if categories:
            category_label = QLabel(categories)
            category_label.setFont(QFont("Arial", 8))
            text_layout.addWidget(category_label)

        layout.addLayout(text_layout, 1)

        delete_btn = QPushButton(_icon("delete"), "Eliminar")
        delete_btn.clicked.connect(lambda: on_delete(self.filename))
        layout.addWidget(delete_btn)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.dark_mode = False
        self.setWindowTitle(PROGRAM_TITLE)
        self.setWindowIcon(_logo_icon())
        self.resize(480, 320)
        self._build_menus()
        self._build_central()
        self._load_preferences()
        self.statusBar().showMessage("Listo")

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Archivo")
        new_action = QAction(_icon("add"), "Nuevo acceso directo...", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.show_launcher)
        file_menu.addAction(new_action)
        file_menu.addSeparator()
        exit_action = QAction(_icon("exit_to_app"), "Salir", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("Ver")
        self.dark_mode_action = QAction(_icon("brightness_6"), "Alternar modo oscuro/claro", self)
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        view_menu.addAction(self.dark_mode_action)

        help_menu = menu_bar.addMenu("Ayuda")
        instructions_action = QAction(_icon("help"), "Instrucciones", self)
        instructions_action.setShortcut("F1")
        instructions_action.triggered.connect(self.show_instructions)
        help_menu.addAction(instructions_action)

        about_action = QAction(_icon("info"), "Acerca de...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _build_central(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Accesos directos creados")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        create_btn = QPushButton(_icon("add"), "Nuevo acceso directo...")
        create_btn.clicked.connect(self.show_launcher)
        header.addWidget(create_btn)
        outer.addLayout(header)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.cards_container)
        outer.addWidget(self.scroll)

        self.setCentralWidget(central)
        self._refresh_cards()

    def _refresh_cards(self) -> None:
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        registry = load_registry()
        if not registry:
            empty = QLabel("Todavía no has creado ningún acceso directo.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.insertWidget(0, empty)
            return

        for filename, info in registry.items():
            card = LauncherCard(filename, info, self._delete_launcher)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _delete_launcher(self, filename: str) -> None:
        info = load_registry().get(filename, {})
        name = info.get("name", filename)
        confirm = QMessageBox.question(
            self,
            "Eliminar acceso directo",
            f"¿Eliminar '{name}'?\nSe borrará {filename} del menú de aplicaciones.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_desktop_entry(filename)
        except OSError as error:
            QMessageBox.critical(self, "Error", f"No se pudo eliminar:\n{error}")
            return
        self._refresh_cards()

    def _apply_dark_mode(self, enabled: bool) -> None:
        self.dark_mode = enabled
        self.setStyleSheet(DARK_STYLE if enabled else "")

    def toggle_dark_mode(self) -> None:
        self._apply_dark_mode(not self.dark_mode)

    def _center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _load_preferences(self) -> None:
        if not CONFIG_FILE.exists():
            self._center()
            return
        try:
            root = ET.parse(CONFIG_FILE).getroot()
        except ET.ParseError:
            self._center()
            return

        window = root.find("window")
        if window is None:
            self._center()
        else:
            try:
                self.resize(int(window.findtext("width")), int(window.findtext("height")))
                self.move(int(window.findtext("x")), int(window.findtext("y")))
            except (TypeError, ValueError):
                self._center()

        dark_mode = root.findtext("settings/dark_mode")
        if dark_mode is not None:
            self._apply_dark_mode(dark_mode.lower() == "true")

    def _save_preferences(self) -> None:
        root = ET.Element(PROGRAM_NAME)
        window = ET.SubElement(root, "window")
        ET.SubElement(window, "x").text = str(self.x())
        ET.SubElement(window, "y").text = str(self.y())
        ET.SubElement(window, "width").text = str(self.width())
        ET.SubElement(window, "height").text = str(self.height())
        settings = ET.SubElement(root, "settings")
        ET.SubElement(settings, "dark_mode").text = str(self.dark_mode).lower()
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tree.write(CONFIG_FILE, encoding="utf-8", xml_declaration=True)

    def closeEvent(self, event) -> None:
        self._save_preferences()
        event.accept()

    def show_launcher(self) -> None:
        dialog = LauncherDialog(self, dark_mode=self.dark_mode)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_cards()

    def show_instructions(self) -> None:
        HelpDialog(self, dark_mode=self.dark_mode).exec()

    def show_about(self) -> None:
        AboutDialog(self, dark_mode=self.dark_mode).exec()


def main() -> int:
    app = QApplication(sys.argv)
    app.setWindowIcon(_logo_icon())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
