# Revisión: auditoría sistémica de tts-sidecar (compatibilidad · corrección · UX/DX · calidad)

## Resumen ejecutivo

Se auditó todo el repositorio `tts-sidecar` bajo una lente combinada de compatibilidad
multiplataforma, corrección/bugs, UX/DX y calidad/deuda técnica, con perfil **preventivo**
(hardening y clases de defectos antes de los builds de CI). Veredicto global: el núcleo del
CLI y del engine está sólido y bien documentado, pero hay **dos defectos que rompen rutas de
build/instalación completas** (dependencias del daemon sin declarar y un `NameError` en el build
de Linux) que materializarían fallos en CI, más deuda de acoplamiento y rutas heredadas
divergentes. Conteo: **2 críticos, 4 advertencias, 4 sugerencias**.

| ID | Título | Grupo | Área/plataforma | Decisión requerida |
|----|--------|-------|-----------------|--------------------|
| CRITICAL-01 | Dependencias del daemon (fastapi/uvicorn/pydantic) sin declarar | Crítico | Empaquetado / todas | Sí |
| CRITICAL-02 | `_get_version()` indefinido en `build_linux.py` (NameError) | Crítico | Build Linux (AppImage) | No |
| WARNING-01 | CI cablea la ruta del artefacto con versión fija `0.1.0` | Advertencia | CI / Windows | No |
| WARNING-02 | `install.py` (`npm run install-model`) provisiona por una vía divergente y probablemente rota | Advertencia | Provisión / todas | Sí |
| WARNING-03 | `snapshots[0]` elige un snapshot arbitrario de la caché HF | Advertencia | Engine / todas | Sí |
| WARNING-04 | La validez de una voz solo comprueba `reference.wav`, no `speech.wav` | Advertencia | Voces / todas | No |
| SUGGESTION-01 | URL de repositorio placeholder `your-org` en `package.json` | Sugerencia | Metadatos | No |
| SUGGESTION-02 | Código muerto `get_socket_path` (residuo de Unix sockets) | Sugerencia | Daemon | No |
| SUGGESTION-03 | Comentario de `tts-sidecar.yml` cita `--appimage-spec`; el código usa `--recipe` | Sugerencia | Build Linux | No |
| SUGGESTION-04 | `devices` en macOS devuelve una lista fija simulada | Sugerencia | Audio / macOS | No |

## Hallazgos por grupo

### Críticos

#### CRITICAL-01 — Dependencias del daemon sin declarar en los manifiestos
- **Área/plataforma**: empaquetado y ejecución del daemon; todas las plataformas.
- **Evidencia**: `src/chatterbox_tts/daemon/server.py:10` (`from fastapi import ...`),
  `src/chatterbox_tts/daemon/run.py:56` (`import uvicorn`),
  `src/chatterbox_tts/daemon/protocol.py:5` (`from pydantic import BaseModel`), frente a
  `pyproject.toml:15-21` y `requirements.txt:9-18`, que **no** listan `fastapi`, `uvicorn`
  ni `pydantic`. Además `daemon/__init__.py:16` importa `.server` de forma ansiosa, y
  `tests/test_daemon.py:14` hace `from chatterbox_tts.daemon import DaemonIPCClient`, por lo
  que importar el paquete daemon arrastra fastapi+pydantic al recolectar los tests.
- **Causa**: la funcionalidad del daemon (FastAPI + uvicorn + pydantic) se añadió sin
  declarar sus dependencias de runtime en la fuente única (`pyproject.toml`) ni en su espejo
  (`requirements.txt`). Los scripts de build tampoco hacen `--collect-all fastapi/uvicorn`
  (PyInstaller las alcanza por el grafo de imports, pero `pip install .` no).
- **Impacto**: `pip install .`, la ejecución desde fuente y el job `test` de CI dependen de
  que alguna dependencia transitiva (p. ej. de `chatterbox-tts`) arrastre estos paquetes.
  `pydantic` es plausible como transitiva; `fastapi`/`uvicorn` no lo son. Si no se resuelven,
  la recolección de `tests/test_daemon.py` y `tests/test_protocol.py` falla con `ImportError`
  y el daemon no arranca. Es un defecto de robustez aunque hoy CI pasara por azar transitivo.
