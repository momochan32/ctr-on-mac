#!/usr/bin/env python3
"""The launcher's runtime from MacPorts' binary archives, for macOS versions Homebrew no longer
builds bottles for (fetch_runtime.py covers the three newest).

MacPorts archives each port per macOS release; the darwin_22 ones are built for macOS 13 and run
on every later macOS. This resolves the launcher's ports and their lib/run dependencies through
ports.macports.org, unpacks each port's archive for the chosen release into <prefix> (MacPorts'
/opt/local layout), points every Mach-O path inside /opt/local at <prefix> and signs it again (ad
hoc; the bundler signs the app's copies), and shortens the library paths in the typelibs to bare
names (the launcher finds them through DYLD_FALLBACK_LIBRARY_PATH, as with Homebrew's).

The result is read by bundle_runtime.py like a Homebrew prefix: BB_RUNTIME_PREFIX=<prefix>,
BB_PY_VER=3.13, BB_PY_FRAMEWORK=<prefix>/Library/Frameworks/Python.framework.

usage: fetch_macports.py <prefix> [--darwin 22] [--arch arm64|x86_64]
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

ROOTS = ["python313", "py313-gobject3", "py313-cairo", "gtk4", "libadwaita", "librsvg", "gdk-pixbuf2",
         "glib2", "adwaita-icon-theme", "hicolor-icon-theme", "bash"]
ORIGIN = "/opt/local"
API = "https://ports.macports.org/api/v1/ports/{}/"
PACKAGES = "https://packages.macports.org/{}/"


def fetch(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as reply:
        return reply.read()


def resolve(roots):
    """Every port the roots need at run time (lib and run dependencies), with its version."""
    found, todo = {}, list(roots)
    while todo:
        name = todo.pop()
        if name in found:
            continue
        try:
            info = json.loads(fetch(API.format(name)))
        except urllib.error.HTTPError:
            print(f"not in the ports API, skipped: {name}")
            continue
        found[name] = info
        for dep in info.get("dependencies") or []:
            if dep["type"] in ("lib", "run"):
                todo += [p.split(":")[-1] for p in dep["ports"] if p]
    return found


def archive_url(name, info, darwin, arch):
    """The archive of the port's current version for the release (or one for any release)."""
    try:
        listing = fetch(PACKAGES.format(name)).decode()
    except urllib.error.HTTPError:
        return None
    version = re.escape(info["version"])
    candidates = re.findall(rf'href="({re.escape(name)}-{version}_\d+[^"]*?\.darwin_(?:{darwin}\.{arch}|any\.noarch)\.tbz2)"',
                            listing)
    if not candidates:
        # The newest archive built for the release, when the current version has none yet.
        candidates = re.findall(rf'href="({re.escape(name)}-[^"]*?\.darwin_(?:{darwin}\.{arch}|any\.noarch)\.tbz2)"',
                                listing)
    if not candidates:
        return None
    candidates.sort(key=lambda n: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", n)])
    return PACKAGES.format(name) + candidates[-1]


def is_macho(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe")
    except OSError:
        return False


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def relocate(prefix):
    for path in prefix.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix == ".typelib":
            # "/opt/local/lib/libgobject-2.0.0.dylib,/opt/local/lib/libglib-2.0.0.dylib\0" ->
            # "libgobject-2.0.0.dylib,libglib-2.0.0.dylib\0" + padding: the offsets stay.
            data = path.read_bytes()

            def bare(m):
                text = m.group(0)[:-1].replace(b"/opt/local/lib/", b"")
                return text + b"\0" * (len(m.group(0)) - len(text))
            new = re.sub(rb"[^\0]*/opt/local/lib/[^\0]*\0", bare, data)
            if new != data:
                path.chmod(path.stat().st_mode | 0o200)
                path.write_bytes(new)
            continue
        if not is_macho(path):
            continue
        try:
            load = run("otool", "-l", str(path))
        except subprocess.CalledProcessError:
            continue
        if ORIGIN not in load:
            continue
        args = []
        ident = run("otool", "-D", str(path)).splitlines()[1:]
        if ident and ident[0].startswith(ORIGIN + "/"):
            args += ["-id", str(prefix) + ident[0][len(ORIGIN):]]
        for line in run("otool", "-L", str(path)).splitlines()[1:]:
            ref = line.strip().split(" (")[0]
            if ref.startswith(ORIGIN + "/"):
                args += ["-change", ref, str(prefix) + ref[len(ORIGIN):]]
        for line in load.splitlines():
            line = line.strip()
            if line.startswith("path " + ORIGIN):
                old = line.split()[1]
                args += ["-rpath", old, str(prefix) + old[len(ORIGIN):]]
        if args:
            path.chmod(path.stat().st_mode | 0o200)
            try:
                subprocess.run(["install_name_tool", *args, str(path)], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                # The longer paths do not fit its load commands (libgcc's, x86_64): its /opt/local
                # rpaths are dropped instead (the bundler drops absolute rpaths anyway).
                short = []
                i = 0
                while i < len(args):
                    if args[i] == "-rpath":
                        short += ["-delete_rpath", args[i + 1]]
                        i += 3
                    else:
                        short += args[i:i + (2 if args[i] == "-id" else 3)]
                        i += 2 if args[i] == "-id" else 3
                subprocess.run(["install_name_tool", *short, str(path)], check=True, capture_output=True)
            subprocess.run(["codesign", "--force", "--sign", "-", str(path)], check=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix")
    parser.add_argument("--darwin", default="22", help="22: macOS 13, 23: macOS 14")
    parser.add_argument("--arch", default="arm64", help="arm64 (Apple Silicon) or x86_64 (Intel)")
    args = parser.parse_args()
    prefix = Path(args.prefix).resolve()
    shutil.rmtree(prefix, ignore_errors=True)
    prefix.mkdir(parents=True)
    cache = prefix.parent / (f"macports-darwin{args.darwin}" + ("" if args.arch == "arm64" else f"-{args.arch}"))
    cache.mkdir(exist_ok=True)
    ports = resolve(ROOTS)
    missing = []
    for name, info in sorted(ports.items()):
        url = archive_url(name, info, args.darwin, args.arch)
        if not url:
            missing.append(name)
            continue
        local = cache / url.rsplit("/", 1)[1]
        if not local.exists():
            local.with_suffix(".part").write_bytes(fetch(url, timeout=300))
            local.with_suffix(".part").rename(local)
        with tarfile.open(local) as tar:
            members = []
            for m in tar.getmembers():
                name_in = m.name.lstrip("./")
                if not name_in.startswith("opt/local/"):
                    continue  # +CONTENTS, +DESC: MacPorts' own records
                m.name = name_in[len("opt/local/"):]
                if re.match(r"(share/(man|doc|info|gtk-doc|devhelp)|include)/|libexec/[^/]+/share/man/", m.name):
                    continue  # documentation and headers: not needed to run
                if m.issym() and m.linkname.startswith(ORIGIN + "/"):
                    m.linkname = str(prefix) + m.linkname[len(ORIGIN):]
                elif m.islnk():
                    target = m.linkname.lstrip("./")
                    m.linkname = target[len("opt/local/"):] if target.startswith("opt/local/") else target
                members.append(m)
            for m in members:
                try:
                    tar.extract(m, prefix, filter="tar")
                except (OSError, KeyError, tarfile.FilterError) as error:
                    print(f"{name}: {m.name} not unpacked ({error})")
    # The icon themes are data only: Homebrew's bottle for every system ("all") gives them.
    for theme in ("adwaita-icon-theme", "hicolor-icon-theme"):
        if theme in missing:
            files = json.loads(fetch(f"https://formulae.brew.sh/api/formula/{theme}.json"))["bottle"]["stable"]["files"]
            entry = files.get("all") or next(iter(files.values()))
            request = urllib.request.Request(entry["url"], headers={"Authorization": "Bearer QQ=="})
            local = cache / f"{theme}-{entry['sha256'][:16]}.bottle.tar.gz"
            if not local.exists():
                with urllib.request.urlopen(request, timeout=300) as reply:
                    local.write_bytes(reply.read())
            if hashlib.sha256(local.read_bytes()).hexdigest() != entry["sha256"]:
                raise SystemExit(f"{theme}: the bottle's SHA-256 does not match")
            with tarfile.open(local) as tar:
                for m in tar.getmembers():
                    parts = m.name.split("/", 2)  # <formula>/<version>/<path>
                    if len(parts) == 3 and parts[2].startswith("share/icons/"):
                        m.name = parts[2]
                        tar.extract(m, prefix, filter="tar")
            missing.remove(theme)
    relocate(prefix)
    print(f"{len(ports) - len(missing)} ports for darwin_{args.darwin} in {prefix}")
    if missing:
        print("no archive (built at install time by MacPorts, or not needed): " + ", ".join(missing))


if __name__ == "__main__":
    main()
