# Guía de Construcción

`tts-sidecar` se compila con **Nuitka** (Python → C → binario) para obtener un ejecutable standalone multiplataforma.

## Requisitos

- **Python 3.12+** ([python.org](https://www.python.org/downloads/))
- **Nuitka** (`pip install nuitka`)
- **Visual Studio Build Tools 2022** (Windows) con:
  - "Desktop development with C++"
  - Windows 11 SDK

## Plataformas Soportadas

| Plataforma | Comando | Output |
|------------|---------|--------|
| Windows x64 | `npm run build-windows` | `bin/win32-x64/tts-sidecar.exe` |
| Linux x64 | `npm run build-linux` | `bin/linux-x64/tts-sidecar` |
| Linux ARM64 | `npm run build-linux-arm64` | `bin/linux-arm64/tts-sidecar` |
| macOS Intel | `npm run build-darwin` | `bin/darwin-x64/tts-sidecar` |
| macOS Apple Silicon | `npm run build-darwin-arm64` | `bin/darwin-arm64/tts-sidecar` |

## Compilación

### Rápido (usa Nuitka)

```bash
# Windows
npm run build-windows

# Linux
npm run build-linux

# macOS
npm run build-darwin
```

El script `scripts/build_windows.py` ejecuta:

```bash
python -m nuitka --standalone --onefile \
  --enable-plugin=anti-bloat \
  --windows-icon=assets/icon.ico \
  --output-dir=bin \
  bin/tts-sidecar
```

## Verificación

Después de compilar:

```bash
bin/win32-x64/tts-sidecar.exe version
bin/win32-x64/tts-sidecar.exe doctor
```
