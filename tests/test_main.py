import xml.etree.ElementTree as ET

import pytest
from PyQt6.QtWidgets import QPushButton

import main
from main import AboutDialog, HelpDialog, LauncherDialog, MainWindow


def _menu_titles(window):
    return [action.text() for action in window.menuBar().actions()]


def _action_texts(window, menu_index):
    menu = window.menuBar().actions()[menu_index].menu()
    return [action.text() for action in menu.actions()]


def test_menus(qapp):
    window = MainWindow()
    assert _menu_titles(window) == ["Archivo", "Ver", "Ayuda"]


def test_file_menu_has_exit(qapp):
    window = MainWindow()
    assert "Salir" in _action_texts(window, 0)


def test_file_menu_has_new_launcher(qapp):
    window = MainWindow()
    assert "Nuevo acceso directo..." in _action_texts(window, 0)


def test_view_menu_has_dark_mode_toggle(qapp):
    window = MainWindow()
    assert "Alternar modo oscuro/claro" in _action_texts(window, 1)


def test_help_menu_actions(qapp):
    window = MainWindow()
    assert _action_texts(window, 2) == ["Instrucciones", "Acerca de..."]


def test_toggle_dark_mode(qapp):
    window = MainWindow()
    assert window.dark_mode is False
    window.toggle_dark_mode()
    assert window.dark_mode is True
    assert window.styleSheet() != ""
    window.toggle_dark_mode()
    assert window.dark_mode is False
    assert window.styleSheet() == ""


def test_dialogs_construct(qapp):
    assert AboutDialog(dark_mode=True).windowTitle() == "Acerca de"
    assert HelpDialog().windowTitle() == "Instrucciones"
    assert LauncherDialog().windowTitle() == "Nuevo acceso directo"


def test_save_preferences_creates_config_dir(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "CONFIG_FILE", tmp_path / "dotdesktop" / "config.xml")
    window = MainWindow()
    window._save_preferences()
    assert main.CONFIG_FILE.is_file()


def test_preferences_persisted(qapp):
    window = MainWindow()
    window.resize(333, 444)
    window.move(11, 22)
    window.toggle_dark_mode()
    window._save_preferences()

    root = ET.parse(main.CONFIG_FILE).getroot()
    assert root.findtext("window/width") == "333"
    assert root.findtext("window/height") == "444"
    assert root.findtext("window/x") == "11"
    assert root.findtext("window/y") == "22"
    assert root.findtext("settings/dark_mode") == "true"

    restored = MainWindow()
    assert restored.width() == 333
    assert restored.height() == 444
    assert restored.dark_mode is True
    assert restored.styleSheet() != ""


def test_menu_actions_have_icons(qapp):
    window = MainWindow()
    for menu_index in range(3):
        for action in window.menuBar().actions()[menu_index].menu().actions():
            if action.isSeparator():
                continue
            assert not action.icon().isNull(), action.text()


def test_logo_used_as_app_icon(qapp):
    assert main.LOGO_FILE.is_file()
    assert not MainWindow().windowIcon().isNull()
    assert not AboutDialog().windowIcon().isNull()


def test_escape_desktop_value():
    assert main._escape_desktop_value("a\\b\nc\td") == "a\\\\b\\nc\\td"


def test_escape_exec_arg():
    assert main._escape_exec_arg("/usr/bin/app") == "/usr/bin/app"
    assert main._escape_exec_arg("/opt/Mi App/app") == '"/opt/Mi App/app"'
    assert main._escape_exec_arg('/opt/a"b') == '"/opt/a\\"b"'


def test_slugify():
    assert main._slugify("Mi Editor") == "mi-editor"
    assert main._slugify("  !!!  ") == "aplicacion"


def test_build_desktop_entry():
    content = main.build_desktop_entry("Mi Editor", "/opt/Mi Editor/editor", "/tmp/icon.png")
    assert content.startswith("[Desktop Entry]\n")
    assert "Type=Application\n" in content
    assert "Name=Mi Editor\n" in content
    assert 'Exec="/opt/Mi Editor/editor"\n' in content
    assert "Categories=Utility;\n" in content
    assert content.endswith("Icon=/tmp/icon.png\n")


def test_build_desktop_entry_omits_empty_categories():
    content = main.build_desktop_entry("X", "/usr/bin/x", categories="")
    assert "Categories=" not in content


def test_launcher_category_checkboxes(qapp):
    dialog = LauncherDialog()
    assert len(dialog.category_checks) == len(main.CATEGORIES)
    assert dialog._selected_categories() == "Utility;"

    for check in dialog.category_checks.values():
        check.setChecked(False)
    assert dialog._selected_categories() == ""

    dialog.category_checks["Game"].setChecked(True)
    dialog.category_checks["Graphics"].setChecked(True)
    assert dialog._selected_categories() == "Game;Graphics;"


