#!/bin/bash
# libappstream for a MacPorts runtime (fetch_macports.py): libadwaita links it, and MacPorts has
# no binary archive of it. Built from the AppStream release MacPorts packages, for macOS 13,
# against the runtime's own libraries (headers from the same archives), library only (no data,
# docs, tools, GIR), then installed into the runtime with its paths pointing there.
#
# usage: packaging/macos/build_appstream.sh <runtime prefix>   (needs ninja, pkgconf; meson is
# installed into a virtualenv under out/)
set -euo pipefail
runtime=$(cd "$1" && pwd)
version=1.2.0
out=$(cd "$(dirname "$0")/../.." && pwd)/out
dev=$out/macports13-dev        # the same archives with headers, only to build against
work=$out/appstream-$version
archives=$runtime/../macports-darwin22

python3 - "$archives" "$dev" <<'EOF'
import sys, tarfile, pathlib
cache, dev = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
dev.mkdir(exist_ok=True)
for archive in sorted(cache.glob("*.tbz2")):
    with tarfile.open(archive) as tar:
        for m in tar.getmembers():
            name = m.name.lstrip("./")
            if not name.startswith("opt/local/") or "/share/man/" in name:
                continue
            m.name = name[len("opt/local/"):]
            if m.islnk():
                target = m.linkname.lstrip("./")
                m.linkname = target[len("opt/local/"):] if target.startswith("opt/local/") else target
            try:
                tar.extract(m, dev, filter="tar")
            except Exception:
                pass
EOF
# MacPorts' glib headers name /opt/local; its code generators only run from /opt/local: the
# build uses Homebrew's (same output).
grep -rl "/opt/local/include" "$dev/include" | while read -r f; do chmod u+w "$f"; sed -i '' "s#/opt/local/include#$dev/include#g" "$f"; done
for tool in glib-mkenums glib-compile-resources glib-genmarshal; do ln -sf "/opt/homebrew/bin/$tool" "$dev/bin/$tool"; done

[[ -x $out/mesonenv/bin/meson ]] || { python3 -m venv "$out/mesonenv" && "$out/mesonenv/bin/pip" -q install meson; }
if [[ ! -d $work ]]; then
    curl -fsSL "https://github.com/ximion/appstream/archive/refs/tags/v$version.tar.gz" | tar -xz -C "$out"
    # data/ needs itstool (translated metainfo) and docs/, tests/, contrib/ are not used.
    sed -i '' -e "s#^subdir('data/')#\#subdir('data/')#" -e "s#^subdir('docs/')#\#subdir('docs/')#" \
        -e "s#^subdir('tests/')#\#subdir('tests/')#" -e "s#^subdir('contrib/')#\#subdir('contrib/')#" "$work/meson.build"
fi
printf '#!/bin/sh\nexec /opt/homebrew/bin/pkgconf --define-prefix "$@"\n' > "$out/pkgconf-define-prefix"
chmod +x "$out/pkgconf-define-prefix"
export PKG_CONFIG=$out/pkgconf-define-prefix PKG_CONFIG_PATH=$dev/lib/pkgconfig:$dev/share/pkgconfig
export PATH=$out/mesonenv/bin:/opt/homebrew/bin:/usr/bin:/bin:$dev/bin MACOSX_DEPLOYMENT_TARGET=13.0
cd "$work"
[[ -d build ]] || meson setup build --prefix=/opt/local --buildtype=release \
    -Dc_args="-I$dev/include -mmacosx-version-min=13.0" -Dc_link_args="-L$dev/lib -mmacosx-version-min=13.0" \
    -Dstemming=false -Dsystemd=false -Dvapi=false -Dgir=false -Dtools=false -Ddocs=false -Dapidocs=false \
    -Dinstall-docs=false -Dman=false -Dcompose=false -Dapt-support=false -Dbash-completion=false \
    -Dzstd-support=true -Dqt=false >/dev/null
ninja -C build >/dev/null

lib=$runtime/lib/libappstream.5.dylib
cp build/src/libappstream.5.dylib "$lib"
args=(-id "$lib")
while read -r ref; do args+=(-change "$ref" "$runtime${ref#/opt/local}"); done < <(otool -L "$lib" | tail -n +2 | awk '{print $1}' | grep '^/opt/local/')
# The build folder's rpaths (meson's) would make @rpath look there first.
while read -r old; do args+=(-delete_rpath "$old"); done < <(otool -l "$lib" | awk '/cmd LC_RPATH/{getline; getline; print $2}' | grep '^/')
install_name_tool "${args[@]}" "$lib" 2>/dev/null
codesign --force --sign - "$lib" 2>/dev/null
echo "libappstream $version for macOS $(otool -l "$lib" | awk '/LC_BUILD_VERSION/{f=1} f&&/minos/{print $2; exit}') in $runtime/lib"
