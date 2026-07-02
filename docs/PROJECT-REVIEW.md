# Revisión: Auditoría sistémica preventiva de tts-sidecar (tercera ronda)

## Resumen ejecutivo

Se auditó todo el repo bajo los lentes de corrección/bugs, seguridad, compatibilidad
multiplataforma, mantenibilidad/deuda técnica y UX/DX, con perfil de mantenimiento
**preventivo**. La ronda anterior (commit `518ff44`, índice eliminado en `7761aae`) se
verificó vigente sin regresión en las cuatro áreas revisadas. Esta ronda no encontró
defectos críticos: **0 críticos, 6 advertencias, 14 sugerencias**.

| ID | Título | Grupo | Área/plataforma | Decisión requerida |
|----|--------|-------|-----------------|--------------------|
| WARNING-01 | Selección no determinista de snapshot en fallback del voice encoder | Advertencia | Motor (todas las plataformas) | No |
| WARNING-02 | Asimetría de manejo de excepciones en enumeración de audio Linux/macOS | Advertencia | Audio (Linux/macOS) | No |
| WARNING-03 | `doctor`/`setup` en Linux/macOS solo verifican el import, no enumeración real | Advertencia | CLI (Linux/macOS) | No |
| WARNING-04 | TOCTOU en validación de rutas de `/synthesize` | Advertencia | Daemon (seguridad) | Sí |
| WARNING-05 | Subprocesos de PyInstaller sin timeout en los tres scripts de build | Advertencia | Build/CI (todas las plataformas) | No |
| WARNING-06 | Instalación de paquetes `pip` sin pin de versión en CI | Advertencia | CI | No |
| SUGGESTION-01 | Fallo silencioso en `load_precomputed_conditionals` | Sugerencia | Motor | No |
| SUGGESTION-02 | Constante mágica `emotion_adv` desacoplada de `EXAGGERATION` | Sugerencia | Motor | No |
| SUGGESTION-03 | `_cache` de clase sin lock en `get_instance` | Sugerencia | Motor | No |
| SUGGESTION-04 | `SoundDevicePlayer.play` asume PCM de 16 bits | Sugerencia | Audio | No |
| SUGGESTION-05 | `cmd_devices` sin manejo de excepciones | Sugerencia | CLI | No |
| SUGGESTION-06 | Riesgo de colisión de nombres de voz por case-folding | Sugerencia | Voces (Windows/macOS) | Sí |
| SUGGESTION-07 | `--text` acepta cadena vacía sin validación | Sugerencia | CLI | No |
| SUGGESTION-08 | Validación de audio en `/synthesize` solo por extensión, sin magic bytes | Sugerencia | Daemon | No |
| SUGGESTION-09 | Clave de caché de modelo hardcodeada y duplicada en `daemon/run.py` | Sugerencia | Daemon | No |
| SUGGESTION-10 | `daemon.py stop()` no verifica el status code de `/shutdown` | Sugerencia | Daemon | No |
| SUGGESTION-11 | Inconsistencia de manejo de JSON inválido entre métodos de `ipc.py` | Sugerencia | Daemon | No |
| SUGGESTION-12 | Bloque de código muerto tras `check=True` en build_utils.py/build_linux.py | Sugerencia | Build | No |
| SUGGESTION-13 | Cálculo de tamaño de bundle duplicado en los tres scripts de build | Sugerencia | Build | No |
| SUGGESTION-14 | `requirements.txt` documenta "pin" pero solo usa límites inferiores | Sugerencia | Dependencias (preexistente) | No |

## Hallazgos por grupo

### Advertencias

#### WARNING-01 — Selección no determinista de snapshot en fallback del voice encoder
- **Área/plataforma**: Motor, todas las plataformas
- **Evidencia**: `src/chatterbox_tts/engine.py:295-300`
- **Causa**: el fallback usa `os.listdir()[0]` en vez de `_resolve_cached_snapshot()` (ya
  implementada correctamente en `src/chatterbox_tts/model_cache.py:38-60` y usada en
  `engine.py:240`). El orden de `os.listdir()` no está garantizado por el sistema de archivos.
