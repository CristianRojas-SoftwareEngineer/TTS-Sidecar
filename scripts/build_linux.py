#!/usr/bin/env python3
"""
Build script for Linux x64 and ARM64 using PyInstaller --onedir.
Produces a folder with the executable + all dependencies, then wraps it
in an AppImage for distribution.
"""

import os
import sys
import subprocess
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
        try:
            import sounddevice
        except ImportError:
            log("sounddevice not installed, installing...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "sounddevice"],
                check=True,
            )

        # appimage-builder genera el AppImage a partir del bundle onedir
        try:
            import appimagebuilder
            log("appimage-builder: installed")
        except ImportError:
            log("appimage-builder not found, installing...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "appimage-builder"],
                check=True,
            )


def build_linux(target_arch="x86_64"):
    """Build Linux with PyInstaller --onedir and package as AppImage."""
    arch_map = {"x86_64": "x86_64", "arm64": "aarch64"}
    arch_suffix = arch_map.get(target_arch, "x86_64")
    appimage_arch = arch_suffix  # mismo mapeo; alias para mayor claridad en la sección AppImage

    with BuildTimer():
        with StageTimer("Setup", "Setting up build environment"):
            log(f"Platform: Linux {arch_suffix}")
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            entry_point = PROJECT_ROOT / "bin" / "tts-sidecar"

        with StageTimer("PyInstaller", "Compiling with PyInstaller (9-15 min)"):
            pyinstaller_args = common_pyinstaller_args(
                entry_point, PROJECT_ROOT, DIST_DIR, BUILD_DIR,
                data_sep=":",
                extra_collect_all=["sounddevice"],
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

        with StageTimer("Licenses", "Empaquetando avisos de licencia"):
            copy_license_files(onedir)

        with StageTimer("AppImage", "Building AppImage"):
            appimageyml = PROJECT_ROOT / "scripts" / "tts-sidecar.yml"
            if not appimageyml.exists():
                log("WARNING: tts-sidecar.yml not found — AppImage not generated.")
                log(f"Create {appimageyml} with appimage-builder config.")
                return

            # El spec toma la versión y la arquitectura del entorno.
            env = os.environ.copy()
            env["APP_VERSION"] = get_version()
            env["TARGET_ARCH"] = appimage_arch

            # appimage-builder requiere un icono presente en el AppDir; genera uno
            # mínimo si no existe (el proyecto es una CLI sin icono propio).
            _ensure_placeholder_icon(PROJECT_ROOT)

            result = subprocess.run(
                ["appimage-builder", "--recipe", str(appimageyml), "--skip-test"],
                cwd=str(PROJECT_ROOT),
                env=env,
                capture_output=True, text=True,
                timeout=BUILD_SUBPROCESS_TIMEOUT,
            )
            if result.returncode != 0:
                log(f"AppImage build failed (rc={result.returncode})")
                print(result.stdout)
                print(result.stderr, file=sys.stderr)
                log("WARNING: AppImage failed — onedir bundle is still in dist/")
                return

            # appimage-builder deja el .AppImage en el cwd (PROJECT_ROOT); localizarlo
            # y moverlo a dist/ con el nombre canónico por arquitectura.
            generated = DIST_DIR / f"tts-sidecar-{appimage_arch}.AppImage"
            candidates = sorted(PROJECT_ROOT.glob("*.AppImage")) + sorted(DIST_DIR.glob("*.AppImage"))
            src = next((c for c in candidates if c != generated), None)
            if src and src.exists():
                if generated.exists():
                    generated.unlink()
                src.rename(generated)
                log(f"AppImage created: {generated}")
            elif generated.exists():
                log(f"AppImage created: {generated}")
            else:
                log("WARNING: appimage-builder ran but no .AppImage was found")


def _ensure_placeholder_icon(project_root: Path):
    """Crea un icono PNG mínimo si no existe (appimage-builder lo exige)."""
    icon = project_root / "tts-sidecar.png"
    if icon.exists():
        return
    # PNG 1x1 transparente (base64) — suficiente como placeholder de icono.
    import base64
    png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    icon.write_bytes(png_1x1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build Linux executable")
    parser.add_argument(
        "--arch", default="x86_64", choices=["x86_64", "arm64"],
        help="Target architecture",
    )
    args = parser.parse_args()
    check_dependencies()
    build_linux(args.arch)
