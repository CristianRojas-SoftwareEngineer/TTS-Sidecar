#!/usr/bin/env python3
"""
Build script for macOS x64 and ARM64 apps using PyInstaller --onedir.
Produces a .app bundle (macOS application) inside the --onedir folder.

macOS uses afplay (built-in) for audio — no sounddevice or pycaw needed.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

sys.path.insert(0, str(Path(__file__).parent))
from build_utils import (
    log, StageTimer, BuildTimer, copy_license_files, get_version,
    check_pyinstaller, common_pyinstaller_args, bundle_size_mb,
    BUILD_SUBPROCESS_TIMEOUT, PYINSTALLER_TIMEOUT,
)


def check_dependencies():
    """Check required dependencies are installed."""
    check_pyinstaller()

    with StageTimer("CheckDeps", "Checking dependencies"):
        # create-dmg es un script de shell (Homebrew), no un paquete de
        # PyPI: se invoca como binario vía subprocess, no se importa como
        # módulo Python. `pip install create-dmg` fallaba siempre porque ese
        # paquete no existe en PyPI.
        if shutil.which("create-dmg"):
            log("create-dmg: installed")
        else:
            log("create-dmg not found (optional for .dmg generation) — instálalo con 'brew install create-dmg'")


def build_macos(target_arch="universal2"):
    """Build macOS .app bundle with PyInstaller --onedir."""
    arch_options = {"x86_64": "x86_64", "arm64": "arm64", "universal2": "universal2"}
    arch_flag = arch_options.get(target_arch, "universal2")

    with BuildTimer():
        with StageTimer("Setup", "Setting up build environment"):
            log(f"Platform: macOS {arch_flag}")
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            entry_point = PROJECT_ROOT / "bin" / "tts-sidecar"

        with StageTimer("PyInstaller", "Compiling with PyInstaller (9-15 min)"):
            # No sounddevice, no pycaw — afplay (built-in) es el player de macOS.
            pyinstaller_args = common_pyinstaller_args(
                entry_point, PROJECT_ROOT, DIST_DIR, BUILD_DIR,
                data_sep=":",
            )
            log(f"Running: pyinstaller {' '.join(pyinstaller_args[2:])}")
            try:
                returncode = subprocess.run(
                    pyinstaller_args,
                    timeout=PYINSTALLER_TIMEOUT,
                ).returncode
            except KeyboardInterrupt:
                log("\n[CANCEL] Build cancelled by user.")
                sys.exit(130)
            except subprocess.TimeoutExpired:
                log(f"\n[TIMEOUT] PyInstaller excedió {PYINSTALLER_TIMEOUT}s.")
                sys.exit(1)

        if returncode != 0:
            log("PyInstaller failed", returncode)
            sys.exit(1)

        onedir = DIST_DIR / "tts-sidecar"
        with StageTimer("Size", "Checking bundle size"):
            if onedir.exists():
                log(f"Bundle size: {bundle_size_mb(onedir):.1f} MB ({onedir})")

        with StageTimer("AppBundle", "Structuring as .app bundle"):
            # Convert: dist/tts-sidecar/ → dist/tts-sidecar.app/Contents/MacOS/
            app_bundle = DIST_DIR / f"tts-sidecar-{arch_flag}.app"
            macos_dir = app_bundle / "Contents" / "MacOS"
            macos_dir.mkdir(parents=True, exist_ok=True)

            if onedir.exists():
                # Move the executable and _internal/ into Contents/MacOS/
                for item in onedir.iterdir():
                    dest = macos_dir / item.name
                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()
                    shutil.move(str(item), str(dest))
                shutil.rmtree(onedir)

            # Write Info.plist
            info_plist = app_bundle / "Contents" / "Info.plist"
            version = get_version()
            info_plist.write_text(_info_plist_content(version), encoding="utf-8")

            # Empaqueta los avisos de licencia dentro de Contents/Resources
            copy_license_files(app_bundle / "Contents" / "Resources")
            log(f".app bundle: {app_bundle}")

        with StageTimer("DMG", "Creating .dmg"):
            dmg_path = DIST_DIR / f"tts-sidecar-{arch_flag}.dmg"

            # Staging del contenido del volumen: el .app + un script de post-instalación
            # que expone `tts-sidecar` en el PATH mediante un symlink en /usr/local/bin,
            # equivalente a lo que hacen el instalador de Windows y el AppImage de Linux.
            dmg_src = DIST_DIR / "dmg_src"
            if dmg_src.exists():
                shutil.rmtree(dmg_src)
            dmg_src.mkdir(parents=True)
            staged_app = dmg_src / app_bundle.name
            shutil.copytree(app_bundle, staged_app, symlinks=True)

            install_script = dmg_src / "Instalar en el PATH.command"
            install_script.write_text(_path_install_script(app_bundle.name), encoding="utf-8")
            os.chmod(install_script, 0o755)

            result = subprocess.run(
                [
                    "create-dmg",
                    "--volname", "tts-sidecar",
                    "--window-pos", "200", "120",
                    "--icon-size", "100",
                    "--icon", app_bundle.name, "150", "185",
                    "--hide-extension", app_bundle.name,
                    "--app-drop-link", "480", "185",
                    "--format", "ULFO",
                    str(dmg_path),
                    str(dmg_src),
                ],
                capture_output=True, text=True,
                timeout=BUILD_SUBPROCESS_TIMEOUT,
            )
            if result.returncode != 0:
                log("dmg creation failed (create-dmg may need brew install create-dmg)",)
                log("WARNING: .dmg not created — .app bundle is still in dist/")
            else:
                log(f".dmg created: {dmg_path}")


def _path_install_script(app_name: str) -> str:
    """Genera el script de post-instalación que enlaza tts-sidecar en /usr/local/bin.

    Se incluye en el volumen del .dmg: al ejecutarlo, el usuario obtiene el comando
    `tts-sidecar` disponible en la terminal, como en Windows (PATH) y Linux (AppImage).

    Superficie de `sudo` (SUGGESTION-07): el script pide privilegios de administrador
    solo para `mkdir -p /usr/local/bin` y `ln -sf` — nunca se ejecuta con privilegios
    elevados como parte del build en CI; el usuario final lo ejecuta manualmente y ve
    el prompt de contraseña del sistema, igual que cualquier post-instalador de macOS
    que publique un binario fuera del propio bundle `.app`.
    """
    return f"""#!/bin/bash
