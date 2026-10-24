#!/bin/zsh
# CTR-Online on Mac (By Momochan32): the app's entry point. The port lives in Resources/port
# (read-only); settings, saves and generated files in ~/Library/Application Support/CTR-Online.
here=${0:A:h}
port="$here/../Resources/port"
export BB_DATA_DIR="$HOME/Library/Application Support/CTR-Online"
export PATH=/opt/homebrew/bin:/usr/bin:/bin
mkdir -p "$BB_DATA_DIR"
missing=()
[[ -x /opt/homebrew/bin/bash ]] || missing+=(bash)
/opt/homebrew/bin/python3 -c 'import gi; gi.require_version("Gtk","4.0"); gi.require_version("Adw","1")' 2>/dev/null ||
    missing+=(python gtk4 libadwaita pygobject3 adwaita-icon-theme)
/usr/bin/pgrep -q oahd || missing+=(rosetta)
if (( ${#missing} )); then
    cmd="brew install bash python gtk4 libadwaita pygobject3 adwaita-icon-theme"
    [[ ${missing[(r)rosetta]} == rosetta ]] && cmd="softwareupdate --install-rosetta --agree-to-license; $cmd"
    /usr/bin/osascript -e "display dialog \"CTR-Online on Mac needs a few free components first (Homebrew: brew.sh).\n\nOpen Terminal and run:\n\n$cmd\" buttons {\"OK\"} default button 1 with title \"CTR-Online on Mac\""
    exit 1
fi
# The import names list fetched from shadPS4 once, shipped so the first start works offline.
if [[ ! -f "$BB_DATA_DIR/out/aerolib.inl" && -f "$port/out/aerolib.inl" ]]; then
    mkdir -p "$BB_DATA_DIR/out" && cp "$port/out/aerolib.inl" "$BB_DATA_DIR/out/"
fi
cd "$port"
exec /opt/homebrew/bin/python3 launcher/sacredfire_launcher.py "$@"
