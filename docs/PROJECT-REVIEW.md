# Revisión: auditoría sistémica de tts-sidecar (segunda ronda · corrección · compatibilidad · mantenibilidad · seguridad)

## Resumen ejecutivo

Se auditó nuevamente todo el repositorio `tts-sidecar` bajo perfil **preventivo**, tras la
ronda anterior (commit `6ddad78`) que cerró `CRITICAL-01`, `WARNING-01`, `SUGGESTION-01/03/04`
del histórico. Se verificaron **las cinco correcciones previas vigentes, sin regresión**
(confirmado por lectura directa de `engine.py` y `daemon/run.py`); ese detalle no se repite
en este índice, que documenta únicamente los **hallazgos nuevos** de esta ronda. No se
detectó ningún defecto crítico. Se identificaron **4 advertencias** (una de seguridad en el
daemon, una de manejo de errores específico de Windows, una de diagnóstico de audio, y una de
cobertura de CI) y **7 sugerencias** de endurecimiento y mantenibilidad.

| ID | Título | Grupo | Área/plataforma | Decisión requerida |
|----|--------|-------|-----------------|--------------------|
| WARNING-01 | `remove_voice` no maneja `PermissionError` de Windows (archivos bloqueados) | Advertencia | voices.py / Windows | No |
| WARNING-02 | `/synthesize` acepta cualquier ruta `.wav` legible por el proceso, sin restricción de directorio | Advertencia | daemon/server.py / todas | Sí |
| WARNING-03 | `doctor`/`setup` no verifican el subsistema COM real de audio en Windows | Advertencia | cli.py / Windows | No |
| WARNING-04 | CI no ejecuta el chequeo de sintaxis (`py_compile`) documentado en `CLAUDE.md` | Advertencia | CI / todas | No |
| SUGGESTION-01 | `/shutdown` sin token ni confirmación adicional | Sugerencia | daemon/server.py | No |
| SUGGESTION-02 | `voice_audio`/`speech_audio` sin `max_length` en `protocol.py` | Sugerencia | daemon/protocol.py | No |
| SUGGESTION-03 | Posible carrera en `daemon.py start()` sin archivo de lock | Sugerencia | daemon/daemon.py | No |
| SUGGESTION-04 | CI instala paquetes Chocolatey sin pin de versión ni checksum | Sugerencia | .circleci/config.yml | No |
| SUGGESTION-05 | Script `sudo ln -sf` embebido en el instalador `.dmg` de macOS | Sugerencia | scripts/build_macos.py | No |
| SUGGESTION-06 | Duplicación de lógica de build entre los tres scripts por SO | Sugerencia | scripts/ | No |
| SUGGESTION-07 | Inconsistencia de `timeout` entre subprocesos de build hermanos | Sugerencia | scripts/ | No |

## Hallazgos por grupo

### Advertencias

#### WARNING-01 — `remove_voice` no maneja `PermissionError` de Windows (archivos bloqueados)
- **Área/plataforma**: `src/chatterbox_tts/voices.py`; Windows.
- **Evidencia**: `voices.py:104-106` llama a `shutil.rmtree` sin `try/except` local. En Windows,
  si `reference.wav`/`speech.wav` están abiertos por otro proceso (el daemon, un reproductor),
  lanza `PermissionError [WinError 32]`. La excepción sube y es capturada por el
  `except Exception as e` genérico de `cli.py:203`, que la reporta igual que un simple "nombre
  inválido" (`cli.py:189-205`).
- **Causa**: falta de manejo diferenciado de errores de I/O en `remove_voice`, y captura
  demasiado amplia en `cmd_voice_remove`.
- **Impacto**: en Windows, un intento legítimo de `voice remove` sobre una voz en uso falla con
  un mensaje que no distingue "nombre inválido" de "archivo bloqueado", dificultando el
  diagnóstico y la resolución (¿reintentar tras cerrar el daemon? ¿el nombre está mal escrito?).
- **Corrección(es) propuesta(s)**:
  1. *(recomendada)* Capturar `PermissionError`/`OSError` específicamente en `remove_voice` (o en
     `cmd_voice_remove`) y emitir un mensaje que indique que el archivo puede estar en uso
     (p. ej. por el daemon) y sugiera cerrarlo antes de reintentar.
