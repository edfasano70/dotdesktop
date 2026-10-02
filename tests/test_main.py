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
