# dotDesktop

Aplicación de escritorio para registrar en los menús de **GNOME / Xfce** las
aplicaciones que descargas (normalmente binarios o AppImages), generando su archivo
`.desktop` en `~/.local/share/applications`.

Idea y programación: **@Edfasano70**

## Capturas

| Ventana principal | Modo oscuro |
| --- | --- |
| ![Ventana principal](docs/screenshots/main.png) | ![Modo oscuro](docs/screenshots/main_dark.png) |

| Acceso desde ejecutable | Acceso desde comando |
| --- | --- |
| ![Acceso desde ejecutable](docs/screenshots/launcher_dialog.png) | ![Acceso desde comando](docs/screenshots/launcher_command.png) |

| Acerca de |
| --- |
| ![Acerca de](docs/screenshots/about.png) |

## Características

- Crea archivos `.desktop` con nombre, ejecutable o comando, carpeta de inicio, ícono y categorías.
- Interfaz gráfica en PyQt6, con selector de archivos, carpetas y lista de categorías.
- Valida el ejecutable y la carpeta de inicio, y avisa si no existen.
- Pregunta antes de sobrescribir un acceso directo existente.
- Escapa los campos según la especificación *Desktop Entry*.
- Refresca el menú con `update-desktop-database` si está disponible.
- Registra los accesos creados y los muestra como tarjetas en la pantalla principal.
- Permite editar los accesos creados (renombra el `.desktop` si cambia el nombre).
- Permite eliminar los accesos creados (borra el `.desktop` y su registro).
- Exporta e importa los accesos creados mediante un archivo XML.
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

1. **Tipo** — `Ejecutable` para un binario o AppImage, o `Comando` para una línea
   de comandos (por ejemplo `bash -c "..."`).
2. **Nombre del programa** — tal como aparecerá en el menú. Se completa solo al
   elegir el ejecutable, a partir de un `.desktop` existente o del nombre del archivo.
3. **Ejecutable** — ruta al binario o AppImage. Al elegirlo, dotDesktop intenta
   detectar el nombre y el ícono automáticamente (desde un `.desktop` existente,
   una imagen junto al ejecutable o el ícono interno del AppImage).
4. **Comando** — línea de comandos que se ejecutará al abrir el acceso.
5. **Carpeta de inicio** (opcional) — directorio de trabajo (`Path=` del `.desktop`).
6. **Ícono** (opcional) — PNG o SVG; se completa solo si se detecta. Si no hay
   ícono, se usa el genérico del sistema (`application-x-executable`).
7. **Categorías** — una o varias casillas.

Ejemplo de acceso por comando: **Tipo** `Comando`, **Comando**
`bash -c "date +%F"` y **Carpeta de inicio** `/home/usuario`.

El acceso aparece listado como tarjeta y se puede **Editar** o **Eliminar** con sus botones.

### Exportar e importar

Usa **Archivo → Exportar accesos...** para guardar todos los accesos creados en un
archivo XML, e **Archivo → Importar accesos...** para restaurarlos. Si ya existe un
acceso con el mismo nombre, se pregunta si se quiere sobrescribir; los demás se
importan igualmente.

El XML generado tiene este formato:

```xml
<?xml version='1.0' encoding='utf-8'?>
<dotdesktop version="1">
  <launcher>
    <name>Consola</name>
    <exec></exec>
    <command>bash -c "date +%F"</command>
    <working_dir>/home/usuario</working_dir>
    <icon></icon>
    <categories>Utility;</categories>
  </launcher>
</dotdesktop>
```

## Estructura del proyecto

```
main.py                     # toda la aplicación (GUI, lógica .desktop, registro, main())
resources/
├── logo.png                # ícono de la aplicación y de "Acerca de"
├── logo.svg                # fuente editable del logo
└── icons/                  # íconos de menú en SVG
docs/screenshots/           # capturas para el README
packaging/
├── build_deb.sh            # compila con PyInstaller y genera el .deb
├── dotdesktop.desktop      # entrada de menú instalada
├── postinst / postrm       # scripts de mantenimiento del paquete
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

## Empaquetado (.deb)

Requiere `pyinstaller` y `dpkg-deb` (`dpkg-dev`):

```bash
python3 -m pip install --user --break-system-packages pyinstaller
./packaging/build_deb.sh
```

El script compila un binario autónomo con PyInstaller y genera
`packages/dotdesktop_<versión>_<arquitectura>.deb` (la carpeta `packages/` está
ignorada por git). El paquete instala la app en `/opt/dotdesktop`, crea
`/usr/bin/dotdesktop`, la entrada de menú en `/usr/share/applications` y el ícono en
`/usr/share/icons/hicolor`.

## Persistencia

- Preferencias (geometría de ventana y tema): `~/.config/dotdesktop/config.xml`.
- Registro de accesos creados por el programa: `~/.config/dotdesktop/launchers.json`.
- Íconos extraídos de AppImages: `~/.local/share/dotdesktop/icons/`.
- Archivos `.desktop`: `~/.local/share/applications`.
