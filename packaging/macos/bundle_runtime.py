#!/usr/bin/env python3
"""Bundles the launcher's runtime into the app, so it runs without Homebrew: Python (framework),
PyGObject, GTK 4 + libadwaita with their typelibs and data, and bash 5 for run.sh.

Every Homebrew dylib any of them loads is copied into Contents/Frameworks/lib, its install name
becomes @rpath/<name>, every reference to it is rewritten to match, and each Mach-O gets an
@loader_path rpath to that folder. Everything changed is signed again (ad hoc unless
--identity names a Developer ID): Apple Silicon refuses to load unsigned code.

usage: [BB_RUNTIME_PREFIX=<prefix>] bundle_runtime.py <path to .app> [--identity "Developer ID Application: ..."]
"""
import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

# The Homebrew prefix to bundle from: BB_RUNTIME_PREFIX names one with bottles for the oldest macOS
# the app supports (fetch_runtime.py); the build Mac's own Homebrew only suits its own macOS.
BREW = Path(os.environ.get("BB_RUNTIME_PREFIX") or "/opt/homebrew").resolve()
# The Python to bundle: Homebrew's python@3.15 by default; a MacPorts prefix (fetch_macports.py)
# names its own (BB_PY_VER=3.13, BB_PY_FRAMEWORK=<prefix>/Library/Frameworks/Python.framework),
# whose PyGObject and pycairo sit in the framework's own site-packages.
PY_VER = os.environ.get("BB_PY_VER") or "3.15"
PY_FRAMEWORK = Path(os.environ.get("BB_PY_FRAMEWORK") or BREW / f"opt/python@{PY_VER}/Frameworks/Python.framework")
PY_SITE = (PY_FRAMEWORK / "Versions" / PY_VER / "lib" / f"python{PY_VER}" / "site-packages"
           if os.environ.get("BB_PY_FRAMEWORK") else BREW / "lib" / f"python{PY_VER}" / "site-packages")
APP_EXE = "CTR-Online on Mac"  # the bundled Python.app's executable (launch.sh starts it)
GI_TYPELIBS = ["Adw-1", "cairo-1.0", "freetype2-2.0", "Gdk-4.0", "GdkMacos-4.0", "GdkPixbuf-2.0",
               "Gio-2.0", "GioUnix-2.0", "GIRepository-3.0", "GLib-2.0", "GLibUnix-2.0", "GModule-2.0",
               "GObject-2.0", "Graphene-1.0", "Gsk-4.0", "Gtk-4.0", "HarfBuzz-0.0", "Pango-1.0",
               "PangoCairo-1.0", "fontconfig-2.0"]
STDLIB_DROP = ["test", "idlelib", "tkinter", "turtledemo", "ensurepip", "lib2to3", "pydoc_data",
               f"config-{PY_VER}-darwin", "__phello__"]


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def is_macho(path):
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
    except OSError:
        return False
    return magic in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf")


def deps(path):
    lines = run("otool", "-L", str(path)).splitlines()[1:]
    return [line.strip().split(" (")[0] for line in lines]


def brew_target(ref, loader):
    """The Homebrew file a reference names, or None (system libraries stay as they are)."""
    if ref.startswith("@loader_path/"):
        hit = (Path(loader).parent / ref[len("@loader_path/"):])
        return hit.resolve() if hit.exists() and str(hit.resolve()).startswith(str(BREW)) else None
    if ref.startswith("@rpath/"):
        name = ref[len("@rpath/"):]
        # Beside the library that asks, in Homebrew's lib, or in a keg-only formula (openssl).
        loader_dir = Path(loader).resolve().parent
        for hit in [loader_dir / name, BREW / "lib" / name, *sorted(BREW.glob(f"opt/*/lib/{name}"))]:
            if hit.exists() and str(hit.resolve()).startswith(str(BREW)):
                return hit.resolve()
        return None
    if ref.startswith(str(BREW)):
        p = Path(ref)
        return p.resolve() if p.exists() else None
    return None


