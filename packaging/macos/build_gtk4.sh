#!/bin/bash
# GTK 4 with its macOS backend for a MacPorts runtime (fetch_macports.py): MacPorts archives GTK 4
# only with the X11 backend, which opens no window on a Mac without XQuartz. The same release is
# built here for macOS 13 against the runtime's libraries (build_appstream.sh prepares the headers
# in out/macports13-dev), with the macOS backend only and no introspection (the archive's
# typelibs describe the same version), and replaces the archive's libgtk-4.1.dylib.
#
# usage: packaging/macos/build_gtk4.sh <runtime prefix>   (after build_appstream.sh)
set -euo pipefail
runtime=$(cd "$1" && pwd)
out=$(cd "$(dirname "$0")/../.." && pwd)/out
dev=$out/macports13-dev
version=$(ls "$out"/macports-darwin22/gtk4-*.tbz2 | sed -E 's#.*/gtk4-([0-9.]+)_.*#\1#' | sort -V | tail -1)
work=$out/gtk-$version
[[ -d $dev/include/glib-2.0 && -x $out/mesonenv/bin/meson ]] || { echo "run build_appstream.sh first"; exit 1; }
[[ -d $work ]] || curl -fsSL "https://download.gnome.org/sources/gtk/${version%.*}/gtk-$version.tar.xz" | tar -xJ -C "$out"

export PKG_CONFIG=$out/pkgconf-define-prefix PKG_CONFIG_PATH=$dev/lib/pkgconfig:$dev/share/pkgconfig
export PATH=$out/mesonenv/bin:/opt/homebrew/bin:/usr/bin:/bin:$dev/bin MACOSX_DEPLOYMENT_TARGET=13.0
cd "$work"
[[ -d build ]] || meson setup build --prefix=/opt/local --buildtype=release \
    -Dc_args="-I$dev/include -mmacosx-version-min=13.0" -Dobjc_args="-I$dev/include -mmacosx-version-min=13.0" \
    -Dc_link_args="-L$dev/lib -mmacosx-version-min=13.0" -Dobjc_link_args="-L$dev/lib -mmacosx-version-min=13.0" \
    -Dx11-backend=false -Dwayland-backend=false -Dbroadway-backend=false -Dmacos-backend=true \
    -Dmedia-gstreamer=disabled -Dprint-cpdb=disabled -Dprint-cups=disabled -Dvulkan=disabled \
    -Dcloudproviders=disabled -Dsysprof=disabled -Dtracker=disabled -Dcolord=disabled -Daccesskit=disabled \
    -Dintrospection=disabled -Ddocumentation=false -Dscreenshots=false -Dman-pages=false \
    -Dbuild-demos=false -Dbuild-testsuite=false -Dbuild-examples=false -Dbuild-tests=false >/dev/null
ninja -C build gtk/libgtk-4.1.dylib >/dev/null

lib=$runtime/lib/libgtk-4.1.dylib
target=$(readlink -f "$lib" 2>/dev/null || echo "$lib")
rm -f "$lib"
cp build/gtk/libgtk-4.1.dylib "$lib"
if [[ $target != "$lib" ]]; then rm -f "$target"; fi
args=(-id "$lib")
while read -r ref; do args+=(-change "$ref" "$runtime${ref#/opt/local}"); done < <(otool -L "$lib" | tail -n +2 | awk '{print $1}' | grep '^/opt/local/')
while read -r old; do args+=(-delete_rpath "$old"); done < <(otool -l "$lib" | awk '/cmd LC_RPATH/{getline; getline; print $2}' | grep '^/')
install_name_tool "${args[@]}" "$lib" 2>/dev/null
codesign --force --sign - "$lib" 2>/dev/null
echo "GTK $version (macOS backend) for macOS $(otool -l "$lib" | awk '/LC_BUILD_VERSION/{f=1} f&&/minos/{print $2; exit}') in $runtime/lib"