- **Impacto**: con múltiples snapshots cacheados del mismo modelo, puede cargarse un
  `ve.safetensors` incorrecto o desactualizado sin ningún error visible. Corrección parcial
  preexistente: el commit `6ddad78` arregló la construcción de la ruta de caché en esta misma
  zona pero dejó la selección de snapshot sin corregir.
- **Corrección(es) propuesta(s)**: reemplazar `os.listdir()[0]` por una llamada a
  `_resolve_cached_snapshot()`, igual que en `engine.py:240` (recomendada — reutiliza lógica ya
  correcta y probada, cero riesgo de diseño nuevo).
- **Decisión requerida**: No

#### WARNING-02 — Asimetría de manejo de excepciones en enumeración de audio Linux/macOS
- **Área/plataforma**: Audio, Linux/macOS
- **Evidencia**: `src/chatterbox_tts/audio.py:187-195` (rama Linux/macOS) vs. `160-182` (rama
  Windows)
- **Causa**: la rama Windows captura `Exception` genérica con fallback a "Default"; la rama
  Linux/macOS solo captura `ImportError`.
- **Impacto**: un `PortAudioError` u otro fallo de `sounddevice` en tiempo de enumeración no
  gestionado produce una excepción no controlada en Linux/macOS, en vez de degradar con
  fallback como en Windows.
- **Corrección(es) propuesta(s)**: ampliar el `except` de la rama Linux/macOS a `Exception`
  genérica con el mismo fallback a "Default" que Windows (recomendada — simetriza el
  comportamiento entre plataformas sin cambiar contrato).
- **Decisión requerida**: No

#### WARNING-03 — `doctor`/`setup` en Linux/macOS solo verifican el import, no enumeración real
- **Área/plataforma**: CLI, Linux/macOS
- **Evidencia**: `src/chatterbox_tts/cli.py:311-313`
- **Causa**: a diferencia de la corrección ya aplicada en Windows en la ronda anterior (WARNING-03
  de esa ronda, ya cerrada, que ahora invoca `audio.get_audio_devices()`), la rama Linux/macOS de
  `_environment_checks` sigue haciendo solo `import sounddevice` sin enumeración real de
  dispositivos.
- **Impacto**: un host Linux/macOS sin audio real (o sin PortAudio configurado) pasa `doctor`
  pero puede fallar en runtime al reproducir — misma clase de riesgo que la corrección de
  Windows de la ronda anterior, sin cubrir en las otras dos plataformas.
- **Corrección(es) propuesta(s)**: extender el mismo patrón ya aprobado para Windows (invocar la
  enumeración real de `audio.py`) a la rama Linux/macOS de `_environment_checks` (recomendada
  — consistencia directa con la corrección ya aprobada para Windows).
- **Decisión requerida**: No

#### WARNING-04 — TOCTOU en validación de rutas de `/synthesize`
- **Área/plataforma**: Daemon, seguridad
- **Evidencia**: `src/chatterbox_tts/daemon/server.py:85`
- **Causa**: la ruta se valida (extensión + directorio permitido, ya reforzado en la ronda
  anterior) y se lee en un momento posterior del flujo; existe una ventana entre check y uso.
- **Impacto**: en teoría, un symlink sustituido en esa ventana dentro de un directorio
  compartido podría burlar la restricción de directorio. Mitigado parcialmente por el bind a
  `127.0.0.1` (solo procesos locales pueden explotarlo).
- **Corrección(es) propuesta(s)**: (1) resolver la ruta canónica una sola vez y abrir el
  archivo inmediatamente después sin releer el path — reduce la ventana pero no la elimina
  del todo; (2) documentar el riesgo residual como aceptado dado el bind a loopback, sin
  cambio de código. Requiere decisión del propietario por el trade-off esfuerzo/riesgo
  residual.
