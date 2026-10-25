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
# The main executable: a small Mach-O that runs Resources/launch.sh (a signed binary, not a script).
clang -arch arm64 -O2 -mmacosx-version-min=14.0 -o "$app/Contents/MacOS/CTR-Online" packaging/macos/stub.c
cp packaging/macos/launch.sh "$app/Contents/Resources/launch.sh"
chmod +x "$app/Contents/Resources/launch.sh"
cp packaging/macos/Info.plist "$app/Contents/"
cp packaging/macos/CTR-Online.icns "$app/Contents/Resources/"
rsync -a --exclude __pycache__ run.sh run.py scripts tools patches shaders launcher "$port/"
rm -f "$port/patches/OCTR-Mod-Library.xml"
# The game executable as CTR-Online: the name macOS shows in the menu bar and the Dock.
cp out/gpu-mac/sacredfire "$port/bin/CTR-Online"
cp packaging/macos/icon.png "$port/bin/icon.png"
cp out/gpu-mac/bb-gpu-capabilities out/gpu-mac/libvulkan.1.dylib \
   out/gpu-mac/libvulkan_kosmickrisp.dylib out/gpu-mac/kosmickrisp_mesa_icd.json "$port/bin/"
[[ -f out/aerolib.inl ]] && mkdir -p "$port/out" && cp out/aerolib.inl "$port/out/"
# The launcher's runtime (Python, GTK 4, libadwaita, bash): no Homebrew needed on the player's Mac.
bundle_args=()
[[ -n ${BB_SIGN_IDENTITY:-} ]] && bundle_args=(--identity "$BB_SIGN_IDENTITY")
/opt/homebrew/bin/python3 packaging/macos/bundle_runtime.py "$app" "${bundle_args[@]}"
# The app's version (Info.plist): what the launcher compares with the latest GitHub release.
version=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" packaging/macos/Info.plist)
printf 'v%s-macos\n' "$version" > "$port/VERSION"
cp README.md README.id.md "$stage/"
mkdir -p "$stage/docs" && cp -R docs/macos "$stage/docs/"
# Signing: every executable of the port and then the app itself (BB_SIGN_IDENTITY: a Developer ID
# with hardened runtime; otherwise ad hoc). Notarization: BB_NOTARY_PROFILE (notarytool keychain profile).
sign_args=(--force --sign "${BB_SIGN_IDENTITY:--}")
[[ -n ${BB_SIGN_IDENTITY:-} ]] && sign_args+=(--options runtime --timestamp --entitlements packaging/macos/entitlements.plist)
for exe in "$port/bin/CTR-Online" "$port/bin/bb-gpu-capabilities" "$port/bin/libvulkan.1.dylib" \
           "$port/bin/libvulkan_kosmickrisp.dylib" "$app/Contents/MacOS/CTR-Online"; do
    codesign "${sign_args[@]}" "$exe"
done
# Nested bundles are signed from the inside out: Python.app, then Python.framework, then the app.
py_fw="$app/Contents/Frameworks/Python.framework"
codesign "${sign_args[@]}" "$py_fw/Versions/3.15/Resources/Python.app"
codesign "${sign_args[@]}" "$py_fw/Versions/3.15"
codesign "${sign_args[@]}" "$app"
codesign --verify --deep --strict "$app" && echo "Signed: ${BB_SIGN_IDENTITY:-ad hoc}"
ln -s /Applications "$stage/Applications"
rm -f "out/$name.dmg"
hdiutil create -volname "$name" -srcfolder "$stage" -ov -format UDZO "out/$name.dmg" >/dev/null
if [[ -n ${BB_SIGN_IDENTITY:-} ]]; then codesign --force --sign "$BB_SIGN_IDENTITY" --timestamp "out/$name.dmg"; fi
if [[ -n ${BB_NOTARY_PROFILE:-} ]]; then
    xcrun notarytool submit "out/$name.dmg" --keychain-profile "$BB_NOTARY_PROFILE" --wait
    xcrun stapler staple "out/$name.dmg"
fi
echo "Built out/$name.dmg ($(du -h "out/$name.dmg" | cut -f1))"