- **Decisión requerida**: No — corrección evidente (diferenciar tipos de excepción).

#### WARNING-02 — `/synthesize` acepta cualquier ruta `.wav` legible por el proceso, sin restricción de directorio
- **Área/plataforma**: `src/chatterbox_tts/daemon/server.py`; todas las plataformas.
- **Evidencia**: `server.py:81-88` valida solo extensión `.wav` y `os.path.isfile(path)`; no hay
  allowlist de directorio (p. ej. restringir a `voices_root()` o a un directorio temporal
  conocido). Mitigante confirmado: `daemon/run.py:116` bindea el servidor a
  `host="127.0.0.1"` (no expuesto a la red), por lo que el riesgo queda acotado a procesos
  locales.
- **Causa**: la validación de `voice_audio`/`speech_audio` se diseñó para aceptar cualquier ruta
  del usuario (uso normal de `--voice-audio`/`--speech-audio` vía CLI), sin acotar el daemon a un
  subconjunto de directorios permitidos cuando la petición llega por IPC.
- **Impacto**: cualquier proceso local (o un error del propio usuario) puede hacer que el daemon
  lea y procese como referencia de voz un `.wav` arbitrario accesible al proceso del daemon,
  fuera del directorio de voces. No es lectura de contenido arbitrario (el resultado es audio
  sintetizado, no un volcado del archivo), pero sí es una superficie de acceso a archivos no
  prevista explícitamente.
- **Corrección(es) propuesta(s)**:
  1. *(elegida)* Restringir `voice_audio`/`speech_audio` recibidos por IPC a un directorio
     permitido (`voices_root()` y/o un directorio temporal de la sesión), rechazando rutas fuera
     de él.
  2. *(descartada)* Documentar el riesgo como aceptado dado el bind a loopback y dejar la
     validación actual.
- **Decisión requerida**: Resuelta — ver «Decisiones del propietario» (se restringe a directorio
  permitido).

#### WARNING-03 — `doctor`/`setup` no verifican el subsistema COM real de audio en Windows
- **Área/plataforma**: `src/chatterbox_tts/cli.py`; Windows.
- **Evidencia**: `cli.py:280-298` (`_environment_checks`) solo ejecuta `import pycaw` para dar
  PASS en el chequeo de audio de Windows, sin instanciar ningún objeto COM. En contraste,
  `audio.py:158-179` (`get_audio_devices`) sí tolera fallos COM en runtime y degrada
  silenciosamente a un dispositivo por defecto (`{"id": 0, "name": "Default"}`).
- **Causa**: el chequeo de `doctor`/`setup` se implementó como una verificación de import, no
  como una verificación funcional equivalente a la que ya existe en `audio.py`.
- **Impacto**: un host sin audio real (sesión RDP sin redirección, servidor headless) puede pasar
  `tts-sidecar doctor`/`setup` con PASS y solo descubrir el problema más tarde, en runtime, con
  degradación silenciosa a un dispositivo por defecto en vez de un diagnóstico claro.
- **Corrección(es) propuesta(s)**:
  1. *(recomendada)* Reusar en `_environment_checks` la misma lógica de fallback/verificación COM
     de `get_audio_devices` para que `doctor` reporte el estado real del subsistema de audio, no
     solo la disponibilidad del import.
- **Decisión requerida**: No — alinear `doctor` con el comportamiento ya implementado en
  `audio.py`.

#### WARNING-04 — CI no ejecuta el chequeo de sintaxis (`py_compile`) documentado en `CLAUDE.md`
- **Área/plataforma**: `.circleci/config.yml`; todas las plataformas.
- **Evidencia**: `CLAUDE.md` documenta `python -m py_compile src/chatterbox_tts/engine.py` y
  `cli.py` como comando común de verificación, pero el job `test` de `.circleci/config.yml`
  (líneas 8-26) solo ejecuta `pytest tests/ -v`; el paso de `py_compile` no aparece en ningún job.