def test_launcher_dialog_prefills_when_editing(qapp):
    info = {
        "name": "Mi Editor",
        "exec": "/opt/editor",
        "icon": "/tmp/i.png",
        "categories": "Game;Graphics;",
    }
    dialog = LauncherDialog(filename="mi-editor.desktop", info=info)
    assert dialog.windowTitle() == "Editar acceso directo"
    assert dialog.name_edit.text() == "Mi Editor"
    assert dialog.exec_edit.text() == "/opt/editor"
    assert dialog.icon_edit.text() == "/tmp/i.png"
    assert dialog._selected_categories() == "Game;Graphics;"


def test_card_has_edit_and_delete_buttons(qapp):
    card = main.LauncherCard("x.desktop", {"name": "X"}, lambda f: None, lambda f: None)
    labels = {button.text() for button in card.findChildren(QPushButton)}
    assert {"Editar", "Eliminar"} <= labels


def test_create_desktop_entry_renames(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(main, "refresh_desktop_database", lambda: None)
    old = main.create_desktop_entry("Mi Editor", "/usr/bin/editor")

    new = main.create_desktop_entry(
        "Mi Editor Nuevo", "/usr/bin/editor", previous_filename=old.name
    )
    assert new.name == "mi-editor-nuevo.desktop"
    assert not old.exists()
    registry = main.load_registry()
    assert list(registry) == ["mi-editor-nuevo.desktop"]
    assert registry[new.name]["name"] == "Mi Editor Nuevo"


def test_create_desktop_entry_edit_same_name(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(main, "refresh_desktop_database", lambda: None)
    dest = main.create_desktop_entry("Mi Editor", "/usr/bin/editor", categories="Game;")

    again = main.create_desktop_entry(
        "Mi Editor", "/usr/bin/other", categories="Utility;", previous_filename=dest.name
    )
    assert again == dest
    assert "Exec=/usr/bin/other" in dest.read_text(encoding="utf-8")
    assert main.load_registry()[dest.name]["categories"] == "Utility;"


def test_create_desktop_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(main, "refresh_desktop_database", lambda: None)

    dest = main.create_desktop_entry("Mi Editor", "/usr/bin/editor")
    assert dest == tmp_path / "mi-editor.desktop"
    assert dest.read_text(encoding="utf-8").startswith("[Desktop Entry]")
    assert dest.stat().st_mode & 0o777 == 0o644

    with pytest.raises(FileExistsError):
        main.create_desktop_entry("Mi Editor", "/usr/bin/editor")

    assert main.create_desktop_entry("Mi Editor", "/usr/bin/editor", overwrite=True) == dest


def test_create_desktop_entry_requires_name(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(main, "refresh_desktop_database", lambda: None)
    with pytest.raises(ValueError):
        main.create_desktop_entry("   ", "/usr/bin/editor")


def test_create_desktop_entry_registers(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(main, "refresh_desktop_database", lambda: None)
    main.create_desktop_entry("Mi Editor", "/usr/bin/editor", categories="Game;")

    registry = main.load_registry()
    assert registry["mi-editor.desktop"]["name"] == "Mi Editor"
    assert registry["mi-editor.desktop"]["exec"] == "/usr/bin/editor"
    assert registry["mi-editor.desktop"]["categories"] == "Game;"


def test_delete_desktop_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(main, "refresh_desktop_database", lambda: None)
    dest = main.create_desktop_entry("Mi Editor", "/usr/bin/editor")

    main.delete_desktop_entry(dest.name)
    assert not dest.exists()
    assert main.load_registry() == {}


def test_main_window_shows_cards(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(main, "refresh_desktop_database", lambda: None)
    main.create_desktop_entry("Mi Editor", "/usr/bin/editor")

    window = MainWindow()
    cards = window.cards_container.findChildren(main.LauncherCard)
    assert len(cards) == 1
    assert cards[0].filename == "mi-editor.desktop"


def test_main_window_without_launchers(qapp):
    window = MainWindow()
    assert not window.cards_container.findChildren(main.LauncherCard)


def test_program_from_exec_handles_quotes_and_arguments():
    assert main._program_from_exec('"/opt/Mi App/app" --flag') == "/opt/Mi App/app"
    assert main._program_from_exec("/usr/bin/app %U") == "/usr/bin/app"
    assert main._program_from_exec("") == ""


def test_detect_icon_from_matching_desktop(tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    apps.mkdir()
    monkeypatch.setattr(main, "APPLICATIONS_DIR", apps)

    program = tmp_path / "program"
    program.mkdir()
    exe = program / "editor"
    exe.write_text("", encoding="utf-8")
    icon = program / "editor.png"
    icon.write_bytes(b"\x89PNG")
    (apps / "editor.desktop").write_text(
        f"[Desktop Entry]\nExec={exe}\nIcon={icon}\n", encoding="utf-8"
    )

    assert main._detect_icon(str(exe)) == str(icon.resolve())


def test_detect_icon_from_desktop_file_argument(tmp_path):
    icon = tmp_path / "icon.svg"
    icon.write_text("<svg/>", encoding="utf-8")
    desktop = tmp_path / "app.desktop"
    desktop.write_text(f"[Desktop Entry]\nIcon={icon}\n", encoding="utf-8")

    assert main._detect_icon(str(desktop)) == str(icon.resolve())


def test_detect_icon_from_nearby_image(tmp_path):
    exe = tmp_path / "app"
    exe.write_text("", encoding="utf-8")
    icon = tmp_path / "app.svg"
    icon.write_text("<svg/>", encoding="utf-8")

    assert main._detect_icon(str(exe)) == str(icon.resolve())


def test_detect_icon_from_single_image(tmp_path):
    exe = tmp_path / "app"
    exe.write_text("", encoding="utf-8")
    icon = tmp_path / "123456.png"
    icon.write_bytes(b"\x89PNG")

    assert main._detect_icon(str(exe)) == str(icon.resolve())


def test_detect_icon_from_assets_dir(tmp_path):
    exe = tmp_path / "app"
    exe.write_text("", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    icon = assets / "appicon.png"
    icon.write_bytes(b"\x89PNG")

    assert main._detect_icon(str(exe)) == str(icon.resolve())


def test_detect_icon_resolves_theme_name(tmp_path, monkeypatch):
    icon = tmp_path / "icons" / "hicolor" / "48x48" / "apps" / "miapp.svg"
    icon.parent.mkdir(parents=True)
    icon.write_text("<svg/>", encoding="utf-8")
    monkeypatch.setattr(main, "ICON_SEARCH_DIRS", (tmp_path / "icons",))

    apps = tmp_path / "apps"
    apps.mkdir()
    monkeypatch.setattr(main, "APPLICATIONS_DIR", apps)
    exe = tmp_path / "app"
    exe.write_text("", encoding="utf-8")
    (apps / "miapp.desktop").write_text(
        f"[Desktop Entry]\nExec={exe}\nIcon=miapp\n", encoding="utf-8"
    )

    assert main._detect_icon(str(exe)) == str(icon.resolve())


def test_launcher_dialog_detects_name_and_icon_without_overwriting_manual(qapp, tmp_path):
    exe = tmp_path / "app"
    exe.write_text("", encoding="utf-8")
    icon = tmp_path / "app.png"
    icon.write_bytes(b"\x89PNG")

    dialog = LauncherDialog()
    dialog._apply_detected_fields(str(exe))
    assert dialog.name_edit.text() == "App"
    assert dialog.icon_edit.text() == str(icon.resolve())

    dialog.name_edit.setText("Mi App")
    dialog.icon_edit.setText("/ruta/manual.png")
    dialog._apply_detected_fields(str(exe))
    assert dialog.name_edit.text() == "Mi App"
    assert dialog.icon_edit.text() == "/ruta/manual.png"


def test_detect_name_from_matching_desktop(tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    apps.mkdir()
    monkeypatch.setattr(main, "APPLICATIONS_DIR", apps)
    exe = tmp_path / "app"
    exe.write_text("", encoding="utf-8")
    (apps / "app.desktop").write_text(
        f"[Desktop Entry]\nName=Mi Aplicación\nExec={exe}\n", encoding="utf-8"
    )

    assert main._detect_name(str(exe)) == "Mi Aplicación"


def test_detect_name_from_desktop_file_argument(tmp_path):
    desktop = tmp_path / "app.desktop"
    desktop.write_text("[Desktop Entry]\nName=Editor\n", encoding="utf-8")

    assert main._detect_name(str(desktop)) == "Editor"


def test_detect_name_from_filename(tmp_path):
    assert main._detect_name(str(tmp_path / "fritzing-1.0.6-l2239-04e5bb02-qt6.AppImage")) == (
        "Fritzing"
    )
    assert main._detect_name(str(tmp_path / "LibreSprite-x86_64.AppImage")) == "LibreSprite"
    assert main._detect_name(str(tmp_path / "Digital-Logic-Sim.x86_64")) == "Digital Logic Sim"
    assert main._detect_name("") == ""


def test_create_desktop_entry_uses_generic_icon(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(main, "refresh_desktop_database", lambda: None)

    dest = main.create_desktop_entry("Mi Editor", str(tmp_path / "missing-bin"))
    assert f"Icon={main.GENERIC_ICON}\n" in dest.read_text(encoding="utf-8")
    assert main.load_registry()[dest.name]["icon"] == main.GENERIC_ICON


def _fake_superblock(block_size=131072, bytes_used=2048):
    block = bytearray(96)
    block[0:4] = b"hsqs"
    block[12:16] = block_size.to_bytes(4, "little")
    block[28:30] = (4).to_bytes(2, "little")
    block[30:32] = (0).to_bytes(2, "little")
    block[40:48] = bytes_used.to_bytes(8, "little")
    return bytes(block)


def test_appimage_detection_and_squashfs_offset(tmp_path):
    image = tmp_path / "app.AppImage"
    payload = bytearray(4096)
    payload[0:4] = b"\x7fELF"
    payload[8:11] = b"AI\x02"
    payload[64:68] = b"hsqs"
    payload[128:224] = _fake_superblock()
    image.write_bytes(payload)

    assert main._is_appimage(image)
    assert main._appimage_squashfs_offset(image) == 128

    image.write_bytes(b"\x7fELF" + b"\x00" * 8)
    assert not main._is_appimage(image)
    assert main._appimage_squashfs_offset(image) is None
