# AGENTS.md

PyQt6 desktop app that registers downloaded apps in the GNOME/Xfce application menu. UI strings and docs are in Spanish; keep them that way.

## Commands

No virtualenv. Dependencies live in `~/.local` (Debian/Ubuntu need `--break-system-packages`):

```bash
python3 -m pip install --user --break-system-packages PyQt6 pytest ruff
python main.py                 # run the app
pytest                         # full suite (config: testpaths=tests, addopts=-q)
pytest tests/test_main.py::test_menus   # single test
ruff check .                   # lint (E,F,I,UP,B; line-length 100, py310)
ruff format .
```

No install step needed: run and test from the repo root. Run `ruff check .` before finishing changes.

## Layout / entrypoints

- `main.py` — the whole application: constants, `DARK_STYLE`, `.desktop` launcher logic (`build_desktop_entry`, `create_desktop_entry`, `delete_desktop_entry`, `refresh_desktop_database`), the `launchers.json` registry (`load_registry`/`save_registry`), dialogs (`AboutDialog`, `HelpDialog`, `LauncherDialog`), `LauncherCard`, `MainWindow`, `main()`. `src/` is empty, reserved for future modules.
- `resources/` — `logo.png` (app + About icon) and `resources/icons/*.svg` (menu icons, referenced by filename via `_icon(name)`).
- `tests/conftest.py` — sets `QT_QPA_PLATFORM=offscreen`, provides the session-scoped `qapp` fixture, and monkeypatches `main.CONFIG_FILE`, `REGISTRY_FILE`, `ICON_CACHE_DIR` and `ICON_SEARCH_DIRS` to temp paths for test isolation. GUI tests take the `qapp` fixture and construct `MainWindow` directly.
- `PLANTILLA.md` — the PyQt6 app template these conventions come from; use it when adding new widgets/dialogs.

## Gotchas

- Never build widgets at import time; `import main` must not open a window (tests rely on this).
- `config.xml` (window geometry + `dark_mode`) lives in `~/.config/dotdesktop/` and is written on `closeEvent`; tests redirect `main.CONFIG_FILE` to a temp path via monkeypatch. The directory is created on save.
- Launchers are written to `APPLICATIONS_DIR` (`~/.local/share/applications`, module constant so tests monkeypatch it). `create_desktop_entry` raises `ValueError`/`FileExistsError`; the dialog handles overwrite confirmation. Always escape launcher fields via `_escape_desktop_value` / `_escape_exec_arg` / `_escape_exec_command`. Pass `command=` for command-line launchers (then `Exec=` is the command, not a single quoted arg) and `working_dir=` for the `Path=` key; the registry stores both as `command`/`working_dir`, empty for plain executables.
- Created launchers are tracked in `REGISTRY_FILE` (`~/.config/dotdesktop/launchers.json`; module constant, monkeypatched in tests). `load_registry` auto-drops entries whose `.desktop` no longer exists; `MainWindow` renders each entry as a `LauncherCard` with Editar/Eliminar. Editing passes `previous_filename` to `create_desktop_entry` (renames the file when the slug changes); `delete_desktop_entry` removes both file and entry.
- Menu action icons are loaded from SVG files by name; a missing icon silently yields an empty `QIcon` and breaks `test_menu_actions_have_icons` (which skips separators).
- `_detect_icon` looks for the icon in existing `.desktop` files (only `APPLICATIONS_DIR` and the executable's directory, capped at 50 files and 1 MiB each), in images next to the executable, or inside an AppImage's `.DirIcon` (via `unsquashfs`, falling back to `--appimage-extract`; cached in `ICON_CACHE_DIR`). `create_desktop_entry` falls back to `Icon=application-x-executable` when nothing is found.
- `_detect_name` uses the `Name=` of a matching `.desktop` (via `_matching_desktops`) or cleans the executable filename. `LauncherDialog._apply_detected_fields` fills name and icon when browsing the executable, without overwriting values the user typed (`_auto_name`/`_auto_icon`).
- `RESOURCES_DIR` derives from `_base_dir()`, which uses `sys._MEIPASS` when frozen so bundled resources resolve in the PyInstaller build (`packaging/build_deb.sh`, output to `packages/`, gitignored).
- This directory is a git repo (remote `origin`), but `packages/`, `build/` and the app state under `~/.config/dotdesktop/` are untracked.
