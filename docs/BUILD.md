# Guía de Construcción

`tts-sidecar` se compila con **PyInstaller** (empaquetado de Python bytecode) para obtener un ejecutable autocontenido multiplataforma, luego se envuelve en un instalador por SO.

---

## 1. Requisitos

- **Python 3.13+** ([python.org](https://www.python.org/downloads/))
- **PyInstaller** (`pip install pyinstaller`)

### Herramientas de empaquetado por plataforma

| Plataforma | Herramienta | Instalación |
|------------|-------------|-------------|
| Windows | Inno Setup 6 | `choco install innosetup -y --version=6.3.3` o [jrsoftware.org](https://jrsoftware.org/isdl.php) |
| Linux | appimagetool + runtime estático (type2-runtime) | Descarga automática pineada por URL + SHA-256 (`build_linux.py`); sin instalación manual |
| macOS | create-dmg | `brew install create-dmg` (script de shell de Homebrew, no existe en PyPI) |

### Política interactiva de dependencias de build

Los tres scripts de build comparten una única política, implementada en
`build_utils.ensure_build_dependency`: **verificar → avisar → preguntar →
instalar pineado o degradar**. Si una herramienta falta y hay TTY, el script
muestra el comando exacto de instalación y pregunta s/n; sin TTY (CI) no
pregunta, emite la instrucción manual y resuelve según criticidad:

- **Requeridas** (PyInstaller, sounddevice en Linux y macOS): sin ellas el
  build no tiene sentido; el script aborta si no se resuelven.
- **Empaquetadores** (appimagetool, create-dmg, Inno Setup): sin ellos el
  bundle onedir/.app sigue siendo usable; el stage degrada con warning.

Las versiones pineadas viven como constantes en `scripts/build_utils.py`
(`PYINSTALLER_PIN=6.21.0`, `INNOSETUP_PIN=6.3.3`), espejo de las que instala
`.circleci/config.yml`: un build local produce el mismo artefacto que el CI.
El tooling del AppImage no se instala vía pip: `APPIMAGE_TOOLING` pinea las
URLs de release de `appimagetool` (`APPIMAGETOOL_PIN=1.9.1`) y del runtime
estático de type2-runtime (`TYPE2_RUNTIME_PIN=20251108`) con su SHA-256 por
arquitectura; `build_linux.py` los descarga a `build/appimage-tooling/`
verificando el checksum (`fetch_pinned_asset`). El runtime estático arranca
sin `libfuse2` (ausente por defecto en distros modernas), garantizando el
primer arranque del AppImage en cualquier distro.

---

## 2. Plataformas Soportadas

| Plataforma | Comando | Artefacto |
|------------|---------|-----------|
| Windows x64 | `python scripts/build_windows.py --arch x86_64` | `dist/tts-sidecar-0.1.0-x86_64-setup.exe` (instalador) |
| Linux x64 | `python scripts/build_linux.py --arch x86_64` | `dist/tts-sidecar-0.1.0-x86_64.AppImage` |
| Linux ARM64 | `python scripts/build_linux.py --arch arm64` | `dist/tts-sidecar-0.1.0-aarch64.AppImage` |
| macOS arm64 (Apple Silicon) | `python scripts/build_macos.py --arch arm64` | `dist/tts-sidecar-0.1.0-arm64.dmg` |

> **Por qué Linux publica 2 arquitecturas y Windows/macOS solo 1.** Cada
> plataforma publica las arquitecturas que cumplen **a la vez** dos condiciones:
> (a) población real de usuarios y (b) wheels disponibles en el toolchain (torch,
> onnxruntime). Bajo ese criterio:
>
> - **Windows → 1 (x86_64)** por **decisión**: Windows-on-ARM es marginal en la
>   población de usuarios objetivo; el flag `--arch` solo acepta `x86_64`.
> - **macOS → 1 (arm64)** por **imposibilidad técnica**: torch≥2.3 no publica
>   wheels macOS x86_64, por lo que no es posible construir un binario Intel con
>   el toolchain actual. El artefacto se nombra por su arquitectura real (arm64).
> - **Linux → 2 (x86_64 + aarch64)** porque **ambas** arquitecturas cumplen las
>   dos condiciones (usuarios reales y wheels disponibles).
>
> Los campos `os`/`cpu` de `package.json` no expresan la matriz por SO (el esquema
> no lo permite): `x64` aplica a Windows/Linux y `arm64` a Linux/macOS.

> Los scripts de build también generan la carpeta `--onedir` en `dist/tts-sidecar/` (o
> `dist/tts-sidecar.app/` en macOS) con el ejecutable y todas las dependencias,
> útil para pruebas directas sin pasar por el instalador.

---

## 3. Compilación Local

### Verificación de sintaxis

Antes de compilar, verificar que el código Python no tenga errores:

```bash
python -m py_compile src/tts_sidecar/engine.py
python -m py_compile src/tts_sidecar/cli.py
python -m py_compile src/tts_sidecar/audio.py
python -m py_compile src/tts_sidecar/timing.py
python -m py_compile src/tts_sidecar/daemon/*.py
```

### Scripts de build

```bash
# Windows (requiere Inno Setup instalado)
python scripts/build_windows.py --arch x86_64

# Linux (descarga appimagetool + runtime estático, pineados por SHA-256)
python scripts/build_linux.py --arch x86_64

# macOS (requiere create-dmg)
python scripts/build_macos.py --arch arm64
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

El **smoke test del binario congelado está automatizado en CI**: cada uno de los
4 jobs de build ejecuta `tts-sidecar version` sobre el ejecutable recién
construido (exit 0 obligatorio) antes de publicar el artefacto, de modo que un
empaquetado roto (metadata faltante, `--collect-all` incompleto) hace fallar el
job en lugar de publicarse «verde». `version` no carga el modelo, así que el
chequeo es de segundos.

Queda **manual** (requiere modelo, audio real y hardware por SO): `doctor`,
`setup` y una síntesis real (`speak`).

```bash
# Tests
pytest tests/ -v

# Ejecutable directo (carpeta onedir) — 'version' es el que corre en CI
dist/tts-sidecar/tts-sidecar.exe version
dist/tts-sidecar/tts-sidecar.exe doctor

# Provisionar el modelo es-mx-latam (chequeos + descarga si falta; idempotente)
dist/tts-sidecar/tts-sidecar.exe setup

# Instalador (Windows)
dist/tts-sidecar-0.1.0-x86_64-setup.exe
```

### Matriz de integración con el SO

Cada plataforma integra `tts-sidecar` en el sistema con un mecanismo distinto,
pero la experiencia resultante es homóloga (comando en el PATH + provisión
guiada + desinstalación limpia):

| Aspecto | Windows | Linux | macOS |
|---------|---------|-------|-------|
| PATH | Automático: el instalador agrega `{app}` al PATH del sistema | `tts-sidecar setup` crea el symlink `~/.local/bin/tts-sidecar → $APPIMAGE` | Opt-in: `Instalar (PATH + modelo).command` del `.dmg` (symlink en `/usr/local/bin`, con sudo) |
| Guía hacia `setup` | Página informativa + casilla post-instalación que lo ejecuta en contexto de usuario | `setup` es el punto único de provisión (modelo + PATH) | El script de instalación ofrece ejecutar `setup` (sin sudo) tras enlazar |
| Desinstalación | Desinstalador de Inno Setup (revierte PATH y registro) | `tts-sidecar setup --remove-path` + borrar el `.AppImage` | `Desinstalar (quitar del PATH).command` del `.dmg` + arrastrar el `.app` a la Papelera |
| Datos provisionados | `tts-sidecar cleanup --all` (paso previo recomendado en los tres SO: elimina modelo y voces de usuario antes de desinstalar el binario) | Ídem | Ídem |
| Dependencias de build | Política interactiva común (`ensure_build_dependency`) | Ídem | Ídem |

> El modelo `es-mx-latam` se descarga a `~/.cache/huggingface/hub` y no se
> empaqueta en el ejecutable; `speak` y `daemon start` fallan rápido remitiendo
> a `setup` mientras falte.

### Limitación conocida: firma de código y notarización

Los artefactos **no están firmados ni notarizados**: en macOS, Gatekeeper
bloquea la primera apertura del `.app`/`.dmg` (clic derecho → Abrir, o
`xattr -d com.apple.quarantine`); en Windows, SmartScreen muestra la advertencia
de editor desconocido en el instalador. Firmar/notarizar requiere certificados
de pago (Apple Developer ID, certificado Authenticode) y queda fuera del
alcance actual del pipeline.

---

## 4. CI/CD con CircleCI

El pipeline de CircleCI ejecuta los tests y, si pasan, compila el proyecto para todas las
plataformas automáticamente. Los jobs `test-linux`, `test-windows` y `test-macos` actúan
como **triple puerta simétrica**: cada build depende de los tres
(`requires: [test-linux, test-windows, test-macos]`), de modo que la suite se ejercita en
los tres SO nativos antes de compilar. Así, un bug específico de plataforma —Windows
(pycaw/COM, winsound, generación del `.iss`) o macOS (afplay/sounddevice, rutas y señales
POSIX)— se detecta en el gate en lugar de llegar al usuario. La cobertura es equivalente
para los tres SO **por familia de SO**: el mismo `pytest tests/` corre en cada uno. La
suite se ejercita en **una** arquitectura por SO (Linux en x86_64), no en las dos que
Linux publica; el porqué de esa asimetría se detalla en la subsección siguiente.

### Simetría: 3 puertas de test vs. 4 targets de build

Los tests (3) y los builds (4) no están desalineados: responden a **ejes distintos**.

- **Por qué 3 puertas de test y 4 builds.** Los tests son **por familia de SO**:
  validan la lógica Python (independiente de la arquitectura) más el código específico
  de cada SO (Windows: pycaw/COM, winsound, generación del `.iss`; macOS:
  afplay/sounddevice, rutas y señales POSIX; Linux: ALSA). Los builds son **por target
  de distribución**, y Linux publica **dos** arquitecturas (x86_64 + aarch64). No es
  una asimetría arbitraria: son dos ejes ortogonales (SO × build-target).

- **Por qué el runner de `test-linux` es x86_64.** Es el executor Docker más barato,
  rápido y disponible. Como la suite es arch-independiente y **mockea el engine**
  (torch/onnxruntime no se ejercitan en los tests), correrla en la arquitectura más
  barata basta: un `test-linux-arm64` no aportaría señal adicional.

- **Hueco de cobertura de ARM64 (divergencia aceptada).** `build-linux-arm64` está
  *gated* por tests que solo corrieron en x86_64 → no hay una puerta `pytest` nativa en
  ARM. El riesgo arch-específico real (wheel `aarch64` faltante, segfault de una
  extensión nativa) lo cubre el **smoke test** del propio build (`tts-sidecar version`,
  que importa el stack nativo en ARM y exige exit 0), no la suite. Se documenta como
  **decisión consciente**: un `test-linux-arm64` re-correría la suite mockeada (señal
  marginal) a un coste recurrente en cada push (VM `machine`), sin cerrar el riesgo que
  el smoke test ya cubre. Reconsiderar solo ante un bug arch-específico; el *fast-follow*
  de mayor ROI sería un test de integración que cargue el modelo y sintetice en ARM, no
  re-correr la suite.

### Arquitectura del Pipeline

```
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│     test-linux     │  │    test-windows    │  │     test-macos     │
│ (pytest — Linux)   │  │ (pytest — Windows) │  │  (pytest — macOS)  │
└─────────┬──────────┘  └─────────┬──────────┘  └─────────┬──────────┘
          └──────────────────────┬┴───────────────────────┘
        ┌───────────────┬────────┴──────┬───────────────┐
        ▼               ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐
│build-windows│ │build-linux- │ │build-linux- │ │ build-darwin-    │
│ -x64+ Inno  │ │    x64      │ │   arm64     │ │     arm64        │
│  Setup      │ │ + AppImage  │ │ + AppImage  │ │  + create-dmg    │
└─────────────┘ └─────────────┘ └─────────────┘ └──────────────────┘
     (cada build corre además un smoke test `version` del binario congelado)
```

### Jobs

| Job | Plataforma | Executor | Notas |
|-----|------------|----------|-------|
| `test-linux` | Linux x64 | docker `cimg/python:3.13` | `pytest tests/` en Linux (puerta previa) |
| `test-windows` | Windows x64 | `win/server-2022` | `pytest tests/` en Windows nativo (puerta previa) |
| `test-macos` | macOS arm64 (Apple Silicon) | macos `m4pro.medium` (Xcode 26.4.0) | `pytest tests/` en macOS nativo (puerta previa) |
| `build-windows-x64` | Windows x64 | `win/server-2022` | PyInstaller onedir + Inno Setup |
| `build-linux-x64` | Linux x64 | docker `cimg/python:3.13` | PyInstaller onedir + AppImage |
| `build-linux-arm64` | Linux ARM64 | machine `arm.medium` | PyInstaller onedir + AppImage |
| `build-darwin-arm64` | macOS arm64 (Apple Silicon) | macos `m4pro.medium` (Xcode 26.4.0) | PyInstaller onedir + .app + .dmg |
| `publish-release` | — (CD) | docker `cimg/base:current` | Solo en tags `v*`: recolecta los 4 artefactos por workspace, genera `SHA256SUMS.txt` y crea un GitHub Release en **borrador** |

El archivo de configuración completo está en `.circleci/config.yml`.

### CD: publicación del GitHub Release (`publish-release`)

Al pushear un tag `v*`, además de tests + builds corre `publish-release`
(estrategia 1, GitHub Releases). Recolecta los 4 artefactos **versionados** por
`persist_to_workspace`/`attach_workspace` (no `gh run download`: se queda dentro
del pipeline, es determinista y no requiere token de API de CircleCI), genera
`SHA256SUMS.txt`, extrae las notas de la sección `[X.Y.Z]` de `CHANGELOG.md`
(fail-fast si no existe) y crea el Release en **borrador**. El humano revisa el
draft y pulsa «publish». El detalle del runbook está en `docs/RELEASING.md`.

Requisito operativo: el context `github-release` en CircleCI con `GH_TOKEN`
(fine-grained PAT, permiso `contents: write` sobre el repo), aislado al job de
release. Para que CircleCI ejecute jobs en un tag, el job **y todas sus
dependencias** deben declarar `filters.tags`; por eso el filtro `v*` se propaga
por tests → builds → `publish-release`.

---

## 5. Distribución de artefactos

Los artefactos publicados por CI se almacenan en `dist/`:

```
dist/
├── tts-sidecar-0.1.0-x86_64-setup.exe   # Windows (instalador Inno Setup)
├── tts-sidecar/                          # Windows onedir (carpeta)
├── tts-sidecar-0.1.0-x86_64.AppImage    # Linux x64
├── tts-sidecar-0.1.0-aarch64.AppImage   # Linux ARM64
├── tts-sidecar-0.1.0-arm64.dmg          # macOS (Apple Silicon)
└── tts-sidecar-arm64.app/                # macOS .app bundle (nombre estable: se arrastra a /Applications)
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

### Lockfile de dependencias (`requirements-lock.txt`)

El CI y los builds **no** instalan desde `requirements.txt` (límites `>=` de
desarrollo), sino desde `requirements-lock.txt`: un **lock universal con hashes**
que fija la versión exacta de cada dependencia de runtime (directa y transitiva)
para builds reproducibles e íntegros. Los 7 jobs de CI lo instalan con
`pip install -r requirements-lock.txt --require-hashes`, que rechaza cualquier
paquete cuyo contenido no coincida con el hash fijado (barrera de supply-chain).

El lock es **universal**: un solo archivo cubre Windows, Linux y macOS mediante
marcadores de entorno (`sys_platform`, etc.), imprescindible porque el grafo de
`torch` diverge por plataforma (wheels NVIDIA/CUDA solo en Linux). Se genera con
[uv](https://github.com/astral-sh/uv), cuyo resolver universal produce esa matriz
en un único archivo (pip-tools resuelve solo para la plataforma donde corre, y no
puede hacerlo).

**Regeneración deliberada** (tras cambiar dependencias en `pyproject.toml`):

```bash
pip install uv   # si no está disponible
uv pip compile --universal --generate-hashes --python-version 3.13 \
    pyproject.toml -o requirements-lock.txt
```

Actualizar el lock es una acción **consciente**, no automática: revisar el diff
antes de commitear para auditar qué versiones y hashes cambian. Las herramientas
de build (`pyinstaller`, `pytest`) se instalan aparte con su pin exacto (`==`),
en invocaciones de pip separadas del lock.

### Lock CPU-only de Linux (`requirements-lock-linux-cpu.txt`)

El lock universal resuelve, para `sys_platform == 'linux' and platform_machine
== 'x86_64'`, el stack `nvidia-*-cu12` (~41 paquetes) que PyPI empareja por
defecto con `torch` en esa combinación de plataforma/arquitectura — el AppImage
lo arrastraba vía `--collect-all torch` aunque el proyecto no usa GPU NVIDIA.
`arm64` no se ve afectado (esos marcadores excluyen `platform_machine !=
'x86_64'`), así que solo el job `build-linux-x64` instala desde este lock
alternativo; `build-linux-arm64`, los jobs de test y los builds de
Windows/macOS siguen usando `requirements-lock.txt`.

`requirements-lock-linux-cpu.txt` fija `torch`/`torchaudio` a los wheels
`+cpu` del índice oficial de PyTorch en vez de los de PyPI, sin ningún paquete
`nvidia-*`. Se regenera con:

```bash
uv pip compile --generate-hashes --python-version 3.13 \
    --python-platform x86_64-unknown-linux-gnu \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match \
    pyproject.toml -o requirements-lock-linux-cpu.txt
```

Un usuario que necesite aceleración NVIDIA debe compilar desde código fuente
instalando el `requirements-lock.txt` universal (que sí resuelve el stack CUDA
en x86_64/Linux) en vez de usar el AppImage distribuido.

### `chatterbox-tts` metadata

`chatterbox/__init__.py` llama `importlib.metadata.version("chatterbox-tts")` al importar.
Sin `--recursive-copy-metadata chatterbox-tts`, el comando `doctor` reporta "NOT INSTALLED"
en el bundle congelado.

### Audio por plataforma

| Plataforma | Librería | Notas |
|------------|----------|-------|
| Windows | `pycaw` | Incluida (enumeración; reproduce `winsound`, built-in) |
| Linux | `sounddevice` | Incluida (reproducción y enumeración) |
| macOS | `afplay` (built-in) + `sounddevice` | `afplay` reproduce; `sounddevice` (incluida en el bundle) enumera dispositivos para `doctor`/`devices` |

### Paquetes recopilados con `--collect-all`

PyInstaller no sigue automáticamente imports lazy ni extensiones nativas en runtime.
Los paquetes que requieren `--collect-all` son: `chatterbox`, `transformers`,
`diffusers`, `torch`, `sklearn`, `pandas`, `s3tokenizer`, `perth`, `librosa`, `onnx`, `pycaw`.

---

## 8. Notas importantes

- **PyInstaller --onedir**: genera una carpeta con el ejecutable y todas las dependencias
  (del orden de 1-2 GB sin comprimir en Windows/macOS y en el AppImage `arm64`
  de Linux, que resuelven `torch` desde `requirements-lock.txt`). El AppImage
  `x86_64` de Linux, construido desde `requirements-lock-linux-cpu.txt` (ver
  «Lock CPU-only de Linux» más arriba), es sensiblemente más liviano al no
  arrastrar el stack `nvidia-*-cu12`; el tamaño exacto queda pendiente de medir
  en un run de CI (`build-linux-x64`) y actualizar aquí. Es el artefacto que el
  script de empaquetado consume.
- **Tiempo de build**: ~10 min en frío, ~5 min incremental.
- **Windows**: el instalador Inno Setup es el artefacto que recibe el usuario final;
  ajusta el `PATH`, muestra la página informativa del modelo y ofrece ejecutar `setup`.
- **Linux**: el AppImage es un único archivo ejecutable, compatible con la mayoría de
  distribuciones; `tts-sidecar setup` lo integra en el PATH (symlink en `~/.local/bin`).
- **macOS**: el `.dmg` es el instalador estándar de macOS; incluye el `.app` bundle más
  los scripts de instalación (PATH + oferta de `setup`) y desinstalación.
- **Firma de código**: ver la limitación conocida en la sección 3 (artefactos sin
  firmar/notarizar: Gatekeeper y SmartScreen advierten en el primer arranque).
