# CI/CD Build Pipeline

Este documento describe el pipeline de CI/CD para compilar `tts-sidecar` en múltiples plataformas usando Nuitka.

## Arquitectura del Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                      Pipeline                                 │
│                   (multijob)                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │build-win64  │  │build-lin64  │  │build-linarm │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                 │                 │                 │
│         ▼                 ▼                 ▼                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │build-darwin │  │build-darwin │                          │
│  │    x64      │  │   arm64     │                          │
│  └─────────────┘  └─────────────┘                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Plataformas Soportadas

| Job | Plataforma | Compilador | Executor | Notas |
|-----|------------|------------|----------|-------|
| `build-windows` | Windows x64 | Nuitka + MSVC | windows-server | Nuitka onefile |
| `build-linux-x64` | Linux x64 | Nuitka + GCC | ubuntu | Nuitka onefile |
| `build-linux-arm64` | Linux ARM64 | Nuitka + GCC | ubuntu | Cross-compile |
| `build-darwin-x64` | macOS Intel | Nuitka + Clang | macos | Nuitka onefile |
| `build-darwin-arm64` | macOS Apple Silicon | Nuitka + Clang | macos | Cross-compile |

## Configuración

### Requisitos del Proyecto

1. **Python 3.13+** con Nuitka instalado:
   ```bash
   pip install nuitka==2.6.8
   ```

2. **Visual Studio Build Tools 2022** (Windows) con:
   - "Desktop development with C++"
   - Windows 11 SDK

3. **macOS**: Command Line Tools for Xcode

4. **Linux**: GCC y dependencias de Python

## Estructura del Proyecto para Build

```
tts-sidecar/
├── bin/
│   └── tts-sidecar           # Entry point (no __main__.py)
├── src/
│   └── chatterbox_tts/       # Python package
├── scripts/
│   ├── build_windows.py
│   ├── build_linux.py
│   └── build_macos.py
├── nuitka/
│   └── tts-sidecar.spec      # Nuitka spec file
└── pyproject.toml
```

## Configuración de GitHub Actions (Recomendado)

```yaml
name: Build tts-sidecar

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build-windows:
    runs-on: windows-2022
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install nuitka==2.6.8
          pip install -r requirements.txt

      - name: Build Windows
        run: python scripts/build_windows.py

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: tts-sidecar-windows
          path: bin/win32-x64/tts-sidecar.exe

  build-linux-x64:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install nuitka==2.6.8
          pip install -r requirements.txt

      - name: Build Linux x64
        run: python scripts/build_linux.py --arch x86_64

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: tts-sidecar-linux-x64
          path: bin/linux-x64/tts-sidecar

  build-linux-arm64:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install nuitka==2.6.8
          pip install -r requirements.txt

      - name: Build Linux ARM64
        run: python scripts/build_linux.py --arch arm64

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: tts-sidecar-linux-arm64
          path: bin/linux-arm64/tts-sidecar

  build-darwin-x64:
    runs-on: macos-13
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install nuitka==2.6.8
          pip install -r requirements.txt

      - name: Build macOS x64
        run: python scripts/build_macos.py --arch x86_64

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: tts-sidecar-darwin-x64
          path: bin/darwin-x64/tts-sidecar

  build-darwin-arm64:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install nuitka==2.6.8
          pip install -r requirements.txt

      - name: Build macOS ARM64
        run: python scripts/build_macos.py --arch arm64

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: tts-sidecar-darwin-arm64
          path: bin/darwin-arm64/tts-sidecar

  release:
    needs: [build-windows, build-linux-x64, build-linux-arm64, build-darwin-x64, build-darwin-arm64]
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    
    steps:
      - name: Download all artifacts
        uses: actions/download-artifact@v4
        with:
          path: artifacts

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: |
            artifacts/tts-sidecar-windows/tts-sidecar.exe
            artifacts/tts-sidecar-linux-x64/tts-sidecar
            artifacts/tts-sidecar-linux-arm64/tts-sidecar
            artifacts/tts-sidecar-darwin-x64/tts-sidecar
            artifacts/tts-sidecar-darwin-arm64/tts-sidecar
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Distribución de Binarios

Los binarios compilados se almacenan en `bin/<platform>/`:

```bash
# Estructura final
bin/
├── win32-x64/
│   └── tts-sidecar.exe
├── linux-x64/
│   └── tts-sidecar
├── linux-arm64/
│   └── tts-sidecar
├── darwin-x64/
│   └── tts-sidecar
└── darwin-arm64/
    └── tts-sidecar
```

## Notas Importantes

- **Nuitka onefile**: El binario incluye el interpreter de Python embebido
- **Tamaño**: Los binarios Nuitka son más grandes (~100-200MB) pero no requieren Python instalado
- **macOS**: Los binarios deben ser firmados/notarized para distribución fuera de App Store
- **Windows**: El binario es autocontenido y no requiere Visual Studio
- **Linux**: Requiere GCC para compilar las extensiones C de Nuitka

## Troubleshooting

### Windows: "Visual Studio not found"
```powershell
# Instalar Visual Studio Build Tools
winget install Microsoft.VisualStudio.2022.BuildTools
```

### macOS: "clang error"
```bash
# Instalar Command Line Tools
xcode-select --install
```

### Linux: "gcc not found"
```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
```