class Bundler:
    def __init__(self, app, identity):
        self.app = Path(app)
        self.identity = identity or "-"
        self.contents = self.app / "Contents"
        self.lib = self.contents / "Frameworks" / "lib"
        self.lib.mkdir(parents=True, exist_ok=True)
        self.copied = {}   # brew real path -> bundled file name
        self.machos = []   # every Mach-O to rewrite and sign

    def add_lib(self, real):
        real = Path(real).resolve()
        if real in self.copied:
            return self.copied[real]
        target = self.lib / real.name
        if not target.exists():
            shutil.copy2(real, target)
            target.chmod(0o755)
        self.copied[real] = real.name
        self.machos.append(target)
        for ref in deps(real):
            dep = brew_target(ref, real)
            if dep:
                self.add_lib(dep)
        return real.name

    def scan(self, path):
        """A Mach-O in the bundle: its Homebrew dependencies come along."""
        self.machos.append(Path(path))
        for ref in deps(path):
            dep = brew_target(ref, path)
            if dep:
                self.add_lib(dep)

    def rewrite_all(self):
        for macho in dict.fromkeys(self.machos):
            args = []
            if macho.parent == self.lib:
                args += ["-id", f"@rpath/{macho.name}"]
            for ref in deps(macho):
                dep = brew_target(ref, macho)
                if dep and dep in self.copied:
                    args += ["-change", ref, f"@rpath/{self.copied[dep]}"]
            rel = os.path.relpath(self.lib, macho.parent)
            rpath = "@loader_path" if rel == "." else f"@loader_path/{rel}"
            load_commands = run("otool", "-l", str(macho))
            # Absolute rpaths (Homebrew's, a build folder's) come first in the search: @rpath/libssl
            # would load the build Mac's copy, which no other Mac has.
            for old in re.findall(r"cmd LC_RPATH\n\s+cmdsize \d+\n\s+path (\S+)", load_commands):
                if old.startswith("/"):
                    args += ["-delete_rpath", old]
            if rpath not in load_commands:
                args += ["-add_rpath", rpath]
            if args:
                subprocess.run(["install_name_tool", *args, str(macho)], check=True, capture_output=True)

    def sign_all(self):
        for macho in dict.fromkeys(self.machos):
            args = ["codesign", "--force", "--sign", self.identity]
            if self.identity != "-":
                # Developer ID: hardened runtime with the port's exceptions and a secure timestamp
                # (notarization needs both).
                args += ["--options", "runtime", "--timestamp",
                         "--entitlements", str(Path(__file__).with_name("entitlements.plist"))]
            else:
                args += ["--timestamp=none"]
            subprocess.run([*args, str(macho)], check=True, capture_output=True)


def copy_python(b):
    dest = b.contents / "Frameworks" / "Python.framework"
    if dest.exists():
        shutil.rmtree(dest)
    vdir = dest / "Versions" / PY_VER
    shutil.copytree((PY_FRAMEWORK / "Versions" / PY_VER).resolve(), vdir, symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "Headers", "include", "share", "bin"))
    stdlib = vdir / "lib" / f"python{PY_VER}"
    for name in STDLIB_DROP:
        shutil.rmtree(stdlib / name, ignore_errors=True)
    site = stdlib / "site-packages"
    if site.is_symlink() or site.is_file():
        site.unlink()
    shutil.rmtree(site, ignore_errors=True)
    site.mkdir()
    for pkg in ("gi", "cairo"):
        shutil.copytree(PY_SITE / pkg, site / pkg, ignore=shutil.ignore_patterns("__pycache__"))
    (dest / "Versions" / "Current").symlink_to(PY_VER)
    fw_lib = vdir / "Python"
    subprocess.run(["install_name_tool", "-id", f"@rpath/Python.framework/Versions/{PY_VER}/Python",
                    str(fw_lib)], check=True, capture_output=True)
    # The interpreter as "CTR-Online on Mac": macOS names the process (Dock, Activity Monitor,
    # menu bar) after the executable's file, whatever the bundle's name says.
    py_exe = vdir / "Resources" / "Python.app" / "Contents" / "MacOS" / "Python"
    interp = py_exe.with_name(APP_EXE)
    py_exe.rename(interp)
    subprocess.run(["/usr/libexec/PlistBuddy", "-c", f"Set :CFBundleExecutable {APP_EXE}",
                    str(vdir / "Resources" / "Python.app" / "Contents" / "Info.plist")], check=True, capture_output=True)
    # The launcher runs as this Python.app: the menu bar and the Dock show its name and icon.
    py_app = vdir / "Resources" / "Python.app" / "Contents"
    for key, value in (("CFBundleName", "CTR-Online on Mac"), ("CFBundleDisplayName", "CTR-Online on Mac"),
                       ("CFBundleIconFile", "CTR-Online"), ("CFBundleIdentifier", "id.momochan32.ctr-online.launcher")):
        subprocess.run(["/usr/libexec/PlistBuddy", "-c", f"Delete :{key}", str(py_app / "Info.plist")],
                       capture_output=True)
        subprocess.run(["/usr/libexec/PlistBuddy", "-c", f"Add :{key} string {value}", str(py_app / "Info.plist")],
                       check=True, capture_output=True)
    shutil.copy2(Path(__file__).with_name("CTR-Online.icns"), py_app / "Resources" / "CTR-Online.icns")
    # The Dock names an app by its folder ("Python") unless the bundle declares a localized display
    # name: the launcher and the game it starts both run as this Python.app.
    subprocess.run(["/usr/libexec/PlistBuddy", "-c", "Delete :LSHasLocalizedDisplayName", str(py_app / "Info.plist")],
                   capture_output=True)
    subprocess.run(["/usr/libexec/PlistBuddy", "-c", "Add :LSHasLocalizedDisplayName bool true",
                    str(py_app / "Info.plist")], check=True, capture_output=True)
    for lang in ("en", "id"):
        lproj = py_app / "Resources" / f"{lang}.lproj"
        lproj.mkdir(parents=True, exist_ok=True)
        (lproj / "InfoPlist.strings").write_text(
            '"CFBundleName" = "CTR-Online on Mac";\n"CFBundleDisplayName" = "CTR-Online on Mac";\n',
            encoding="utf-8")
    for exe in (interp,):
        for ref in deps(exe):
            if ref.endswith(f"Python.framework/Versions/{PY_VER}/Python"):
                rel = os.path.relpath(fw_lib, exe.parent)
                subprocess.run(["install_name_tool", "-change", ref, f"@loader_path/{rel}", str(exe)],
                               check=True, capture_output=True)
        b.scan(exe)
    for path in vdir.rglob("*"):
        if path.is_file() and not path.is_symlink() and path.suffix in (".so", ".dylib") and is_macho(path):
            b.scan(path)
    b.scan(fw_lib)
    return interp


