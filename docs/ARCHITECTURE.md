# Arquitectura de TTS Sidecar

## Visión General

```
┌─────────────────────────────────────────────────────────────┐
│              tts-sidecar (binario ejecutable)              │
│   Instalador por SO (Windows, Linux, macOS)                │
│   Bundle PyInstaller --onedir con intérprete embebido      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Chatterbox Multilingual V3                         │
│   Modelo: es-mx-latam (caché de HuggingFace)              │
│   Licencia: MIT                                           │
│   Idiomas: 23+ (español, inglés, francés, etc.)            │
│   Inferencia: CPU / CUDA / MPS                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Reproducción de audio (APIs nativas)             │
│   Windows: pycaw (WASAPI) / winsound                     │
│   Linux: sounddevice (PortAudio) / pyalsaaudio          │
│   macOS: afplay (nativo) / AVFoundation                 │
└─────────────────────────────────────────────────────────────┘
```

## Principios de Diseño

### Python + PyInstaller

- **Python**: Motor TTS con Chatterbox
- **PyInstaller**: Empaqueta Python bytecode en ejecutable con interpreter embebido
- **Resultado**: Un solo archivo binario por SO, sin dependencias externas

### El entry point `bin/tts-sidecar`

El archivo `bin/tts-sidecar` es el **punto de entrada único** de la aplicación. Está escrito en **Python 3**, pero deliberadamente **no lleva extensión `.py`**:

- **Convención de comando CLI**: el objetivo del proyecto es exponer una herramienta invocable como `tts-sidecar speak ...`, no como `tts-sidecar.py speak ...`. Los comandos de terminal no llevan extensión (igual que `git`, `node` o `pip`), de modo que el archivo se nombra como el comando final que representa.
- **Shebang en vez de extensión**: la primera línea es `#!/usr/bin/env python3`. En Linux/macOS, con el bit de ejecución activo (`chmod +x`), el sistema operativo lee esa línea para saber con qué intérprete ejecutarlo; la extensión `.py` solo orienta a editores y humanos, el SO nunca la necesita. Por eso `./tts-sidecar speak ...` funciona sin nombrar a Python.
- **Invocación en desarrollo bajo Windows**: Windows ignora el shebang, así que en desarrollo el entry point se invoca explícitamente a través del intérprete: `python bin/tts-sidecar speak --text "Hola"`.

El archivo no contiene lógica de negocio: prepara el entorno (silencia warnings, ajusta `sys.path`, parchea `pkg_resources` para Python 3.13+) y delega en `chatterbox_tts.cli.main`. Además es la **semilla de compilación** que reciben los scripts de `scripts/build_*.py`: PyInstaller lo toma como entrada y produce el bundle final. Véase `docs/BUILD.md`.

### Estructura del Proyecto

```
tts-sidecar/
├── src/
│   └── chatterbox_tts/        # Paquete Python
│       ├── __init__.py         # Imports perezosos (lazy)
│       ├── engine.py           # Wrapper de ChatterboxTTS
│       ├── audio.py           # Reproducción de audio multiplataforma
│       ├── timing.py           # Instrumentación y timing
│       ├── cli.py             # Interfaz CLI
│       └── daemon/            # Daemon mode (FastAPI + IPC)
│           ├── daemon.py      # Gestor del ciclo de vida
│           ├── server.py      # Endpoints FastAPI
│           ├── ipc.py         # Cliente HTTP del daemon
│           ├── protocol.py    # Modelos Pydantic de request/response
│           └── run.py         # Entry point
├── bin/
│   └── tts-sidecar           # Entry point (Python, sin extensión; semilla de compilación)
├── scripts/
│   ├── build_windows.py      # Build PyInstaller para Windows
│   ├── build_linux.py       # Build PyInstaller para Linux
│   ├── build_macos.py       # Build PyInstaller para macOS
│   └── install.py            # Descarga del modelo + setup
├── tests/                    # Suite de tests pytest
├── requirements.txt           # Dependencias Python
├── pyproject.toml            # Configuración del proyecto Python
└── docs/
    ├── ARCHITECTURE.md
    ├── BUILD.md
    ├── DAEMON-MODE.md
    ├── DESIGN.md
    └── GOAL.md
```

## Modelos Disponibles

| Modelo | Descripción | Licencia |
|--------|-------------|----------|
| `multilingual` | Modelo base, 23+ idiomas | MIT |
| `es-mx-latam` | Español latinoamericano (RECOMENDADO) | MIT |

## Flujo de Síntesis

```
speak --text "Hola" -v mi_voz
       │
       ▼
┌──────────────────┐
│ ChatterboxEngine │
│ speak()         │
│                 │
│ 1. Cargar modelo│
│ 2. Generar     │
│ 3. Devolver WAV │
└────────┬────────┘
         │ bytes WAV
         ▼
┌──────────────────┐
│ AudioPlayer      │
│ play()          │
│                 │
│ API nativa del SO│
└─────────────────┘
```

## Clonación de Voz

Chatterbox permite clonar cualquier voz a partir de ~10 segundos de audio. Cada voz requiere dos archivos:

1. `voice-add --name mi_voz --reference timbre.wav --speech condicion.wav` registra la voz
2. Los archivos se guardan en `voices/mi_voz/reference.wav` y `voices/mi_voz/speech.wav`
   - `reference.wav` → Voice Encoder (timbre completo)
   - `speech.wav` → T3 conditioning + S3Gen decoder (patrón de habla)
3. `speak --text "..." -v mi_voz` usa ambos archivos automáticamente para la síntesis

## Extensibilidad

Para añadir un nuevo motor TTS:

1. Crear nuevo módulo en `src/chatterbox_tts/`
2. Mantener la misma interfaz en `cli.py`
3. Re-empaquetar con PyInstaller para cada plataforma
