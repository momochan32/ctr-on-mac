#!/bin/zsh
# Builds "CTR-Online on Mac.dmg": the app (launcher, game executable, KosmicKrisp, scripts) with
# an Applications link to drag it onto. Run after `ninja -C out/gpu-mac sacredfire`.
set -euo pipefail
cd "${0:A:h}/../.."
name="CTR-Online on Mac"
stage=out/dmg
app="$stage/$name.app"
rm -rf "$stage" && mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources/port/bin"
port="$app/Contents/Resources/port"
cp packaging/macos/launch.sh "$app/Contents/MacOS/CTR-Online"
chmod +x "$app/Contents/MacOS/CTR-Online"
cp packaging/macos/Info.plist "$app/Contents/"
cp packaging/macos/CTR-Online.icns "$app/Contents/Resources/"
rsync -a --exclude __pycache__ run.sh run.py scripts tools patches shaders launcher "$port/"
rm -f "$port/patches/OCTR-Mod-Library.xml"
cp out/gpu-mac/sacredfire out/gpu-mac/bb-gpu-capabilities out/gpu-mac/libvulkan.1.dylib \
   out/gpu-mac/libvulkan_kosmickrisp.dylib out/gpu-mac/kosmickrisp_mesa_icd.json "$port/bin/"
[[ -f out/aerolib.inl ]] && mkdir -p "$port/out" && cp out/aerolib.inl "$port/out/"
printf '%s-macos\n' "$(git describe --tags --match 'v*' --always 2>/dev/null || echo dev)" > "$port/VERSION"
cp README.md README.id.md "$stage/"
mkdir -p "$stage/docs" && cp -R docs/macos "$stage/docs/"
ln -s /Applications "$stage/Applications"
rm -f "out/$name.dmg"
hdiutil create -volname "$name" -srcfolder "$stage" -ov -format UDZO "out/$name.dmg" >/dev/null
echo "Built out/$name.dmg ($(du -h "out/$name.dmg" | cut -f1))"
