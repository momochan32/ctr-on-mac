#!/bin/zsh
# SacredFire on macOS (development launcher).
cd "$(dirname "$0")"
export BB_GAME_DIR=${BB_GAME_DIR:-$HOME/Downloads/ctr-extract/CTR_ANDROID_PRONTO/CUSA13795-1.21}
export BB_PREBUILT=1 BB_PROBE=$PWD/out/gpu-mac/sacredfire ROSETTA_ADVERTISE_AVX=1
export BB_NO_MSAA=${BB_NO_MSAA:-1}
export VK_ICD_FILENAMES=$PWD/out/gpu-mac/kosmickrisp_mesa_icd.json BB_TIMEOUT=${BB_TIMEOUT:-0}
exec /opt/homebrew/bin/bash run.sh "$@"
