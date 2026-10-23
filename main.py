from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

PROGRAM_NAME = "dotDesktop"
PROGRAM_TITLE = "dotDesktop"
PROGRAM_VERSION = "0.6.0"
PROGRAM_DESCRIPTION = "Programa que registra en los menús de Gnome/Xfce Aplicaciones descargadas"
PROGRAM_CREDITS = "Idea y programación: @Edfasano70"


def _base_dir() -> Path:
    """Directory that holds bundled resources (handles PyInstaller builds)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return Path(__file__).resolve().parent


BASE_DIR = _base_dir()
RESOURCES_DIR = BASE_DIR / "resources"
ICONS_DIR = RESOURCES_DIR / "icons"
LOGO_FILE = RESOURCES_DIR / "logo.png"

CONFIG_DIR = Path.home() / ".config" / "dotdesktop"
CONFIG_FILE = CONFIG_DIR / "config.xml"
REGISTRY_FILE = CONFIG_DIR / "launchers.json"

APPLICATIONS_DIR = Path.home() / ".local" / "share" / "applications"

GENERIC_ICON = "application-x-executable"
ICON_IMAGE_SUFFIXES = (".png", ".svg", ".xpm", ".jpg", ".jpeg", ".ico")
ICON_SEARCH_DIRS = (
    Path.home() / ".local" / "share" / "icons",
    Path.home() / ".icons",
    Path("/usr/local/share/icons"),
    Path("/usr/share/icons"),
    Path("/usr/share/pixmaps"),
)
ICON_CACHE_DIR = Path.home() / ".local" / "share" / "dotdesktop" / "icons"
ICON_NEARBY_DIRS = ("assets", "resources", "icons", "share/icons", "usr/share/icons")
_SQUASHFS_MAGIC = b"hsqs"

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


def _generic_icon() -> QIcon:
    icon = QIcon.fromTheme(GENERIC_ICON)
    return icon if not icon.isNull() else _logo_icon()


def _icon_from_value(value: str) -> QIcon:
    value = (value or "").strip()
    if not value:
        return _generic_icon()
    path = Path(os.path.expanduser(value))
    if path.is_file():
        return QIcon(str(path))
    if not path.is_absolute() and "/" not in value:
        icon = QIcon.fromTheme(value)
        if not icon.isNull():
            return icon
    return _generic_icon()


def _prefer_svg(paths: list[Path]) -> Path:
    for path in paths:
        if path.suffix.lower() == ".svg":
            return path
    return max(paths, key=lambda item: item.stat().st_size)


def _resolve_icon(value: str, base_dir: Path | None = None) -> str:
    """Return an existing icon file for a path or an icon theme name."""
    value = (value or "").strip()
    if not value:
        return ""
    raw = os.path.expanduser(value)
    if Path(raw).is_absolute() or "/" in raw:
        candidate = Path(raw)
        if not candidate.is_absolute() and base_dir is not None:
            candidate = base_dir / candidate
        return str(candidate.resolve()) if candidate.is_file() else ""
    if base_dir is not None:
        local = base_dir / raw
        if local.is_file():
            return str(local.resolve())

    found: list[Path] = []
    for root in ICON_SEARCH_DIRS:
        root = Path(root)
        if not root.is_dir():
            continue
        try:
            found.extend(path for path in root.glob(f"**/apps/{raw}.*") if path.is_file())
            found.extend(path for path in root.glob(f"{raw}.*") if path.is_file())
        except OSError:
            continue
    if not found:
        return ""
    return str(_prefer_svg(found).resolve())


def _read_desktop_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        if path.stat().st_size > 1024 * 1024:
            return values
        data = path.read_bytes()
    except OSError:
        return values
    for line in data.decode("utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith(("#", "[")) or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values.setdefault(key.strip(), value.strip())
    return values


def _program_from_exec(exec_value: str) -> str:
    """Return the program of a desktop Exec line, without arguments."""
    value = exec_value.strip()
    if not value:
        return ""
    if value.startswith('"'):
        chars: list[str] = []
        escaped = False
        for char in value[1:]:
            if escaped:
                chars.append(char)
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                break
            else:
                chars.append(char)
        return "".join(chars)
    return value.split()[0]


def _best_image_in(root: Path, stem: str) -> str:
    if not root.is_dir():
        return ""
    try:
        images = [
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in ICON_IMAGE_SUFFIXES
        ]
    except OSError:
        return ""
    if not images:
        return ""
    for wanted in (stem.lower(), "appicon", "icon", "logo", "application"):
        matches = [path for path in images if path.stem.lower() == wanted]
        if matches:
            return str(_prefer_svg(matches).resolve())
    if len(images) == 1:
        return str(images[0].resolve())
    return ""


def _nearby_icon(exec_path: Path) -> str:
    """Look for an icon bundled next to the given executable."""
    directory = exec_path.parent
    stem = exec_path.stem
    for suffix in ICON_IMAGE_SUFFIXES:
        candidate = directory / f"{stem}{suffix}"
        if candidate.is_file():
            return str(candidate.resolve())
    dir_icon = directory / ".DirIcon"
    if dir_icon.is_file():
        return str(dir_icon.resolve())
    for relative in ICON_NEARBY_DIRS:
        found = _best_image_in(directory / relative, stem)
        if found:
            return found
    try:
        images = [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in ICON_IMAGE_SUFFIXES
        ]
    except OSError:
        return ""
    if len(images) == 1:
        return str(images[0].resolve())
    return ""


def _is_appimage(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            header = handle.read(12)
    except OSError:
        return False
    return header[:4] == b"\x7fELF" and header[8:11] == b"AI\x02"


def _valid_squashfs_superblock(path: Path, offset: int, size: int) -> bool:
    if offset < 0 or offset + 96 > size:
        return False
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            block = handle.read(96)
    except OSError:
        return False
    if len(block) < 96 or block[:4] != _SQUASHFS_MAGIC:
        return False
    major = int.from_bytes(block[28:30], "little")
    minor = int.from_bytes(block[30:32], "little")
    block_size = int.from_bytes(block[12:16], "little")
    bytes_used = int.from_bytes(block[40:48], "little")
    if major != 4 or minor != 0:
        return False
    if block_size < 4096 or block_size > 1 << 20 or block_size & (block_size - 1):
        return False
    return 0 < bytes_used <= size - offset


def _appimage_squashfs_offset(path: Path) -> int | None:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            position = 0
            tail = b""
            while True:
                chunk = handle.read(1 << 20)
                if not chunk:
                    return None
                block = tail + chunk
                base = position - len(tail)
                index = 0
                while True:
                    found = block.find(_SQUASHFS_MAGIC, index)
                    if found < 0:
                        break
                    offset = base + found
                    if _valid_squashfs_superblock(path, offset, size):
                        return offset
                    index = found + 4
                tail = block[-3:]
                position += len(chunk)
    except OSError:
        return None


def _follow_symlink(current: str, link: str) -> str:
    if os.path.isabs(link):
        return link.lstrip("/")
    return os.path.normpath(os.path.join(os.path.dirname(current), link))


def _extract_with_unsquashfs(tool: str, image: Path, offset: int, tmpdir: Path) -> Path | None:
    current = ".DirIcon"
    for attempt in range(10):
        root = tmpdir / f"unsquashfs-{attempt}"
        try:
            subprocess.run(
                [
                    tool,
                    "-no-progress",
                    "-no-xattrs",
                    "-o",
                    str(offset),
                    "-d",
                    str(root),
                    str(image),
                    current,
                ],
                check=False,
                capture_output=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        extracted = root / current
        if not extracted.is_symlink():
            return extracted if extracted.is_file() else None
        current = _follow_symlink(current, os.readlink(extracted))
    return None


def _extract_with_runtime(image: Path, tmpdir: Path) -> Path | None:
    current = ".DirIcon"
    for attempt in range(10):
        work = tmpdir / f"runtime-{attempt}"
        work.mkdir(exist_ok=True)
        try:
            subprocess.run(
                [str(image), "--appimage-extract", current],
                cwd=work,
                check=False,
                capture_output=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        root = work / "squashfs-root"
        extracted = root / current
        if not extracted.is_symlink():
            return extracted if extracted.is_file() else None
        current = _follow_symlink(current, os.readlink(extracted))
    return None


def _cache_icon(source: Path, exec_path: Path) -> str:
    try:
        ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix.lower() or ".png"
        digest = hashlib.sha1(str(exec_path.resolve()).encode("utf-8")).hexdigest()[:10]
        destination = ICON_CACHE_DIR / f"{_slugify(exec_path.stem)}-{digest}{suffix}"
        shutil.copy2(source, destination)
    except OSError:
        return ""
    return str(destination)


def _extract_appimage_icon(path: Path) -> str:
    offset = _appimage_squashfs_offset(path)
    unsquashfs = shutil.which("unsquashfs")
    with tempfile.TemporaryDirectory(prefix="dotdesktop-icon-") as tmp:
        tmpdir = Path(tmp)
        extracted: Path | None = None
        if unsquashfs and offset is not None:
            extracted = _extract_with_unsquashfs(unsquashfs, path, offset, tmpdir)
        if extracted is None:
            extracted = _extract_with_runtime(path, tmpdir)
        if extracted is None:
            return ""
        return _cache_icon(extracted, path)


def _matching_desktops(exec_path: Path) -> list[Path]:
    """Return existing .desktop files whose Exec field points to the executable."""
    target = exec_path.resolve() if exec_path.exists() else exec_path
    matches: list[Path] = []
    seen: set[Path] = set()
    for directory in (APPLICATIONS_DIR, exec_path.parent):
        if directory in seen or not directory.is_dir():
            continue
        seen.add(directory)
        for desktop in sorted(directory.glob("*.desktop"))[:50]:
            program = _program_from_exec(_read_desktop_file(desktop).get("Exec", ""))
            if not program:
                continue
            candidate = Path(os.path.expanduser(program))
            if not candidate.is_absolute():
                candidate = desktop.parent / candidate
            try:
                if candidate.resolve() == target:
                    matches.append(desktop)
            except OSError:
                continue
    return matches


def _name_from_filename(path: Path) -> str:
    stem = re.sub(r"\.(?:appimage|run|bin|exe)$", "", path.name, flags=re.IGNORECASE)
    stem = re.sub(
        r"[-_.](?:x86_64|amd64|arm64|aarch64|i386|i686|linux|win64|osx)(?:[-_.].*)?$",
        "",
        stem,
        flags=re.IGNORECASE,
    )
    stem = re.sub(r"[-_.]v?\d[\w.-]*$", "", stem, flags=re.IGNORECASE)
    parts = [part for part in re.split(r"[-_.]+", stem) if part]
    if not parts:
        return ""
    return " ".join(
        part if any(char.isupper() for char in part) else part.capitalize() for part in parts
    )


def _detect_name(exec_path: str) -> str:
    """Try to derive a display name for the given executable path."""
    expanded = os.path.expanduser((exec_path or "").strip())
    if not expanded:
        return ""
    path = Path(expanded)

    if path.suffix == ".desktop" and path.is_file():
        return _read_desktop_file(path).get("Name", "").strip()

    for desktop in _matching_desktops(path):
        name = _read_desktop_file(desktop).get("Name", "").strip()
        if name:
            return name
    return _name_from_filename(path)


def _detect_icon(exec_path: str) -> str:
    """Try to find an icon for the given executable path."""
    expanded = os.path.expanduser((exec_path or "").strip())
    if not expanded:
        return ""
    path = Path(expanded)

    if path.suffix == ".desktop" and path.is_file():
        fields = _read_desktop_file(path)
        if fields.get("Icon", "") == GENERIC_ICON:
            return ""
        return _resolve_icon(fields.get("Icon", ""), path.parent)

    for desktop in _matching_desktops(path):
        icon = _read_desktop_file(desktop).get("Icon", "")
        if not icon or icon == GENERIC_ICON:
            continue
        resolved = _resolve_icon(icon, desktop.parent)
        if resolved:
            return resolved

    target = path.resolve() if path.exists() else path
    if target.is_file():
        nearby = _nearby_icon(target)
        if nearby:
            return nearby
        if _is_appimage(target):
            return _extract_appimage_icon(target)
    return ""


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
    value = value.replace("%", "%%")
    if not any(char in _EXEC_RESERVED for char in value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("$", "\\$").replace("`", "\\`")
    return f'"{escaped}"'


def _escape_exec_command(command: str) -> str:
    """Return a command line ready for the Exec field of a desktop entry."""
    command = command.strip()
    if "\n" in command or "\r" in command:
        raise ValueError("El comando no puede tener saltos de línea")
    return _escape_desktop_value(command).replace("%", "%%")


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
    working_dir: str = "",
    command: str = "",
) -> str:
    """Return the contents of a .desktop launcher for the given program."""
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={_escape_desktop_value(name)}",
    ]
    if command.strip():
        lines.append(f"Exec={_escape_exec_command(command)}")
    else:
        lines.append(f"Exec={_escape_exec_arg(exec_path)}")
    if working_dir.strip():
        lines.append(f"Path={_escape_desktop_value(working_dir.strip())}")
    lines.append("Terminal=false")
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


EXPORT_VERSION = "1"
_EXPORT_FIELDS = ("name", "exec", "command", "working_dir", "icon", "categories")


def export_registry_xml(dest: Path) -> int:
    """Write the created launchers to an XML file and return how many were exported."""
    registry = load_registry()
    root = ET.Element("dotdesktop", {"version": EXPORT_VERSION})
    for info in sorted(registry.values(), key=lambda item: item.get("name", "").lower()):
        node = ET.SubElement(root, "launcher")
        for field in _EXPORT_FIELDS:
            ET.SubElement(node, field).text = str(info.get(field, ""))
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dest, encoding="utf-8", xml_declaration=True)
    return len(registry)


def read_export_xml(path: Path) -> list[dict]:
    """Read an XML export and return the launcher definitions it contains."""
    root = ET.parse(path).getroot()
    if root.tag != "dotdesktop":
        raise ValueError("El archivo XML no es una exportación de dotDesktop")

    launchers: list[dict] = []
    for index, node in enumerate(root.findall("launcher"), start=1):
        info = {field: (node.findtext(field) or "").strip() for field in _EXPORT_FIELDS}
        if not info["name"]:
            raise ValueError(f"El acceso {index} no tiene nombre")
        if not info["exec"] and not info["command"]:
            raise ValueError(f"El acceso '{info['name']}' no tiene ejecutable ni comando")
        if "\n" in info["command"] or "\r" in info["command"]:
            raise ValueError(f"El comando de '{info['name']}' no puede tener saltos de línea")
        launchers.append(info)
    return launchers


def import_registry_xml(path: Path, overwrite: bool = True) -> tuple[int, int]:
    """Create launchers from an XML export, returning (imported, skipped)."""
    imported = 0
    skipped = 0
    for info in read_export_xml(path):
        dest = APPLICATIONS_DIR / f"{_slugify(info['name'])}.desktop"
        if dest.exists() and not overwrite:
            skipped += 1
            continue

        icon = info["icon"]
        expanded_icon = os.path.expanduser(icon)
        if icon and os.path.isabs(expanded_icon) and not Path(expanded_icon).exists():
            icon = ""

        create_desktop_entry(
            info["name"],
            info["exec"],
            icon,
            info["categories"],
            overwrite=True,
            command=info["command"],
            working_dir=info["working_dir"],
        )
        imported += 1
    return imported, skipped


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
    exec_path: str = "",
    icon_path: str = "",
    categories: str = DEFAULT_CATEGORIES,
    overwrite: bool = False,
    previous_filename: str | None = None,
    command: str = "",
    working_dir: str = "",
) -> Path:
    """Write a .desktop launcher under APPLICATIONS_DIR and return its path.

    Pass ``command`` to create a launcher that runs a command line instead of a
    lone executable. ``working_dir`` sets the ``Path=`` (start folder) key.

    When ``previous_filename`` is given (editing), the old file is removed if the
    generated name changed, and its registry entry is replaced.
    """
    name = name.strip()
    if not name:
        raise ValueError("El nombre no puede estar vacío")

    command = command.strip()
    exec_path = os.path.expanduser(exec_path.strip())
    working_dir = os.path.expanduser(working_dir.strip())
    if command:
        exec_path = ""
    elif not exec_path:
        raise ValueError("La ruta del ejecutable no puede estar vacía")

    icon_path = os.path.expanduser(icon_path.strip())
    if not icon_path and exec_path:
        icon_path = _detect_icon(exec_path)
    if not icon_path:
        icon_path = GENERIC_ICON

    APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    dest = APPLICATIONS_DIR / f"{_slugify(name)}.desktop"
    is_same_file = previous_filename is not None and dest.name == previous_filename
    if dest.exists() and not is_same_file and not overwrite:
        raise FileExistsError(dest)

    dest.write_text(
        build_desktop_entry(
            name, exec_path, icon_path, categories, working_dir=working_dir, command=command
        ),
        encoding="utf-8",
    )
    os.chmod(dest, 0o644)
    refresh_desktop_database()

    registry = load_registry()
    if previous_filename is not None and previous_filename != dest.name:
        registry.pop(previous_filename, None)
        old_path = APPLICATIONS_DIR / previous_filename
        if old_path.exists():
            old_path.unlink()

    existing = registry.get(dest.name, {})
    registry[dest.name] = {
        "name": name,
        "exec": exec_path or command,
        "command": command,
        "working_dir": working_dir,
        "icon": icon_path,
        "categories": _normalize_categories(categories),
        "created": existing.get("created", datetime.now().isoformat(timespec="seconds")),
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
        self.setFixedSize(390, 320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel(f"Cómo usar {PROGRAM_TITLE}")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)

        instructions = (
            "1. Usa <b>Archivo &rarr; Nuevo acceso directo...</b> para registrar "
            "una aplicación o un comando en el menú.<br>"
            "2. Elige el <b>Tipo</b> (Ejecutable o Comando) y, si lo necesitas, "
            "indica la <b>Carpeta de inicio</b>.<br>"
            "3. Usa <b>Ver &rarr; Alternar modo oscuro/claro</b> para cambiar el tema.<br>"
            "4. Usa <b>Archivo &rarr; Exportar/Importar accesos...</b> para "
            "respaldarlos o restaurarlos en XML.<br>"
            "5. Consulta <b>Ayuda &rarr; Acerca de...</b> para ver la versión.<br>"
            "6. Usa <b>Archivo &rarr; Salir</b> para cerrar la aplicación."
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
    """Formulario para crear o editar un acceso directo .desktop."""

    def __init__(
        self,
        parent=None,
        dark_mode: bool = False,
        filename: str | None = None,
        info: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self.filename = filename
        self._auto_name = ""
        self._auto_icon = ""
        editing = filename is not None and info is not None
        self.setWindowTitle("Editar acceso directo" if editing else "Nuevo acceso directo")
        self.setWindowIcon(_logo_icon())
        self.setMinimumWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Mi Editor")
        form.addRow("Nombre del programa:", self.name_edit)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Ejecutable", "Comando"])
        self.mode_combo.currentIndexChanged.connect(self._update_mode)
        form.addRow("Tipo:", self.mode_combo)

        self.exec_label = QLabel("Ejecutable:")
        self.exec_edit = QLineEdit()
        self.exec_edit.setPlaceholderText("/home/usuario/app/app")
        self.exec_row = self._with_browse(self.exec_edit, self._browse_exec)
        form.addRow(self.exec_label, self.exec_row)

        self.command_label = QLabel("Comando:")
        self.command_edit = QLineEdit()
        self.command_edit.setPlaceholderText('bash -c "..."')
        form.addRow(self.command_label, self.command_edit)

        self.working_dir_edit = QLineEdit()
        self.working_dir_edit.setPlaceholderText("(opcional)")
        form.addRow(
            "Carpeta de inicio:",
            self._with_browse(self.working_dir_edit, self._browse_working_dir),
        )

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
        save_btn = QPushButton("Guardar" if editing else "Crear")
        save_btn.setFixedWidth(90)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._create)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

        self._update_mode()
        if editing:
            self._apply_info(info)

        if dark_mode:
            self.setStyleSheet(DARK_STYLE)

    def _update_mode(self) -> None:
        command_mode = self.mode_combo.currentIndex() == 1
        self.exec_label.setVisible(not command_mode)
        self.exec_row.setVisible(not command_mode)
        self.command_label.setVisible(command_mode)
        self.command_edit.setVisible(command_mode)

    def _apply_info(self, info: dict) -> None:
        self.name_edit.setText(info.get("name", ""))
        self.working_dir_edit.setText(info.get("working_dir", ""))
        command = info.get("command", "")
        if command:
            self.mode_combo.setCurrentIndex(1)
            self.command_edit.setText(command)
        else:
            self.mode_combo.setCurrentIndex(0)
            self.exec_edit.setText(info.get("exec", ""))
        self._update_mode()
        self.icon_edit.setText(info.get("icon", ""))
        selected = {item for item in info.get("categories", "").split(";") if item}
        for category, check in self.category_checks.items():
            check.setChecked(category in selected)

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
            self._apply_detected_fields(path)

    def _browse_working_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Selecciona la carpeta de inicio")
        if path:
            self.working_dir_edit.setText(path)

    def _apply_detected_fields(self, exec_path: str) -> None:
        name = self.name_edit.text().strip()
        icon = self.icon_edit.text().strip()
        detect_name = not name or name == self._auto_name
        detect_icon = not icon or icon == self._auto_icon
        if not detect_name and not detect_icon:
            return

        detected_name = ""
        detected_icon = ""
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if detect_name:
                detected_name = _detect_name(exec_path)
            if detect_icon:
                detected_icon = _detect_icon(exec_path)
        finally:
            QApplication.restoreOverrideCursor()

        if detect_name and detected_name:
            self.name_edit.setText(detected_name)
            self._auto_name = detected_name
        if detect_icon and detected_icon:
            self.icon_edit.setText(detected_icon)
            self._auto_icon = detected_icon

    def _browse_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecciona el ícono",
            filter="Imágenes (*.png *.svg *.xpm *.ico)",
        )
        if path:
            self.icon_edit.setText(path)

    def _create(self) -> None:
        name = self.name_edit.text().strip()
        command_mode = self.mode_combo.currentIndex() == 1
        command = self.command_edit.text().strip()
        exec_path = self.exec_edit.text().strip()
        working_dir = self.working_dir_edit.text().strip()

        if command_mode and not command:
            QMessageBox.warning(self, "Datos incompletos", "Indica el comando.")
            return
        if not command_mode and not exec_path:
            QMessageBox.warning(self, "Datos incompletos", "Indica la ruta del ejecutable.")
            return

        if not name and not command_mode:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                name = _detect_name(exec_path)
            finally:
                QApplication.restoreOverrideCursor()
            if name:
                self.name_edit.setText(name)
                self._auto_name = name

        if not name:
            QMessageBox.warning(self, "Datos incompletos", "El nombre no puede estar vacío.")
            return

        if not command_mode and not os.path.isfile(os.path.expanduser(exec_path)):
            confirm = QMessageBox.question(
                self,
                "Ejecutable no encontrado",
                f"El archivo '{exec_path}' no existe.\n"
                "¿Quieres crear el acceso directo igualmente?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        working_dir_expanded = os.path.expanduser(working_dir) if working_dir else ""
        if working_dir_expanded and not os.path.isdir(working_dir_expanded):
            confirm = QMessageBox.question(
                self,
                "Carpeta no encontrada",
                f"La carpeta '{working_dir}' no existe.\n"
                "¿Quieres crear el acceso directo igualmente?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        dest = APPLICATIONS_DIR / f"{_slugify(name)}.desktop"
        is_same_file = self.filename is not None and dest.name == self.filename
        overwrite = False
        if dest.exists() and not is_same_file:
            confirm = QMessageBox.question(
                self,
                "Ya existe",
                f"'{dest.name}' ya existe.\n¿Quieres sobrescribirlo?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            overwrite = True

        icon_path = self.icon_edit.text().strip()
        if not icon_path and not command_mode:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                icon_path = _detect_icon(exec_path)
            finally:
                QApplication.restoreOverrideCursor()
            if icon_path:
                self.icon_edit.setText(icon_path)

        try:
            saved = create_desktop_entry(
                name,
                "" if command_mode else exec_path,
                icon_path,
                self._selected_categories(),
                overwrite=overwrite,
                previous_filename=self.filename,
                command=command if command_mode else "",
                working_dir=working_dir,
            )
        except (ValueError, OSError) as error:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el acceso directo:\n{error}")
            return

        action = "actualizó" if self.filename is not None else "creó"
        QMessageBox.information(
            self,
            f"Acceso directo {'actualizado' if self.filename else 'creado'}",
            f"Se {action} '{saved.name}' en:\n{saved.parent}",
        )
        self.accept()


class LauncherCard(QFrame):
    """Tarjeta que representa un acceso directo creado por el programa."""

    def __init__(self, filename: str, info: dict, on_edit, on_delete) -> None:
        super().__init__()
        self.filename = filename
        self.setObjectName("launcherCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        icon = _icon_from_value(info.get("icon", ""))
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

        labels = [name_label, exec_label]
        categories = info.get("categories", "")
        if categories:
            category_label = QLabel(categories)
            category_label.setFont(QFont("Arial", 8))
            text_layout.addWidget(category_label)
            labels.append(category_label)

        for label in labels:
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            label.setToolTip(label.text())

        layout.addLayout(text_layout, 1)

        edit_btn = QPushButton(_icon("edit"), "Editar")
        edit_btn.clicked.connect(lambda: on_edit(self.filename))
        layout.addWidget(edit_btn)

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
        export_action = QAction(_icon("file_upload"), "Exportar accesos...", self)
        export_action.triggered.connect(self.export_launchers)
        file_menu.addAction(export_action)
        import_action = QAction(_icon("file_download"), "Importar accesos...", self)
        import_action.triggered.connect(self.import_launchers)
        file_menu.addAction(import_action)
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
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
            card = LauncherCard(filename, info, self._edit_launcher, self._delete_launcher)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _edit_launcher(self, filename: str) -> None:
        info = load_registry().get(filename)
        if info is None:
            self._refresh_cards()
            return
        dialog = LauncherDialog(self, dark_mode=self.dark_mode, filename=filename, info=info)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_cards()

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

    def export_launchers(self) -> None:
        if not load_registry():
            QMessageBox.information(self, "Sin accesos", "No hay accesos directos para exportar.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar accesos directos",
            str(Path.home() / "dotdesktop-accesos.xml"),
            "Archivos XML (*.xml)",
        )
        if not path:
            return
        if not path.lower().endswith(".xml"):
            path += ".xml"

        try:
            count = export_registry_xml(Path(path))
        except OSError as error:
            QMessageBox.critical(self, "Error", f"No se pudo exportar:\n{error}")
            return

        self.statusBar().showMessage(f"{count} accesos exportados")
        QMessageBox.information(
            self,
            "Exportación completa",
            f"Se exportaron {count} accesos directos a:\n{path}",
        )

    def import_launchers(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar accesos directos",
            "",
            "Archivos XML (*.xml)",
        )
        if not path:
            return

        try:
            entries = read_export_xml(Path(path))
        except (OSError, ValueError, ET.ParseError) as error:
            QMessageBox.critical(self, "Error", f"No se pudo leer el archivo:\n{error}")
            return
        if not entries:
            QMessageBox.information(self, "Sin accesos", "El archivo no contiene accesos directos.")
            return

        collisions = {
            info["name"]
            for info in entries
            if (APPLICATIONS_DIR / f"{_slugify(info['name'])}.desktop").exists()
        }
        overwrite = True
        if collisions:
            confirm = QMessageBox.question(
                self,
                "Accesos existentes",
                f"{len(collisions)} acceso(s) ya existen.\n¿Quieres sobrescribirlos?",
            )
            overwrite = confirm == QMessageBox.StandardButton.Yes

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            imported, skipped = import_registry_xml(Path(path), overwrite=overwrite)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Error", f"No se pudieron importar los accesos:\n{error}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        self._refresh_cards()
        self.statusBar().showMessage(f"{imported} accesos importados")
        message = f"Se importaron {imported} accesos directos."
        if skipped:
            message += f"\nSe omitieron {skipped} que ya existían."
        QMessageBox.information(self, "Importación completa", message)

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