- **Decisión requerida**: Sí — mitigar la ventana de carrera vs. documentar el riesgo aceptado

#### WARNING-05 — Subprocesos de PyInstaller sin timeout en los tres scripts de build
- **Área/plataforma**: Build/CI, todas las plataformas
- **Evidencia**: `scripts/build_windows.py:49-53`, `scripts/build_linux.py:74-78`,
  `scripts/build_macos.py:65-69`
- **Causa**: a diferencia de los subprocesos de empaquetado final (que sí usan
  `BUILD_SUBPROCESS_TIMEOUT=600` desde la consolidación de la ronda anterior), la etapa de
  PyInstaller —la más larga del build (9-15 min)— no tiene timeout.
- **Impacto**: un cuelgue en PyInstaller bloquearía el job de CI indefinidamente hasta el
  timeout global de CircleCI, consumiendo minutos de cómputo sin diagnóstico claro.
- **Corrección(es) propuesta(s)**: aplicar `timeout=BUILD_SUBPROCESS_TIMEOUT` (o uno mayor,
  acorde a la duración esperada de 9-15 min) al `subprocess.run` de PyInstaller en los tres
  scripts (recomendada — reutiliza la constante ya consolidada en `build_utils.py`).
- **Decisión requerida**: No

#### WARNING-06 — Instalación de paquetes `pip` sin pin de versión en CI
- **Área/plataforma**: CI
- **Evidencia**: `.circleci/config.yml:23,83,116,142`
- **Causa**: `pip install pytest`, `pip install pyinstaller appimage-builder`, y
  `pip3 install pyinstaller create-dmg` no fijan versión, mientras que la ronda anterior sí
  fijó Python (`choco install python313 --version=3.13.14`) e Inno Setup vía Chocolatey.
- **Impacto**: un release nuevo de cualquiera de estos paquetes puede romper el build sin
  cambios en el repo, la misma clase de riesgo que motivó el pin de Chocolatey en la ronda
  anterior, sin cubrir en pip.
- **Corrección(es) propuesta(s)**: fijar versión explícita (`==`) en las cuatro instalaciones
  de pip listadas (recomendada — mismo patrón ya aprobado para Chocolatey).
- **Decisión requerida**: No

### Sugerencias

#### SUGGESTION-01 — Fallo silencioso en `load_precomputed_conditionals`
- **Área/plataforma**: Motor
- **Evidencia**: `src/chatterbox_tts/engine.py:650-655`
- **Causa**: `except Exception: return False` sin log, a diferencia del fallback análogo en
  `speak()` (líneas 409-411) que sí registra.
- **Impacto**: dificulta diagnosticar por qué se recalculan condicionales en cada síntesis en
  vez de reutilizar los precomputados.
- **Corrección(es) propuesta(s)**: añadir logging del motivo del fallo antes del `return
  False`, igual que en `speak()`.
- **Decisión requerida**: No

#### SUGGESTION-02 — Constante mágica `emotion_adv` desacoplada de `EXAGGERATION`
- **Área/plataforma**: Motor
- **Evidencia**: `src/chatterbox_tts/engine.py:519`
- **Causa**: `emotion_adv=0.5` hardcodeado, sin relación explícita con
  `self.EXAGGERATION = 0.75` documentado en `CLAUDE.md`.
- **Impacto**: mantenibilidad — un cambio futuro en `EXAGGERATION` no propaga a este valor si
  hay una relación implícita entre ambos que no está documentada.
- **Corrección(es) propuesta(s)**: extraer a una constante de clase nombrada, o documentar
  explícitamente por qué el valor es independiente de `EXAGGERATION`.
- **Decisión requerida**: No