# Expone tts-sidecar en el PATH creando un symlink en /usr/local/bin.
set -e

APP="/Applications/{app_name}"
TARGET="$APP/Contents/MacOS/tts-sidecar"
LINK="/usr/local/bin/tts-sidecar"

if [ ! -x "$TARGET" ]; then
    echo "No se encontró {app_name} en /Applications."
    echo "Arrastra primero {app_name} a la carpeta Aplicaciones y vuelve a ejecutar este script."
    exit 1
fi

sudo mkdir -p /usr/local/bin
sudo ln -sf "$TARGET" "$LINK"
echo "Listo: 'tts-sidecar' está disponible en la terminal (via $LINK)."
"""


def _info_plist_content(version):
    """Genera el contenido XML del Info.plist del bundle .app para macOS.

    Define los metadatos del bundle (CFBundleIdentifier, CFBundleVersion, etc.)
    que macOS usa para identificar la aplicación en el sistema.
    """
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>tts-sidecar</string>
    <key>CFBundleIdentifier</key>
    <string>com.tts-sidecar.app</string>
    <key>CFBundleName</key>
    <string>tts-sidecar</string>
    <key>CFBundleDisplayName</key>
    <string>tts-sidecar</string>
    <key>CFBundleVersion</key>
    <string>{version}</string>
    <key>CFBundleShortVersionString</key>
    <string>{version}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string></string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.utilities</string>
    <key>NSHumanReadableCopyright</key>
    <string>GPL-3.0-or-later</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
"""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build macOS .app bundle")
    parser.add_argument(
        "--arch", default="universal2",
        choices=["x86_64", "arm64", "universal2"],
        help="Target architecture (default: universal2)",
    )
    args = parser.parse_args()
    check_dependencies()
    build_macos(args.arch)