- **Corrección(es) propuesta(s)**:
  1. *(recomendada)* Declarar `fastapi`, `uvicorn` (o `uvicorn[standard]`) y `pydantic` con
     pines en `[project.dependencies]` de `pyproject.toml` y reflejarlos en `requirements.txt`.
  2. Declararlos solo en `requirements.txt` (rechazada: rompe la regla de fuente única).
- **Decisión requerida**: Sí — confirmar el conjunto/forma de los pines y si `uvicorn` va con
  el extra `[standard]`.

#### CRITICAL-02 — `_get_version()` indefinido en `build_linux.py` (NameError)
- **Área/plataforma**: build de Linux (etapa AppImage); jobs `build-linux-x64` y
  `build-linux-arm64` de CI.
- **Evidencia**: `scripts/build_linux.py:144` (`env["APP_VERSION"] = _get_version()`) invoca
  `_get_version()`, que **no** está definido en el módulo ni en su import de `build_utils`
  (`scripts/build_linux.py:18` importa solo `log, StageTimer, BuildTimer, copy_license_files`).
  La función solo existe en `scripts/build_macos.py:214`.
- **Causa**: `_get_version` se definió en `build_macos.py` y se usó en `build_linux.py` sin
  moverla a un hogar compartido ni importarla.
- **Impacto**: la etapa AppImage aborta con `NameError: name '_get_version' is not defined`
  en cuanto existe `scripts/tts-sidecar.yml` (existe), es decir siempre. El bundle onedir se
  genera, pero el AppImage nunca se produce y el build de Linux termina en error.
- **Corrección(es) propuesta(s)**:
  1. *(recomendada)* Mover `_get_version()` a `scripts/build_utils.py` e importarla en los tres
     scripts de build (elimina la duplicación con `create_installer_windows.get_version`).
  2. Duplicar `_get_version()` dentro de `build_linux.py` (rechazada: perpetúa la duplicación).
- **Decisión requerida**: No — corrección evidente (centralizar en `build_utils`).

### Advertencias

#### WARNING-01 — CI cablea la ruta del artefacto con la versión fija `0.1.0`
- **Área/plataforma**: `.circleci/config.yml`, job `build-windows`.
- **Evidencia**: `.circleci/config.yml:47` (`path: dist/tts-sidecar-0.1.0-setup.exe`). El nombre
  real lo genera `create_installer_windows.py` a partir de `__version__` (`__init__.py:6`).
- **Causa**: la ruta del artefacto se escribió literal en lugar de derivarla de la versión.
- **Impacto**: al subir la versión en `__init__.py`, `store_artifacts` apunta a un archivo que
  ya no existe y la subida del instalador falla/queda vacía silenciosamente.
- **Corrección(es) propuesta(s)**: usar un glob (`dist/tts-sidecar-*-setup.exe`) o exportar la
  versión a una variable de entorno de CI. *(recomendada: glob)*.
- **Decisión requerida**: No.

#### WARNING-02 — `install.py` provisiona por una vía divergente y probablemente rota
- **Área/plataforma**: `scripts/install.py`, expuesto como `npm run install-model`
  (`package.json:17`); todas las plataformas.
- **Evidencia**: `scripts/install.py:67`
  (`ChatterboxTTS.from_pretrained("ResembleAI/Chatterbox-Multilingual-es-mx-latam")`), frente
  al loader propio que el engine exige para es-mx-latam (`engine.py:220` `_load_es_latam`,
  vocab de 2454 tokens). El comando canónico `setup` usa `ChatterboxEngine.get_instance`
  (`cli.py:393`), no `from_pretrained`.
- **Causa**: `install.py` es un artefacto heredado (así lo declara su docstring, `install.py:7`)
  que no se actualizó cuando la provisión pasó a `tts-sidecar setup` y al loader es-mx-latam.