#### SUGGESTION-03 — `_cache` de clase sin lock en `get_instance`
- **Área/plataforma**: Motor
- **Evidencia**: `src/chatterbox_tts/engine.py:148-151`
- **Causa**: patrón check-then-act sobre un dict de clase compartido.
- **Impacto**: señal preventiva débil; el `_synthesis_lock` del daemon (`server.py:65,104`)
  mitiga la única vía de concurrencia real hoy. No es explotable en el flujo actual.
- **Corrección(es) propuesta(s)**: añadir un lock si en el futuro se habilita concurrencia
  real de instanciación; no urgente.
- **Decisión requerida**: No

#### SUGGESTION-04 — `SoundDevicePlayer.play` asume PCM de 16 bits
- **Área/plataforma**: Audio
- **Evidencia**: `src/chatterbox_tts/audio.py:136-137`
- **Causa**: no valida `wf.getsampwidth()` antes de reproducir.
- **Impacto**: un WAV con otro ancho de muestra se reproduciría con ruido o velocidad
  incorrecta sin error explícito.
- **Corrección(es) propuesta(s)**: validar `sampwidth` y lanzar un error claro si no es de 16
  bits, o adaptar el dtype de reproducción según el ancho real.
- **Decisión requerida**: No

#### SUGGESTION-05 — `cmd_devices` sin manejo de excepciones
- **Área/plataforma**: CLI
- **Evidencia**: `src/chatterbox_tts/cli.py:249-262`
- **Causa**: a diferencia de otros comandos del CLI, no envuelve la enumeración en
  `try/except`.
- **Impacto**: una excepción no capturada en `audio.py` produce un traceback crudo en vez de
  un mensaje accionable, inconsistente con el resto del CLI.
- **Corrección(es) propuesta(s)**: envolver en `try/except` con el mismo patrón de mensaje de
  error que usan los demás comandos.
- **Decisión requerida**: No

#### SUGGESTION-06 — Riesgo de colisión de nombres de voz por case-folding
- **Área/plataforma**: Voces, Windows/macOS (sistemas de archivos case-insensitive)
- **Evidencia**: `src/chatterbox_tts/voices.py:25,35`
- **Causa**: `_VOICE_NAME_RE`/`_validate_voice_name` no normalizan mayúsculas/minúsculas.
- **Impacto**: en sistemas de archivos case-insensitive, dos nombres que difieren solo en
  capitalización (`MiVoz` y `mivoz`) colisionarían en el mismo directorio. Hipótesis
  parcialmente verificada — el efecto exacto en `engine.add_voice` no se confirmó en runtime.
- **Corrección(es) propuesta(s)**: (1) normalizar a minúsculas en la validación/resolución de
  nombres, cerrando la colisión en las tres plataformas; (2) verificar primero el
  comportamiento real con un test de colisión antes de decidir la corrección, dado que el
  hallazgo es una hipótesis no confirmada. Requiere decisión del propietario porque implica
  verificar antes de normalizar.
- **Decisión requerida**: Sí — verificar el comportamiento real antes de decidir si normalizar

#### SUGGESTION-07 — `--text` acepta cadena vacía sin validación
- **Área/plataforma**: CLI
- **Evidencia**: `src/chatterbox_tts/cli.py:502`
- **Causa**: no hay validación explícita de `--text` vacío.
- **Impacto**: el comportamiento resultante del motor ante texto vacío no fue confirmado en
  runtime; hallazgo menor de UX.
- **Corrección(es) propuesta(s)**: validar y rechazar `--text ""` con un mensaje claro antes de
  invocar el motor.
- **Decisión requerida**: No

#### SUGGESTION-08 — Validación de audio en `/synthesize` solo por extensión, sin magic bytes
- **Área/plataforma**: Daemon
- **Evidencia**: `src/chatterbox_tts/daemon/server.py:89`
- **Causa**: solo se comprueba la extensión `.wav`, no los primeros bytes del archivo.
- **Impacto**: un archivo con extensión falsificada pasaría la validación y fallaría más
  adelante en el pipeline de audio con un error menos claro que un rechazo temprano.
