#!/bin/zsh
# CTR-Online on Mac (By Momochan32): the app's entry point. The port lives in Resources/port
# (read-only); settings, saves and generated files in ~/Library/Application Support/CTR-Online.
# The launcher's runtime (Python, GTK 4, libadwaita, bash 5) is bundled in the app
# (packaging/macos/bundle_runtime.py); a build without it falls back to Homebrew.
here=${0:A:h}                # Contents/Resources (run by the Contents/MacOS/CTR-Online stub)
contents=${here:h}
res="$contents/Resources"
port="$res/port"
export BB_DATA_DIR="$HOME/Library/Application Support/CTR-Online"
mkdir -p "$BB_DATA_DIR"
# HTTPS (update check, downloads): the bundled OpenSSL looks for MacPorts' certificates in
# /opt/local; macOS's own list is used instead (1.2.0 to 1.2.3 could not reach GitHub).
[[ -z ${SSL_CERT_FILE:-} && -f /etc/ssl/cert.pem ]] && export SSL_CERT_FILE=/etc/ssl/cert.pem

python=$(echo "$contents"/Frameworks/Python.framework/Versions/[0-9]*/Resources/Python.app/Contents/MacOS/"CTR-Online on Mac")
if [[ -x $python ]]; then
    export PATH="$res/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    export BB_BASH="$res/bin/bash"
    export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
    export GI_TYPELIB_PATH="$res/girepository-1.0"
    export DYLD_FALLBACK_LIBRARY_PATH="$contents/Frameworks/lib"
    export XDG_DATA_DIRS="$res/share"
    export GSETTINGS_SCHEMA_DIR="$res/share/glib-2.0/schemas"
    # The image loaders' cache names their paths: written for wherever the app is.
    cache="$BB_DATA_DIR/gdk-pixbuf-loaders.cache"
    sed "s|@APP_LOADERS@|$contents/Frameworks/gdk-pixbuf/loaders|g" \
        "$res/gdk-pixbuf-loaders.cache.in" > "$cache" 2>/dev/null
    export GDK_PIXBUF_MODULE_FILE="$cache"
else
    export PATH=/opt/homebrew/bin:/usr/bin:/bin
    export BB_BASH=/opt/homebrew/bin/bash
    python=/opt/homebrew/bin/python3
    missing=()
    [[ -x /opt/homebrew/bin/bash ]] || missing+=(bash)
    $python -c 'import gi; gi.require_version("Gtk","4.0"); gi.require_version("Adw","1")' 2>/dev/null ||
        missing+=(gtk)
    if (( ${#missing} )); then
        /usr/bin/osascript -e 'display dialog "This build of CTR-Online on Mac needs Homebrew packages:\n\nbrew install bash python gtk4 libadwaita pygobject3 adwaita-icon-theme" buttons {"OK"} default button 1 with title "CTR-Online on Mac"'
        exit 1
    fi
fi
# Apple Silicon (also when this runs under Rosetta): the game is Intel code, run by Rosetta 2.
apple_silicon=$( [[ $(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null) == 1 ]] && echo 1 )
if [[ -n $apple_silicon && ! -f "$port/bin/kosmickrisp_mesa_icd.json" ]]; then
    # The Intel app (no KosmicKrisp) on an Apple Silicon Mac.
    /usr/bin/osascript -e 'display dialog "This is the Intel version of CTR-Online on Mac.\n\nOn a Mac with Apple Silicon (M1 or newer), download CTR-Online-on-Mac.dmg from the releases page instead." buttons {"OK"} default button 1 with title "CTR-Online on Mac"'
    exit 1
fi
if [[ -n $apple_silicon ]] && ! /usr/bin/pgrep -q oahd; then
    /usr/bin/osascript -e 'display dialog "CTR-Online on Mac needs Rosetta 2 (the game runs as Intel code).\n\nOpen Terminal and run:\nsoftwareupdate --install-rosetta --agree-to-license" buttons {"OK"} default button 1 with title "CTR-Online on Mac"'
    exit 1
fi
# The import names list fetched from shadPS4 once, shipped so the first start works offline.
if [[ ! -f "$BB_DATA_DIR/out/aerolib.inl" && -f "$port/out/aerolib.inl" ]]; then
    mkdir -p "$BB_DATA_DIR/out" && cp "$port/out/aerolib.inl" "$BB_DATA_DIR/out/"
fi
cd "$port"
exec "$python" launcher/sacredfire_launcher.py "$@"
