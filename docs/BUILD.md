# Guía de Construcción

`tts-sidecar` se compila con **PyInstaller** (empaquetado de Python bytecode) para obtener un ejecutable autocontenido multiplataforma, luego se envuelve en un instalador por SO.

---

## 1. Requisitos

- **Python 3.13+** ([python.org](https://www.python.org/downloads/))
- **PyInstaller** (`pip install pyinstaller`)

### Herramientas de empaquetado por plataforma

| Plataforma | Herramienta | Instalación |
|------------|-------------|-------------|
| Windows | Inno Setup 6 | `choco install innosetup` o [jrsoftware.org](https://jrsoftware.org/isdl.php) |
| Linux | appimage-builder | `pip install appimage-builder` |
| macOS | create-dmg | `pip install create-dmg` (o `brew install create-dmg`) |

---

## 2. Plataformas Soportadas

| Plataforma | Comando | Artefacto |
|------------|---------|-----------|
| Windows x64 | `python scripts/build_windows.py` | `dist/tts-sidecar-0.1.0-setup.exe` (instalador) |
| Linux x64 | `python scripts/build_linux.py --arch x86_64` | `dist/tts-sidecar-x86_64.AppImage` |
| Linux ARM64 | `python scripts/build_linux.py --arch arm64` | `dist/tts-sidecar-aarch64.AppImage` |
| macOS universal2 | `python scripts/build_macos.py --arch universal2` | `dist/tts-sidecar-universal2.dmg` |

> Los scripts de build también generan la carpeta `--onedir` en `dist/tts-sidecar/` (o
> `dist/tts-sidecar.app/` en macOS) con el ejecutable y todas las dependencias,
> útil para pruebas directas sin pasar por el instalador.

---

## 3. Compilación Local

### Verificación de sintaxis

Antes de compilar, verificar que el código Python no tenga errores:

```bash
python -m py_compile src/chatterbox_tts/engine.py
python -m py_compile src/chatterbox_tts/cli.py
python -m py_compile src/chatterbox_tts/audio.py
python -m py_compile src/chatterbox_tts/timing.py
python -m py_compile src/chatterbox_tts/daemon/*.py
```

### Scripts de build

```bash
# Windows (requiere Inno Setup instalado)
python scripts/build_windows.py

# Linux (requiere appimage-builder)
python scripts/build_linux.py --arch x86_64

# macOS (requiere create-dmg)
python scripts/build_macos.py --arch universal2
```

Los scripts (`scripts/build_*.py`) ejecutan PyInstaller con `--onedir` y luego llaman
a la herramienta de empaquetado correspondiente para producir el instalador final.

> El entry point `bin/tts-sidecar` es la semilla que PyInstaller empaqueta. El bundle
> resultante hereda ese nombre en `dist/tts-sidecar/`. Véase `docs/ARCHITECTURE.md` para
> el detalle del entry point.

### Opciones clave de PyInstaller

```bash
python -m PyInstaller --onedir --console \
  --name tts-sidecar \
  --paths src \
  --collect-all chatterbox --collect-all transformers \
  --collect-all diffusers --collect-all torch \
  --collect-all sklearn --collect-all pandas \
  --recursive-copy-metadata chatterbox-tts \
  --copy-metadata requests \
  --exclude-module tensorflow --exclude-module gradio \
  bin/tts-sidecar
```

Los flags `--collect-all` aseguran que PyInstaller empaquete paquetes con extensiones
nativas o imports lazy que no siguen automáticamente. Los flags de metadata (`--recursive-copy-metadata`) son necesarios para que `importlib.metadata` y `pkg_resources` encuentren los metadatos de paquete en el bundle congelado.

### Verificación post-build

```bash
# Tests
pytest tests/ -v

# Ejecutable directo (carpeta onedir)
dist/tts-sidecar/tts-sidecar.exe version
dist/tts-sidecar/tts-sidecar.exe doctor

# Instalador (Windows)
dist/tts-sidecar-0.1.0-setup.exe
```

---

## 4. CI/CD con CircleCI

El pipeline de CircleCI ejecuta los tests y, si pasan, compila el proyecto para todas las
plataformas automáticamente. El job `test` actúa como **puerta**: cada build depende de él
(`requires: [test]`).

### Arquitectura del Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                         test                                 │
│              (pytest tests/ — puerta previa)                 │
└───────┬───────────────┬───────────────┬───────────────┬─────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐
│build-windows│ │build-linux- │ │build-linux- │ │ build-darwin-    │
│  + Inno     │ │    x64      │ │   arm64     │ │   universal2     │
│  Setup      │ │ + AppImage  │ │ + AppImage  │ │  + create-dmg    │
└─────────────┘ └─────────────┘ └─────────────┘ └──────────────────┘
```

### Jobs

| Job | Plataforma | Executor | Notas |
|-----|------------|----------|-------|
| `test` | — | docker `cimg/python:3.13` | `pytest tests/` (puerta previa) |
| `build-windows` | Windows x64 | `win/server-2022` | PyInstaller onedir + Inno Setup |
| `build-linux-x64` | Linux x64 | docker `cimg/python:3.13` | PyInstaller onedir + AppImage |
| `build-linux-arm64` | Linux ARM64 | machine `arm.medium` | PyInstaller onedir + AppImage |
| `build-darwin-universal2` | macOS universal2 | macos `m4pro.medium` (Xcode 26.4.0) | PyInstaller onedir + .app + .dmg |

El archivo de configuración completo está en `.circleci/config.yml`.

---

## 5. Distribución de artefactos

Los artefactos publicados por CI se almacenan en `dist/`:

```
dist/
├── tts-sidecar-0.1.0-setup.exe    # Windows (instalador Inno Setup)
├── tts-sidecar/                     # Windows onedir (carpeta)
├── tts-sidecar-x86_64.AppImage     # Linux x64
├── tts-sidecar-aarch64.AppImage    # Linux ARM64
├── tts-sidecar-universal2.dmg      # macOS
└── tts-sidecar-universal2.app/     # macOS .app bundle
```

---

## 6. Paquetes excluidos (bloat)

Los siguientes paquetes no se usan en runtime y están excluidos del bundle:

| Paquete | Razón |
|---------|--------|
| `gradio` + `gradio_client` | UI web, fuera del path TTS |
| `tensorflow`, `jax`, `flax` | Shims de transformers no cargados en runtime |

---

## 7. Notas de dependencias

### `chatterbox-tts` metadata

`chatterbox/__init__.py` llama `importlib.metadata.version("chatterbox-tts")` al importar.
Sin `--recursive-copy-metadata chatterbox-tts`, el comando `doctor` reporta "NOT INSTALLED"
en el bundle congelado.

### Audio por plataforma

| Plataforma | Librería | Notas |
|------------|----------|-------|
| Windows | `pycaw` | Incluida |
| Linux | `sounddevice` | Incluida |
| macOS | `afplay` (built-in) | Ninguna librería adicional |

### Paquetes recopilados con `--collect-all`

PyInstaller no sigue automáticamente imports lazy ni extensiones nativas en runtime.
Los paquetes que requieren `--collect-all` son: `chatterbox`, `transformers`,
`diffusers`, `torch`, `sklearn`, `pandas`, `s3tokenizer`, `perth`, `librosa`, `onnx`, `pycaw`.

---

## 8. Notas importantes

- **PyInstaller --onedir**: genera una carpeta con el ejecutable y todas las dependencias
  (~1.7 GB sin comprimir). Es el artefacto que el script de empaquetado consume.
- **Tiempo de build**: ~10 min en frío, ~5 min incremental.
- **Windows**: el instalador Inno Setup es el artefacto que recibe el usuario final.
- **Linux**: el AppImage es un único archivo ejecutable, compatible con la mayoría de distribuciones.
- **macOS**: el `.dmg` es el instalador estándar de macOS; el `.app` bundle es la aplicación.
- **macOS code signing**: para distribución fuera de App Store se recomienda firmar/notarize el `.app`.