- **Causa**: el chequeo se documentó como práctica de desarrollo local pero no se trasladó al
  pipeline de CI.
- **Impacto**: bajo dado que `pytest` ya ejercita la mayoría del código, pero un error de sintaxis
  en un módulo sin cobertura de tests (o importado de forma condicional) podría no detectarse
  hasta el build de PyInstaller, más costoso de diagnosticar que un `py_compile` temprano.
- **Corrección(es) propuesta(s)**:
  1. *(recomendada)* Añadir un paso de `py_compile` (o `python -m compileall src/`) al job `test`
     de CI, antes o junto a `pytest`.
- **Decisión requerida**: No.

### Sugerencias

#### SUGGESTION-01 — `/shutdown` sin token ni confirmación adicional
- **Evidencia**: `daemon/server.py:130-142`; cualquier POST local apaga el daemon sin control
  adicional. Riesgo bajo dado el bind a `127.0.0.1` (`daemon/run.py:116`).
- **Impacto**: bajo, acotado a procesos locales; **Corrección**: opcional, un token compartido
  simple si en algún momento se contempla exponer el daemon más allá de loopback.
- **Decisión requerida**: No.

#### SUGGESTION-02 — `voice_audio`/`speech_audio` sin `max_length` en `protocol.py`
- **Evidencia**: `daemon/protocol.py:20-21`; a diferencia de `text` (`max_length=5000`,
  línea 19), estos campos no tienn límite de longitud.
- **Impacto**: bajo. **Corrección**: añadir `max_length` razonable (p. ej. 260-4096 caracteres,
  acorde a límites de ruta del SO) por consistencia con el resto del modelo.
- **Decisión requerida**: No.

#### SUGGESTION-03 — Posible carrera en `daemon.py start()` sin archivo de lock
- **Evidencia**: `daemon.py:36-98`; no hay archivo de lock ni verificación atómica entre el
  check `is_running()` (línea 46) y el lanzamiento del proceso (líneas 76-91). *Hipótesis no
  confirmada en runtime*: dos invocaciones concurrentes de `daemon start` podrían ambas pasar el
  check y lanzar procesos que compitan por el mismo puerto.
- **Impacto**: bajo, ventana estrecha y uso típico es de un solo usuario invocando `daemon start`
  manualmente. **Corrección**: opcional, un archivo de lock (`fcntl`/`msvcrt` o librería
  multiplataforma) si se detecta el problema en la práctica.
- **Decisión requerida**: No.

#### SUGGESTION-04 — CI instala paquetes Chocolatey sin pin de versión ni checksum
- **Evidencia**: `.circleci/config.yml:34,42` — `choco install python313 -y`,
  `choco install innosetup -y`, sin pin de versión exacta ni verificación de checksum/firma.
- **Impacto**: riesgo de supply-chain de bajo-medio impacto (interpretación: depende de la
  confianza depositada en el repositorio de Chocolatey). **Corrección**: pin de versión explícito
  y, si Chocolatey lo soporta, verificación de checksum.
- **Decisión requerida**: No.

#### SUGGESTION-05 — Script `sudo ln -sf` embebido en el instalador `.dmg` de macOS
- **Evidencia**: `scripts/build_macos.py:189-211` (`_path_install_script`) genera un script que
  usa `sudo ln -sf`, empaquetado en el `.dmg` y ejecutado en la máquina del usuario final (no en
  CI).
- **Impacto**: no es un riesgo del pipeline en sí, pero es una superficie de escalamiento de
  privilegios que vale la pena que el equipo revise explícitamente. **Corrección**: opcional,
  documentar la necesidad de `sudo` en el instalador o evaluar alternativas sin privilegios
  elevados (p. ej. añadir al PATH del usuario en vez de un symlink en `/usr/local/bin`).
- **Decisión requerida**: No.

#### SUGGESTION-06 — Duplicación de lógica de build entre los tres scripts por SO
- **Evidencia**: listas de flags `--collect-all`/`--exclude-module` de PyInstaller casi
  idénticas en `build_windows.py:48-90`, `build_linux.py:74-112`, `build_macos.py:65-102`; y
  `check_dependencies` reimplementado en cada script en vez de centralizarse en
  `scripts/build_utils.py`.
