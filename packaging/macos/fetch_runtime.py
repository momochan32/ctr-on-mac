#!/usr/bin/env python3
"""A Homebrew prefix with the launcher's runtime built for an older macOS, for bundle_runtime.py.

The Homebrew installed on the build Mac has bottles built for that Mac's own macOS: bundled as
they are, the app would only start there and later. This fetches the bottles of another macOS
(arm64_tahoe: macOS 26, the oldest KosmicKrisp runs on) for the launcher's formulae and their
dependencies, unpacks them into <prefix>/Cellar, links them into <prefix>/{lib,bin,share,opt} as
`brew link` does, and fills in the paths Homebrew leaves as placeholders in a bottle.

usage: fetch_runtime.py <prefix> [--tag arm64_tahoe]
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ROOTS = ["python@3.15", "gtk4", "libadwaita", "pygobject3", "py3cairo", "bash", "librsvg", "gdk-pixbuf",
         "glib", "adwaita-icon-theme", "hicolor-icon-theme"]
LINKED = ("lib", "bin", "share")


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def formulae():
    deps = run("brew", "deps", "--union", *ROOTS).split()
    return sorted(set(ROOTS + deps))


def bottle(name, tag, cache):
    """The bottle of name for tag (or the one for all systems), as the formulae API lists it:
    downloaded into cache once and checked against its SHA-256. The local brew may not know a
    tag the API has."""
    with urllib.request.urlopen(f"https://formulae.brew.sh/api/formula/{name}.json", timeout=30) as reply:
        files = json.load(reply)["bottle"]["stable"]["files"]
    entry = files.get(tag) or files.get("all")
    if not entry:
        raise SystemExit(f"{name}: no bottle for {tag}")
    path = cache / f"{name}--{tag}--{entry['sha256'][:16]}.tar.gz"
    if not path.exists():
        # ghcr.io serves Homebrew's public bottles with this anonymous token.
        request = urllib.request.Request(entry["url"], headers={"Authorization": "Bearer QQ=="})
        with urllib.request.urlopen(request, timeout=120) as reply, open(path.with_suffix(".part"), "wb") as out:
            shutil.copyfileobj(reply, out)
        path.with_suffix(".part").rename(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        path.unlink()
        raise SystemExit(f"{name}: the bottle's SHA-256 does not match")
    return path


def link_tree(src, dst):
    """Symlinks every file of src into dst, keeping the folders real (brew link)."""
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for f in files:
            target = dst / rel / f
            if not target.exists() and not target.is_symlink():
                target.symlink_to(Path(root) / f)


def is_macho(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe")
    except OSError:
        return False


def relocate(prefix):
    """Fills in @@HOMEBREW_PREFIX@@ / @@HOMEBREW_CELLAR@@ in every Mach-O's install names and rpaths
    and in text files, then signs the Mach-Os again (ad hoc: the bundler signs the app's copies)."""
    cellar = prefix / "Cellar"
    places = {"@@HOMEBREW_PREFIX@@": str(prefix), "@@HOMEBREW_CELLAR@@": str(cellar),
              "@@HOMEBREW_LIBRARY@@": str(prefix / "Library")}
    # Text files (pkg-config, Python's build settings) only record where things were built: they
    # get Homebrew's usual prefix, so no path of the build Mac ends up in the app.
    usual = {"@@HOMEBREW_PREFIX@@": "/opt/homebrew", "@@HOMEBREW_CELLAR@@": "/opt/homebrew/Cellar",
             "@@HOMEBREW_LIBRARY@@": "/opt/homebrew/Library"}

    def fill(text, values=places):
        for key, value in values.items():
            text = text.replace(key, value)
        return text

    for path in cellar.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        if is_macho(path):
            try:
                load = run("otool", "-l", str(path))
            except subprocess.CalledProcessError:
                continue  # a Java class starts with the same magic as a universal binary
            ident = run("otool", "-D", str(path)).splitlines()[1:]
            if "@@HOMEBREW_" not in load:
                continue
            args = []
            if ident and "@@HOMEBREW_" in ident[0]:
                args += ["-id", fill(ident[0].strip())]
            for line in run("otool", "-L", str(path)).splitlines()[1:]:
                ref = line.strip().split(" (")[0]
                if "@@HOMEBREW_" in ref:
                    args += ["-change", ref, fill(ref)]
            for line in load.splitlines():
                line = line.strip()
                if line.startswith("path @@HOMEBREW_"):
                    old = line.split()[1]
                    args += ["-rpath", old, fill(old)]
            path.chmod(path.stat().st_mode | 0o200)
            subprocess.run(["install_name_tool", *args, str(path)], check=True, capture_output=True)
            subprocess.run(["codesign", "--force", "--sign", "-", str(path)], check=True, capture_output=True)
        else:
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if b"@@HOMEBREW_" in data and b"\0" not in data[:8192]:
                path.chmod(path.stat().st_mode | 0o200)
                path.write_text(fill(data.decode("utf-8", errors="surrogateescape"), usual),
                                encoding="utf-8", errors="surrogateescape")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix")
    parser.add_argument("--tag", default="arm64_tahoe")
    args = parser.parse_args()
    prefix = Path(args.prefix).resolve()
    shutil.rmtree(prefix, ignore_errors=True)
    (prefix / "Cellar").mkdir(parents=True)
    (prefix / "opt").mkdir()
    names = formulae()
    cache = prefix.parent / f"bottles-{args.tag}"
    cache.mkdir(exist_ok=True)
    for name in names:
        with tarfile.open(bottle(name, args.tag, cache)) as tar:
            tar.extractall(prefix / "Cellar", filter="tar")
    relocate(prefix)
    for keg_dir in (prefix / "Cellar").iterdir():
        keg = next(keg_dir.iterdir())  # Cellar/<name>/<version>
        (prefix / "opt" / keg_dir.name).symlink_to(keg)
        for sub in LINKED:
            if (keg / sub).is_dir():
                link_tree(keg / sub, prefix / sub)
    print(f"{len(names)} formulae for {args.tag} in {prefix}")


if __name__ == "__main__":
    main()