- **Corrección(es) propuesta(s)**: verificar el header RIFF/WAVE al abrir el archivo, antes de
  pasarlo al motor.
- **Decisión requerida**: No

#### SUGGESTION-09 — Clave de caché de modelo hardcodeada y duplicada en `daemon/run.py`
- **Área/plataforma**: Daemon
- **Evidencia**: `src/chatterbox_tts/daemon/run.py:143`
- **Causa**: el string `"es-mx-latam:cpu:None"` duplica manualmente la lógica de construcción
  de clave que vive en `engine.py`.
- **Impacto**: si la lógica de clave cambia en `engine.py`, la clave del daemon queda
  desincronizada silenciosamente, invalidando el cacheo del modelo sin ningún error visible.
- **Corrección(es) propuesta(s)**: exponer una función compartida de construcción de clave en
  `engine.py` o `model_cache.py` y reutilizarla desde `run.py`.
- **Decisión requerida**: No

#### SUGGESTION-10 — `daemon.py stop()` no verifica el status code de `/shutdown`
- **Área/plataforma**: Daemon
- **Evidencia**: `src/chatterbox_tts/daemon/daemon.py:127-132`
- **Causa**: no se inspecciona el código de estado de la respuesta HTTP de `/shutdown`.
- **Impacto**: si el endpoint responde con un error, `stop()` no lo detecta y puede reportar
  éxito falso al usuario.
- **Corrección(es) propuesta(s)**: verificar `status_code` y propagar el fallo si no es 2xx.
- **Decisión requerida**: No

#### SUGGESTION-11 — Inconsistencia de manejo de JSON inválido entre métodos de `ipc.py`
- **Área/plataforma**: Daemon
- **Evidencia**: `src/chatterbox_tts/daemon/ipc.py:78-81` (synthesize) vs. `98-99`
  (list_voices)
- **Causa**: `synthesize()` captura `ValueError` en el parseo de la respuesta; `list_voices()`
  no.
- **Impacto**: una respuesta malformada del daemon produce una excepción no controlada en
  `list_voices()` pero no en `synthesize()`.
- **Corrección(es) propuesta(s)**: aplicar el mismo manejo de `ValueError` en `list_voices()`.
- **Decisión requerida**: No

#### SUGGESTION-12 — Bloque de código muerto tras `check=True` en build_utils.py/build_linux.py
- **Área/plataforma**: Build
- **Evidencia**: `scripts/build_utils.py:37-42`, replicado en `scripts/build_linux.py:33-38,46-51`
- **Causa**: el patrón `subprocess.run(..., check=True)` seguido de
  `if result.returncode != 0: sys.exit(1)` es inalcanzable — `check=True` ya lanza
  `CalledProcessError` antes de llegar a esa comprobación.
- **Impacto**: no es un bug funcional, pero es código muerto que sugiere un manejo de errores
  que en realidad no ocurre (el `sys.exit(1)` nunca se ejecuta con ese código de salida
  controlado; en su lugar el proceso termina por excepción no capturada).
- **Corrección(es) propuesta(s)**: eliminar el bloque `if result.returncode != 0` inalcanzable,
  o cambiar a `check=False` con manejo explícito si se prefiere un `sys.exit(1)` controlado.
- **Decisión requerida**: No

#### SUGGESTION-13 — Cálculo de tamaño de bundle duplicado en los tres scripts de build
- **Área/plataforma**: Build
- **Evidencia**: `scripts/build_windows.py:64-66`, `scripts/build_linux.py:85-90`,
  `scripts/build_macos.py:76-81`
- **Causa**: mismo bloque de `sum(f.stat().st_size for f in onedir.rglob("*") if f.is_file())`
  repetido en los tres scripts en vez de extraerse a `build_utils.py`.
- **Impacto**: mantenibilidad — la ronda anterior ya consolidó otras partes de estos mismos
  scripts en `build_utils.py`, dejando este bloque como duplicación residual.
