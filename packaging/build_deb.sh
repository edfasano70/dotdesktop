#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="dotdesktop"
VERSION="$(python3 -c "import re; print(re.search(r'PROGRAM_VERSION = \"([^\"]+)\"', open('${ROOT}/main.py').read()).group(1))")"
ARCH="$(dpkg --print-architecture)"
MAINTAINER="EdFasano70 <edfasano70@gmail.com>"

OUT="$ROOT/packages"
BUILD="$ROOT/build/deb"
DIST="$BUILD/dist"
STAGE="$BUILD/${PKG}_${VERSION}_${ARCH}"

cd "$ROOT"

echo ">> Compilando con PyInstaller (${PKG} ${VERSION}, ${ARCH})"
rm -rf "$BUILD"
mkdir -p "$OUT" "$STAGE/DEBIAN"

pyinstaller --noconfirm --clean --windowed \
    --name "$PKG" \
    --add-data "$ROOT/resources:resources" \
    --distpath "$DIST" \
    --workpath "$BUILD/work" \
    --specpath "$BUILD" \
    "$ROOT/main.py"

echo ">> Preparando el árbol del paquete"
mkdir -p "$STAGE/opt/$PKG"
cp -a "$DIST/$PKG/." "$STAGE/opt/$PKG/"

mkdir -p "$STAGE/usr/bin"
ln -sf "/opt/$PKG/$PKG" "$STAGE/usr/bin/$PKG"

mkdir -p "$STAGE/usr/share/applications"
cp "$ROOT/packaging/$PKG.desktop" "$STAGE/usr/share/applications/$PKG.desktop"

mkdir -p "$STAGE/usr/share/icons/hicolor/128x128/apps"
cp "$ROOT/resources/logo.png" "$STAGE/usr/share/icons/hicolor/128x128/apps/$PKG.png"

install -m 755 "$ROOT/packaging/postinst" "$STAGE/DEBIAN/postinst"
install -m 755 "$ROOT/packaging/postrm" "$STAGE/DEBIAN/postrm"

SIZE="$(du -sk "$STAGE" | cut -f1)"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: $MAINTAINER
Installed-Size: $SIZE
Depends: libc6, libgl1, libegl1, libxkbcommon-x11-0, libxcb-cursor0, libxcb-xinerama0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0
Description: Registra aplicaciones descargadas en el menu de GNOME/Xfce
 dotDesktop es una aplicacion de escritorio en PyQt6 que crea y gestiona
 archivos .desktop para registrar aplicaciones descargadas (binarios o
 AppImages) en el menu de aplicaciones de GNOME/Xfce.
EOF

echo ">> Generando el .deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT/${PKG}_${VERSION}_${ARCH}.deb"

echo ">> Listo: $OUT/${PKG}_${VERSION}_${ARCH}.deb"