- **Impacto**: la ruta `npm run install-model` puede fallar al construir el modelo es-mx-latam
  con el loader base, instala dependencias de forma redundante y escribe un `config.json` que
  ningún módulo lee (`install.py:86`). Divergencia de dos vías de provisión que confunde y
  puede romper la re-descarga del modelo.
- **Corrección(es) propuesta(s)**:
  1. *(recomendada)* Reapuntar `install-model` a `tts-sidecar setup` y eliminar/reducir
     `install.py` (o convertirlo en un thin wrapper de `cmd_setup`).
  2. Corregir `download_model` para usar el engine, conservando el resto.
- **Decisión requerida**: Sí — elegir entre eliminar `install.py`, convertirlo en wrapper de
  `setup`, o corregir su descarga.

#### WARNING-03 — `snapshots[0]` elige un snapshot arbitrario de la caché HF
- **Área/plataforma**: `engine.py`; todas las plataformas.
- **Evidencia**: `engine.py:187` (`cached = snap_path / snapshots[0]`) y `engine.py:624`
  (idéntico en `is_model_cached`). `snapshots` proviene de `os.listdir`, sin orden garantizado.
- **Causa**: se asume un único snapshot; con varias revisiones en caché se toma una al azar.
- **Impacto**: tras una actualización del repo del modelo pueden coexistir varios snapshots; se
  podría cargar/validar una revisión obsoleta de forma no determinista entre ejecuciones.
- **Corrección(es) propuesta(s)**: resolver la revisión actual (leer `refs/main`) o elegir el
  snapshot más reciente por `mtime` en lugar de `[0]`. *(recomendada: refs/main)*.
- **Decisión requerida**: Sí — estrategia de selección (refs vs. mtime).

#### WARNING-04 — La validez de una voz solo comprueba `reference.wav`
- **Área/plataforma**: `voices.py`; todas las plataformas.
- **Evidencia**: `voices.py:43` (`_resolve_voice_dir` valida solo `reference.wav`) y
  `voices.py:56` (`list_voices` idem), mientras que `voice_paths` exige además `speech.wav`
  (`voices.py:89`) y el diseño dual-audio requiere ambos.
- **Causa**: criterio de existencia incompleto (un solo archivo en vez de los dos requeridos).
- **Impacto**: un directorio con solo `reference.wav` se lista y resuelve como voz válida, pero
  luego `voice_paths` lanza `FileNotFoundError` en un punto posterior → validez inconsistente y
  fallo confuso para el usuario.
- **Corrección(es) propuesta(s)**: exigir la existencia de `reference.wav` **y** `speech.wav`
  en `_resolve_voice_dir` y `list_voices`.
- **Decisión requerida**: No.

### Sugerencias

#### SUGGESTION-01 — URL de repositorio placeholder en `package.json`
- **Evidencia**: `package.json:35` (`"url": "https://github.com/your-org/tts-sidecar"`).
- **Impacto**: metadato incorrecto en el paquete publicable. **Corrección**: fijar la URL real.
- **Decisión requerida**: No.

#### SUGGESTION-02 — Código muerto `get_socket_path`
- **Evidencia**: `src/chatterbox_tts/daemon/server.py:22` (marcado como residuo en `:19`), aún
  exportado en `daemon/__init__.py:16,28`.
- **Impacto**: deuda/confusión; el daemon usa HTTP/TCP en todas las plataformas.
  **Corrección**: eliminar la función y su export.
- **Decisión requerida**: No.

#### SUGGESTION-03 — Comentario obsoleto en `tts-sidecar.yml`
- **Evidencia**: `scripts/tts-sidecar.yml:7` cita `appimage-builder --appimage-spec ...`, pero
  `scripts/build_linux.py:152` invoca `--recipe ... --skip-test`.
- **Impacto**: documentación engañosa. **Corrección**: actualizar el comentario a `--recipe`.
- **Decisión requerida**: No.