- **Corrección(es) propuesta(s)**: extraer una función `bundle_size_mb(onedir)` a
  `build_utils.py` y reutilizarla en los tres scripts.
- **Decisión requerida**: No

#### SUGGESTION-14 — `requirements.txt` documenta "pin" pero solo usa límites inferiores
- **Área/plataforma**: Dependencias (preexistente)
- **Evidencia**: `requirements.txt:1,9-21`
- **Causa**: el comentario de cabecera afirma "Pin de dependencias" pero todas las entradas
  usan `>=` sin cota superior.
- **Impacto**: riesgo de cadena de suministro si una dependencia transitiva introduce un
  cambio incompatible. Preexistente y fuera del foco estricto de rondas anteriores.
- **Corrección(es) propuesta(s)**: (1) corregir el comentario para que refleje la política real
  (límites inferiores, no pines exactos); (2) evaluar fijar cotas superiores o usar un archivo
  de lock. Bajo prioridad dado que no es una regresión ni un hallazgo nuevo de comportamiento.
- **Decisión requerida**: No

## Orden de corrección recomendado

**Fase 1 (advertencias de seguridad y confiabilidad, bajo esfuerzo)**: WARNING-01, WARNING-02,
WARNING-03 — correcciones directas y acotadas en motor y audio multiplataforma.

**Fase 2 (decisión del propietario)**: WARNING-04 (TOCTOU) y SUGGESTION-06 (case-folding) —
requieren resolución 1×1 antes de plan.

**Fase 3 (CI/build, bajo esfuerzo, alto valor preventivo)**: WARNING-05, WARNING-06,
SUGGESTION-12, SUGGESTION-13 — agrupables por tocar los mismos archivos de `scripts/` y
`.circleci/config.yml`.

**Fase 4 (sugerencias de mantenibilidad y UX del daemon/CLI, independientes entre sí)**:
SUGGESTION-01, SUGGESTION-02, SUGGESTION-03, SUGGESTION-04, SUGGESTION-05, SUGGESTION-07,
SUGGESTION-08, SUGGESTION-09, SUGGESTION-10, SUGGESTION-11.

**Fase 5 (baja prioridad, preexistente)**: SUGGESTION-14.

## Decisiones del propietario

- **WARNING-04** (TOCTOU en `/synthesize`): **resuelto** — resolver la ruta canónica una sola
  vez y abrir el archivo inmediatamente después, sin releer el path. Reduce significativamente
  la ventana de carrera con un cambio acotado a `daemon/server.py`; no la elimina en sentido
  estricto (persiste una ventana ínfima entre `resolve()` y `open()`) ni defiende contra un
  atacante local con privilegios suficientes para manipular symlinks, pero es la mitigación
  proporcional dado el bind a `127.0.0.1`.
- **SUGGESTION-06** (case-folding en nombres de voz): **resuelto** — verificar primero con un
  test de colisión (crear dos voces que difieran solo en capitalización en un filesystem
  case-insensitive) antes de decidir si normalizar. Evita normalizar un comportamiento que
  podría no materializarse como se hipotetiza, generando evidencia confirmada antes de cambiar
  el comportamiento visible al usuario; si el test confirma el riesgo, la normalización a
  minúsculas se incorpora al plan de corrección en una iteración siguiente.

## Confirmación en CI

- WARNING-05 (timeout de PyInstaller) y WARNING-06 (pin de pip) se confirman al observar que
  un run de CI no cuelga indefinidamente y que las versiones instaladas coinciden con las
  fijadas, respectivamente — verificable en el próximo run de `.circleci/config.yml` tras
  aplicar la corrección.
- WARNING-02 y WARNING-03 (comportamiento multiplataforma de audio) ya están probados por
  lectura de código contra el patrón simétrico de Windows; su comportamiento real en
  Linux/macOS se confirmará cuando corran los jobs `build-linux-x64`, `build-linux-arm64` y
  `build-darwin-universal2` del CI tras aplicar la corrección.