def copy_gtk_data(b):
    res = b.contents / "Resources"
    typelibs = res / "girepository-1.0"
    typelibs.mkdir(parents=True, exist_ok=True)
    for name in GI_TYPELIBS:
        src = (BREW / "lib" / "girepository-1.0" / f"{name}.typelib").resolve()
        if not src.exists():
            print(f"no {name}.typelib in {BREW}: skipped")
            continue
        shutil.copy2(src, typelibs / src.name)
        # The libraries a typelib names are opened by name (dlopen): they must be bundled.
        for lib in set(re.findall(rb"[A-Za-z0-9_.+-]+\.dylib", src.read_bytes())):
            hit = BREW / "lib" / lib.decode()
            if hit.exists():
                b.add_lib(hit.resolve())
    loaders_src = BREW / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders"
    loaders = b.contents / "Frameworks" / "gdk-pixbuf" / "loaders"
    loaders.mkdir(parents=True, exist_ok=True)
    for f in loaders_src.iterdir():
        if f.suffix == ".so" and is_macho(f.resolve()):
            shutil.copy2(f.resolve(), loaders / f.name)
            b.scan(loaders / f.name)
    share = res / "share"
    (share / "glib-2.0").mkdir(parents=True, exist_ok=True)
    shutil.copytree(BREW / "share" / "glib-2.0" / "schemas", share / "glib-2.0" / "schemas",
                    dirs_exist_ok=True)
    subprocess.run([str(BREW / "bin" / "glib-compile-schemas"), str(share / "glib-2.0" / "schemas")],
                   check=True)
    for theme in ("Adwaita", "hicolor"):
        src = BREW / "share" / "icons" / theme
        if src.exists():
            shutil.copytree(src, share / "icons" / theme, symlinks=False, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("cursors", "legacy"))


def copy_bash(b):
    bin_dir = b.contents / "Resources" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    bash = bin_dir / "bash"
    shutil.copy2((BREW / "bin" / "bash").resolve(), bash)
    bash.chmod(0o755)
    b.scan(bash)
    # run.sh and its scripts call python3: the bundled interpreter.
    python3 = bin_dir / "python3"
    if python3.exists() or python3.is_symlink():
        python3.unlink()
    python3.symlink_to(f"../../Frameworks/Python.framework/Versions/{PY_VER}/Resources/Python.app/Contents/MacOS/{APP_EXE}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app")
    parser.add_argument("--identity", default="")
    args = parser.parse_args()
    b = Bundler(args.app, args.identity)
    copy_python(b)
    copy_gtk_data(b)
    copy_bash(b)
    b.rewrite_all()
    b.sign_all()
    # The image loaders' cache, with the bundle's loader folder as a placeholder (launch.sh fills it).
    # Absolute: the tool prints absolute paths, and all of the folder must become the placeholder.
    loaders = (b.contents / "Frameworks" / "gdk-pixbuf" / "loaders").resolve()
    cache = run(str(BREW / "bin" / "gdk-pixbuf-query-loaders"), *sorted(str(p) for p in loaders.glob("*.so")))
    (b.contents / "Resources" / "gdk-pixbuf-loaders.cache.in").write_text(cache.replace(str(loaders), "@APP_LOADERS@"))
    print(f"Bundled {len(b.copied)} libraries; {len(set(b.machos))} Mach-O files signed "
          f"({'ad hoc' if b.identity == '-' else b.identity})")


if __name__ == "__main__":
    main()
