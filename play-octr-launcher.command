#!/bin/zsh
# SacredFire launcher (GTK4) on macOS: settings, online, mods; starts the macOS build.
cd "$(dirname "$0")"
export BB_GUEST_GPU_MEMORY=${BB_GUEST_GPU_MEMORY:-1}
export BB_GAME_DIR=${BB_GAME_DIR:-$HOME/Downloads/ctr-extract/CTR_ANDROID_PRONTO/CUSA13795-1.21}
export BB_PROBE=$PWD/out/gpu-mac/sacredfire ROSETTA_ADVERTISE_AVX=1
export BB_TIMEOUT=${BB_TIMEOUT:-0}
export VK_ICD_FILENAMES=$PWD/out/gpu-mac/kosmickrisp_mesa_icd.json
export PATH=/opt/homebrew/bin:$PATH
exec /opt/homebrew/bin/python3 launcher/sacredfire_launcher.py "$@"
