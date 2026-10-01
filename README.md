# dotDesktop

Programa que registra en los menús de Gnome/Xfce Aplicaciones descargadas

Idea y programación: @Edfasano70

Estructura plana: todo el código en `main.py`, los recursos en `resources/` y `src/`
reservado para futuros módulos.

```
main.py            # toda la aplicación (MainWindow, diálogos, persistencia, main())
resources/         # logo.png + icons/*.svg
src/               # vacío (para módulos futuros)
tests/             # pytest
pyproject.toml     # ruff + pytest + metadatos
```

## Setup

No se usa entorno virtual. Solo necesitas PyQt6, pytest y ruff en tu usuario:

```bash
python3 -m pip install --user --break-system-packages PyQt6 pytest ruff
```

`--user` escribe en `~/.local` y `--break-system-packages` es necesario en Debian/Ubuntu
(regla PEP 668). No hace falta instalar el proyecto: `python main.py` y `pytest` funcionan
directamente desde la raíz.

## Run

```bash
python main.py
```

## Uso

En la ventana principal, usa **Archivo → Nuevo acceso directo...** (o el botón superior)
para registrar una aplicación: indica el nombre, la ruta del ejecutable y, opcionalmente,
el ícono y las categorías. Se genera un archivo `.desktop` en
`~/.local/share/applications` y se refresca el menú con `update-desktop-database`
si está disponible.

Los accesos directos creados se muestran como tarjetas en la pantalla principal, con un
botón **Eliminar** que borra el `.desktop` y su registro. La lista de accesos creados por
el programa se guarda en `launchers.json` (ignorado por git); si borras un `.desktop` a
mano, la tarjeta desaparece al recargar.

## Test / Lint

```bash
pytest
pytest tests/test_main.py::test_menus
ruff check .
ruff format .
```

## Persistencia

La geometría de la ventana y el tema se guardan en `~/.config/dotdesktop/config.xml`.