#### SUGGESTION-04 — `devices` en macOS devuelve una lista fija simulada
- **Evidencia**: `src/chatterbox_tts/audio.py:178-181` (TODO; retorna un único dispositivo
  «Built-in Output» fijo).
- **Impacto**: UX: `tts-sidecar devices` en macOS no refleja los dispositivos reales.
  **Corrección**: implementar enumeración vía CoreAudio/AVFoundation o documentar la limitación.
- **Decisión requerida**: No.

## Orden de corrección recomendado

- **Fase 1 (desbloquear CI)**: CRITICAL-02 (NameError del build Linux) y CRITICAL-01
  (dependencias del daemon). Ambos gatean los jobs de CI; bajo esfuerzo, impacto máximo.
- **Fase 2 (robustez y coherencia)**: WARNING-03 (selección de snapshot), WARNING-04 (validez
  de voz), WARNING-02 (unificar provisión), WARNING-01 (ruta de artefacto en CI).
- **Fase 3 (limpieza)**: SUGGESTION-01…04 (metadatos, código muerto, comentario, UX macOS).

## Decisiones del propietario

Resueltas en la Fase 4 (resolución 1×1):

- **CRITICAL-01** → *Declarar en pyproject + espejo en requirements.* Añadir `fastapi`,
  `uvicorn[standard]` y `pydantic` (con pines) a `[project.dependencies]` de `pyproject.toml`
  y reflejarlos en la sección runtime de `requirements.txt`. Respeta la regla de fuente única.
- **WARNING-02** → *Reapuntar `install-model` a `tts-sidecar setup`.* Cambiar el script
  `install-model` de `package.json` para invocar el comando canónico `setup` y eliminar
  `scripts/install.py` (artefacto heredado; nada lo importa), dejando una sola vía de provisión.
- **WARNING-03** → *Leer `refs/main`.* Resolver la revisión apuntada por `refs/main` del repo
  cacheado y usar ese snapshot en `_download_model` (`engine.py:187`) e `is_model_cached`
  (`engine.py:624`), en lugar de `snapshots[0]`.

El resto de hallazgos (CRITICAL-02, WARNING-01, WARNING-04, SUGGESTION-02…03) son correcciones
evidentes que se llevan directas al plan sin decisión del propietario.

Decisiones emergentes resueltas durante la planificación (Fase 5):

- **SUGGESTION-01** → *Publicar el repo y fijar la URL real.* El repo local no tenía remote,
  así que la URL no era derivable: se decidió publicarlo como repo nuevo bajo el usuario
  `CristianRojas-SoftwareEngineer`, instalando GitHub CLI (`gh`) para automatizar la creación
  (`gh repo create`), y fijar `https://github.com/CristianRojas-SoftwareEngineer/tts-sidecar`
  en `package.json`.
- **SUGGESTION-04** → *Reusar `sounddevice`.* En vez de documentar la limitación o implementar
  CoreAudio, la rama macOS de `get_audio_devices` se unifica con la de Linux vía
  `sounddevice.query_devices()` (dependencia ya declarada, mismo patrón, diff mínimo).
  Verificación end-to-end pendiente de un entorno macOS real.
- **Alcance de tests** → *Tests dirigidos incluidos.* Perfil preventivo: se añaden
  `tests/test_voices.py`, `tests/test_engine_cache.py` y `tests/test_build_utils.py` para
  fijar el comportamiento corregido de WARNING-03/04 y CRITICAL-02.

## Confirmación en CI

- **CRITICAL-01**: probado por lectura (imports vs. manifiestos). El que el job `test` de CI
  pase o falle hoy depende de la resolución transitiva de `pydantic`/`fastapi`/`uvicorn`; se
  confirma revisando la salida de recolección de `pytest` en el job `test`.
- **CRITICAL-02**: probado por lectura (símbolo indefinido). Se confirma en los jobs
  `build-linux-x64` / `build-linux-arm64`, que abortarían en la etapa AppImage con `NameError`.
- **WARNING-01**: se confirma en el job `build-windows` tras un bump de versión, observando si
  `store_artifacts` encuentra el `.exe`.
