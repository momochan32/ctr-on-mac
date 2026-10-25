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
# BB_GPU_DIR: the game's build (deployment target 15.0); BB_VULKAN_LOADER: a loader built for
# macOS 15; the drivers: KosmicKrisp (macOS 26+, from the shadPS4 build) and MoltenVK (macOS 15).
gpu=${BB_GPU_DIR:-out/gpu-mvk}
kosmickrisp=${BB_KOSMICKRISP_DIR:-out/gpu-mac}
moltenvk=${BB_MOLTENVK_DIR:-out/moltenvk-1.4.2/MoltenVK/MoltenVK/dynamic/dylib/macOS}
cp "$gpu/sacredfire" "$port/bin/CTR-Online"
cp packaging/macos/icon.png "$port/bin/icon.png"
cp "$gpu/bb-gpu-capabilities" "${BB_VULKAN_LOADER:-out/vulkan-loader-build/loader/libvulkan.1.dylib}" \
   "$kosmickrisp/libvulkan_kosmickrisp.dylib" "$kosmickrisp/kosmickrisp_mesa_icd.json" \
   "$moltenvk/libMoltenVK.dylib" "$moltenvk/MoltenVK_icd.json" "$port/bin/"
[[ -f out/aerolib.inl ]] && mkdir -p "$port/out" && cp out/aerolib.inl "$port/out/"
# The build's rpaths name folders on the build Mac: the bundled executables look beside themselves only.
for exe in "$port/bin/CTR-Online" "$port/bin/bb-gpu-capabilities"; do
    while read -r old; do
        install_name_tool -delete_rpath "$old" "$exe"
    done < <(otool -l "$exe" | awk '/cmd LC_RPATH/{getline; getline; print $2}' | grep -v '^@')
    otool -l "$exe" | grep -q 'path @executable_path ' || install_name_tool -add_rpath @executable_path "$exe"
done
# The launcher's runtime (Python, GTK 4, libadwaita, bash): no Homebrew needed on the player's Mac.
bundle_args=()
[[ -n ${BB_SIGN_IDENTITY:-} ]] && bundle_args=(--identity "$BB_SIGN_IDENTITY")
# From bottles for the oldest macOS the app supports (macOS 15, arm64_sequoia), not from this
# Mac's Homebrew, whose bottles only suit this Mac's own macOS.
min_macos=$(/usr/libexec/PlistBuddy -c "Print :LSMinimumSystemVersion" packaging/macos/Info.plist)
runtime=out/runtime-sequoia
[[ -d $runtime/opt/python@3.15 ]] || /opt/homebrew/bin/python3 packaging/macos/fetch_runtime.py "$runtime" --tag arm64_sequoia
BB_RUNTIME_PREFIX=$runtime /opt/homebrew/bin/python3 packaging/macos/bundle_runtime.py "$app" "${bundle_args[@]}"
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
           "$port/bin/libvulkan_kosmickrisp.dylib" "$port/bin/libMoltenVK.dylib" "$app/Contents/MacOS/CTR-Online"; do
    codesign "${sign_args[@]}" "$exe"
done
# Nested bundles are signed from the inside out: Python.app, then Python.framework, then the app.
py_fw="$app/Contents/Frameworks/Python.framework"
codesign "${sign_args[@]}" "$py_fw/Versions/3.15/Resources/Python.app"
codesign "${sign_args[@]}" "$py_fw/Versions/3.15"
codesign "${sign_args[@]}" "$app"
codesign --verify --deep --strict "$app" && echo "Signed: ${BB_SIGN_IDENTITY:-ad hoc}"
# Every executable must start on the oldest macOS the app claims: one built for a newer macOS stops the build.
too_new=$(find "$app" -type f -print0 | while IFS= read -r -d '' f; do
    # KosmicKrisp is only loaded on macOS 26 and later (launcher: mac_vulkan_driver).
    [[ $f == */libvulkan_kosmickrisp.dylib ]] && continue
    minos=$(otool -l "$f" 2>/dev/null | awk '/LC_BUILD_VERSION/{f=1} f&&/minos/{print $2; exit}')
    [[ -n $minos ]] && [[ $(printf '%s\n%s\n' "$min_macos" "$minos" | sort -V | tail -1) != "$min_macos" ]] &&
        echo "  needs macOS $minos: ${f#$app/}"
    true
done)
if [[ -n $too_new ]]; then echo "Built for a macOS newer than $min_macos:"; echo "$too_new" | head -20; exit 1; fi
echo "Every executable runs on macOS $min_macos"
ln -s /Applications "$stage/Applications"
rm -f "out/$name.dmg"
hdiutil create -volname "$name" -srcfolder "$stage" -ov -format UDZO "out/$name.dmg" >/dev/null
if [[ -n ${BB_SIGN_IDENTITY:-} ]]; then codesign --force --sign "$BB_SIGN_IDENTITY" --timestamp "out/$name.dmg"; fi
if [[ -n ${BB_NOTARY_PROFILE:-} ]]; then
    xcrun notarytool submit "out/$name.dmg" --keychain-profile "$BB_NOTARY_PROFILE" --wait
    xcrun stapler staple "out/$name.dmg"
fi
echo "Built out/$name.dmg ($(du -h "out/$name.dmg" | cut -f1))"
