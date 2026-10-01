# dotDesktop

Aplicación de escritorio para registrar en los menús de **GNOME / Xfce** las
aplicaciones que descargas (normalmente binarios o AppImages), generando su archivo
`.desktop` en `~/.local/share/applications`.

Idea y programación: **@Edfasano70**

## Capturas

| Ventana principal | Modo oscuro |
| --- | --- |
| ![Ventana principal](docs/screenshots/main.png) | ![Modo oscuro](docs/screenshots/main_dark.png) |

| Nuevo acceso directo | Acerca de |
| --- | --- |
| ![Nuevo acceso directo](docs/screenshots/launcher_dialog.png) | ![Acerca de](docs/screenshots/about.png) |

## Características

- Crea archivos `.desktop` con nombre, ejecutable, ícono y categorías.
- Interfaz gráfica en PyQt6, con selector de archivos y lista de categorías.
- Valida el ejecutable y avisa si no existe.
- Pregunta antes de sobrescribir un acceso directo existente.
- Escapa los campos según la especificación *Desktop Entry*.
- Refresca el menú con `update-desktop-database` si está disponible.
- Registra los accesos creados y los muestra como tarjetas en la pantalla principal.
- Permite eliminar los accesos creados (borra el `.desktop` y su registro).
- Tema claro/oscuro y geometría de ventana persistentes.

## Requisitos

- Python 3.10 o superior
- PyQt6

## Instalación

No se usa entorno virtual. En Debian/Ubuntu, `--break-system-packages` es necesario
por la regla PEP 668:

```bash
python3 -m pip install --user --break-system-packages PyQt6
```

No hace falta instalar el proyecto: los comandos se ejecutan desde la raíz del repo.

## Uso

```bash
python main.py
```

En la ventana principal, usa **Archivo → Nuevo acceso directo...** (o el botón
**Nuevo acceso directo...**) e indica:

1. **Nombre del programa** — tal como aparecerá en el menú.
2. **Ejecutable** — ruta al binario o AppImage.
3. **Ícono** (opcional) — PNG o SVG.
4. **Categorías** — una o varias casillas.

El acceso aparece listado como tarjeta y se puede eliminar con su botón **Eliminar**.

## Estructura del proyecto

```
main.py                     # toda la aplicación (GUI, lógica .desktop, registro, main())
resources/
├── logo.png                # ícono de la aplicación y de "Acerca de"
├── logo.svg                # fuente editable del logo
└── icons/                  # íconos de menú en SVG
docs/screenshots/           # capturas para el README
src/                        # vacío, reservado para módulos futuros
tests/                      # pytest
pyproject.toml              # ruff + pytest + metadatos
```

## Desarrollo

Instala las dependencias de desarrollo y ejecuta las comprobaciones:

```bash
python3 -m pip install --user --break-system-packages pytest ruff
pytest                       # suite completa
pytest tests/test_main.py::test_menus   # un solo test
ruff check .                 # lint
ruff format .                # formato
```

## Persistencia

- Preferencias (geometría de ventana y tema): `~/.config/dotdesktop/config.xml`.
- Accesos directos creados por el programa: `launchers.json` (ignorado por git).
- Archivos `.desktop`: `~/.local/share/applications`.