- **Impacto**: cada cambio de dependencia empaquetada requiere editar 3 archivos en sincronía,
  con riesgo de que diverjan. **Corrección**: extraer la lista de flags de PyInstaller y
  `check_dependencies` a `build_utils.py` como fuente única, parametrizada por SO donde
  corresponda.
- **Decisión requerida**: No.

#### SUGGESTION-07 — Inconsistencia de `timeout` entre subprocesos de build hermanos
- **Evidencia**: `create_installer_windows.py:206` define `timeout=600` en su `subprocess.run`;
  `build_linux.py:151-156` (`appimage-builder`) y `build_macos.py:166-180` (`create-dmg`) no
  definen ningún timeout.
- **Impacto**: bajo; un build colgado en Linux/macOS no tiene el mismo corte automático que en
  Windows. **Corrección**: añadir `timeout=600` (o valor equivalente) a los subprocesos de
  `build_linux.py`/`build_macos.py` por consistencia.
- **Decisión requerida**: No.

## Orden de corrección recomendado

- **Fase 1 (seguridad y confiabilidad)**: WARNING-02 (validación de rutas en `/synthesize`,
  requiere decisión) y WARNING-01 (manejo de errores de Windows en `remove_voice`) — impacto en
  seguridad/confiabilidad, bajo esfuerzo.
- **Fase 2 (diagnóstico y CI)**: WARNING-03 (chequeo real de audio en `doctor`) y WARNING-04
  (`py_compile` en CI) — cierran brechas de detección temprana.
- **Fase 3 (endurecimiento del daemon)**: SUGGESTION-01, SUGGESTION-02, SUGGESTION-03.
- **Fase 4 (mantenibilidad y supply-chain de build)**: SUGGESTION-04, SUGGESTION-05,
  SUGGESTION-06, SUGGESTION-07 — sin urgencia, agrupables en una limpieza de scripts.

## Decisiones del propietario

Un solo hallazgo requería decisión del propietario: **WARNING-02**. Resuelto: se prioriza la
seguridad sobre la flexibilidad actual — **restringir `voice_audio`/`speech_audio` recibidos por
IPC a un directorio permitido** (`voices_root()` y/o un directorio temporal de sesión conocido),
rechazando rutas fuera de él. Se acepta como costo el posible impacto en flujos que hoy pasan
rutas arbitrarias vía `--voice-audio`/`--speech-audio` a través del daemon; la corrección deberá
contemplar cómo esas rutas externas llegan a un directorio permitido (copia o registro explícito)
antes de ser aceptadas por `/synthesize`. El resto de los hallazgos de esta ronda son
correcciones directas y de bajo riesgo.

Del histórico previo (rondas anteriores), quedan confirmados sin regresión (no requieren nueva
decisión): `CRITICAL-01` (reuso de snapshot cacheado para modelos no `es-mx-latam`,
`engine.py:248-250`), `WARNING-01` (invalidación de caché de instancia en `--auto-restart`,
`daemon/run.py:143`), `SUGGESTION-01` (ruta del voice-encoder consolidada,
`engine.py:294-300`), `SUGGESTION-03` (comentario sobre handlers de señal,
`daemon/run.py:76-79`) y `SUGGESTION-04` (traducción de alias redundante eliminada,
`engine.py:234-263`).

## Confirmación en CI

- **WARNING-04**: una vez agregado el paso de `py_compile` a `.circleci/config.yml`, confirmar
  que el job `test` lo ejecute y falle ante un error de sintaxis introducido deliberadamente en
  una rama de prueba.
- **WARNING-01**: confirmar reproduciendo en Windows: abrir `speech.wav` de una voz de usuario
  (p. ej. reproduciéndolo) y ejecutar `voice remove` sobre esa voz mientras el archivo está en
  uso; verificar que el mensaje de error distinga el bloqueo de un nombre inválido tras la
  corrección.
- **WARNING-02**: si se opta por restringir el directorio permitido, confirmar con una petición
  `/synthesize` que use una ruta fuera de `voices_root()` y verificar que sea rechazada con
  `400`.
