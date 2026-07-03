# Auditoría de Preparación para Distribución — `tts-sidecar` (segunda ronda)

## Introducción

Este documento es el reporte completo de la **segunda auditoría integral** de
preparación para producción del proyecto `tts-sidecar`, realizada desde cero el
2026-07-03, sobre el estado del repositorio en el commit `8a18fad`. Su objetivo
es determinar qué tan listo está el producto para ser **publicado, empaquetado y
distribuido** como proyecto Open Source (GPL-3.0-or-later) con soporte
multiplataforma (Windows x86_64, Linux x86_64/aarch64, macOS arm64) y
experiencia de usuario equivalente en los tres sistemas operativos.

### Postura de la auditoría

Adversarial-constructiva: el objetivo no es confirmar que el proyecto está bien,
sino encontrar lo que impediría, degradaría o avergonzaría el release. Cada
afirmación de la documentación se verificó contra el código como hipótesis, no
como hecho dado.

### Punto de partida

Esta auditoría **no repite** las anteriores; asume sus cierres como base:

- Dos auditorías de equivalencia de UX entre SO (cerradas en `df43eca` y `a0a77cc`).
- El gate de release completo de la primera auditoría PROJECT-REVIEW
  (`c599dbd`): R-01…R-37 resueltos.
- Los 11 hallazgos menores post-gate (`8a18fad`): todos cerrados excepto R-38
  (firma de artefactos), reserva conocida y documentada.

La suite de tests se ejecutó durante la auditoría: **185/185 tests pasan**.

### Alcance

| Capa | Archivos evaluados |
|------|-------------------|
| **Código fuente** | `src/chatterbox_tts/*.py` (cli.py, engine.py, audio.py, voices.py, paths.py, timing.py, model_cache.py, daemon/*) y `bin/tts-sidecar` |
| **Scripts de build** | `scripts/build_windows.py`, `build_linux.py`, `build_macos.py`, `build_utils.py`, `create_installer_windows.py`, `clean_build.py` |
| **CI** | `.circleci/config.yml` (3 jobs de test + 4 de build) |
| **Dependencias** | `pyproject.toml`, `requirements.txt`, `requirements-lock.txt`, `package.json` |
| **Documentación** | `README.md`, `USAGE.md`, `docs/GOAL.md`, `DESIGN.md`, `ARCHITECTURE.md`, `DAEMON-MODE.md`, `BUILD.md` |
| **Gobernanza y licencias** | `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `THIRD-PARTY-LICENSES.md` |
| **Tests** | `tests/*.py` (185 tests; ejecución completa + mapeo de cobertura) |

### Convenciones

- Hallazgos con código `N-XX` (Nueva serie, para no colisionar con los `R-XX`
  de la primera auditoría).
- Severidad: **Bloqueante** (impide el release o rompe el caso de uso central),
  **Mayor** (degradaría la primera impresión o el soporte), **Menor** (pulido).
- Cada hallazgo incluye evidencia (archivo:línea), escenario concreto de usuario
  o integrador que lo sufre, propuesta de solución y tradeoffs.

---

## Tabla de Contenido

1. [Pipeline de build y empaquetado](#dimensión-1--pipeline-de-build-y-empaquetado)
2. [Contrato programático](#dimensión-2--contrato-programático)
3. [Daemon](#dimensión-3--daemon)
4. [Modelo, estado en disco y ciclo de vida de los datos](#dimensión-4--modelo-estado-en-disco-y-ciclo-de-vida-de-los-datos)
5. [Instalación/desinstalación end-to-end y equivalencia entre SO](#dimensión-5--instalacióndesinstalación-end-to-end-y-equivalencia-entre-so)
6. [Tests y CI](#dimensión-6--tests-y-ci)
7. [Gobernanza de release, licenciamiento y cadena de suministro](#dimensión-7--gobernanza-de-release-licenciamiento-y-cadena-de-suministro)
8. [Tabla resumen de hallazgos](#tabla-resumen-de-hallazgos)
9. [Gate mínimo de release](#gate-mínimo-de-release)
10. [Recomendación global](#recomendación-global)

---

## Dimensión 1 — Pipeline de build y empaquetado

### Veredicto **[NO LISTO]** (por N-01)

Qué está production-ready: los pines con SHA-256 del tooling AppImage
(`build_utils.py:56-77`, verificados por `fetch_pinned_asset`), el lockfile
universal con hashes instalado con `--require-hashes` en CI y builds, los
timeouts en todos los subprocesos de empaquetado, los smoke tests del binario
congelado en los 4 jobs de build, la degradación con gracia cuando falta el
empaquetador (el onedir sigue siendo usable), y la fuente única de flags de
PyInstaller (`common_pyinstaller_args`) compartida por las tres plataformas.

### Hallazgos

#### N-01 — El instalador de Windows nunca se genera: `main()` quedó truncada

| | |
|---|---|
| **Severidad** | **Bloqueante** |
| **Evidencia** | `scripts/create_installer_windows.py:165-223` (main truncada) y `225-315` (bloque de compilación inalcanzable) |

Al insertar `info_after_text()` (cierre de R-34, commit `8a18fad`), la función
se definió **en medio del cuerpo de `main()`**, partiéndolo en dos:

- `main()` termina ahora en la línea 223 (`output_dir.mkdir(...)`): valida
  argumentos, localiza ISCC… y retorna sin compilar nada.
- El bloque que escribe el `.iss`, invoca ISCC y reporta el instalador (líneas
  256-315) quedó anidado dentro de `info_after_text()` **después de su
  `return`**: código inalcanzable. Verificado por AST: `main` abarca 165-223;
  `info_after_text` 225-315 con el `Try` de compilación tras el `Return`.

Consecuencias en cadena:

1. `main()` sale con código 0 → `build_windows.py:91` loguea **«Instalador
   creado correctamente»** sin que exista ningún `.exe`. Éxito falso.
2. El CI no lo atrapa de forma fiable: el step `Stage installer artifact` usa
   `Copy-Item dist/tts-sidecar-*-setup.exe` en PowerShell, donde un wildcard
   sin coincidencias emite un error *no terminante* que puede salir con
   código 0.
3. Los tests no lo detectan: `tests/test_create_installer_windows.py` solo
   ejercita las funciones puras (`generate_iss`, `info_after_text`), que siguen
   funcionando; nunca el flujo de `main()`.

**Escenario**: no existe instalador de Windows que distribuir; el canal de
instalación principal del SO mayoritario está roto desde el commit que
«cerraba los hallazgos menores».

**Propuesta**: mover el bloque 256-315 de vuelta al final de `main()` (con su
indentación original), añadir un test que ejercite `main()` con ISCC mockeado
(monkeypatch de `get_inno_setup_path` + `subprocess.run`) verificando que se
genera e invoca el `.iss`, y endurecer el step de staging del CI
(`$ErrorActionPreference='Stop'` o `if (-not (Test-Path ...)) { throw }`).

**Tradeoffs**: ninguno relevante; es una restauración. El test de `main()`
exige mockear más superficie, pero es exactamente la clase de test cuya
ausencia dejó pasar esta regresión.

#### N-05 — AppImage x86_64 con el stack CUDA completo; tamaños declarados contradictorios

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `requirements-lock.txt` (41 paquetes `nvidia-*` para `sys_platform == 'linux'`), `USAGE.md:506` («varios cientos de MB»), `docs/BUILD.md:302` («~1.7 GB sin comprimir») |

El lock universal resuelve el stack CUDA completo en Linux x86_64;
`--collect-all torch` lo arrastra al bundle. El AppImage cargará gigabytes de
librerías CUDA que un usuario CPU-only jamás usa, mientras la documentación
declara dos números distintos e incompatibles entre sí.

**Escenario**: un usuario Linux con laptop sin GPU descarga un artefacto
multi-GB para un producto cuyo caso de uso principal declarado es CPU; la
primera impresión de descarga queda comprometida y el claim de USAGE es falso.

**Propuesta**: medir el AppImage real generado por CI; decidir explícitamente
entre (a) lockear torch desde el índice CPU de PyTorch para el build Linux
(artefacto mucho más pequeño; `--compute-backend cuda` deja de funcionar en
Linux) o (b) mantener CUDA y documentar el peso real y su porqué en
README/USAGE/BUILD.

**Tradeoffs**: (a) contradice la opción `--compute-backend cuda` documentada —
habría que retirarla del build Linux o publicar dos variantes; (b) conserva la
funcionalidad al costo de una descarga pesada. Cualquiera de las dos es
defendible; lo indefendible es la contradicción documental actual.

#### N-06 — Baseline de glibc del binario Linux ni validada ni documentada

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `.circleci/config.yml:131-133` (`cimg/python:3.13`, base Ubuntu 22.04) y `169-171` (`ubuntu-2204`); glibc 2.35 |

Un binario PyInstaller no corre en distros con glibc anterior a la del host de
build (Debian 11, RHEL 8, Ubuntu 20.04). El criterio 2 de GOAL.md («funciona en
distribuciones principales») no es alcanzable sin declarar el requisito mínimo.

**Escenario**: un usuario de Debian 11 descarga el AppImage y recibe
`GLIBC_2.35 not found` — un error críptico sin mención en la documentación ni
en la solución de problemas de USAGE.

**Propuesta**: documentar «requiere glibc ≥ 2.35 (Ubuntu 22.04+, Debian 12+,
Fedora 36+)» en README/USAGE, o mover el build a una base más vieja si se
quiere ampliar el rango.

**Tradeoffs**: documentar es gratis pero restringe el claim de GOAL; construir
sobre una base más vieja amplía compatibilidad al costo de mantener una imagen
de build distinta de la de tests.

#### N-07 — `LSMinimumSystemVersion=12.0` sin respaldo del toolchain

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `scripts/build_macos.py:299` (declara 12.0); `.circleci/config.yml:211-227` (CPython compilado por pyenv en runner Xcode 26.4) |

El CPython que se empaqueta lo compila pyenv en el runner, con el
`MACOSX_DEPLOYMENT_TARGET` del SDK del runner (muy posterior a macOS 12). El
Info.plist promete un mínimo que el toolchain no garantiza.

**Escenario**: un usuario de macOS 12/13 instala el `.dmg` que declara soportar
su sistema y recibe un crash de símbolos (`Symbol not found`) al primer
arranque.

**Propuesta**: fijar `MACOSX_DEPLOYMENT_TARGET` en el job de build (y verificar
que los wheels lo respeten), o subir `LSMinimumSystemVersion` a la versión
realmente soportada por el toolchain y actualizar GOAL/README. Coherente con el
criterio 3 de GOAL.md (validación E2E pendiente), pero el claim del plist va
más allá de lo validado.

**Tradeoffs**: sin hardware de prueba viejo, la opción honesta es alinear el
claim con el runner; recuperar macOS 12 real exigiría compilar CPython y
dependencias con target 12.0, trabajo significativo.

---

## Dimensión 2 — Contrato programático

### Veredicto **[LISTO CON RESERVAS]**

Qué está production-ready: el mapa de exit codes congelado y testeado
(`cli.py:33-41`; `test_cli.py` cubre los 7 códigos), `schema_version` en todos
los payloads JSON (R-07 cerrado de verdad), stdout/stderr forzados a UTF-8
(`cli.py:756-759`), y la separación datos/diagnóstico en los comandos de
lectura (`timing.py` emite todo a stderr). Es un contrato real, no aspiracional.

### Hallazgos

#### N-03 — `cleanup` es inusable desde otro proceso

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `cli.py:680` (`input()` sin flag de confirmación); `cli.py:892-900` (`main()` solo captura `KeyboardInterrupt`) |

No existe `--yes`/`--force`, y `EOFError` no se captura en ninguna parte.
Invocado vía `subprocess` con stdin cerrado — el caso de uso central del
producto — `input()` lanza `EOFError` → traceback crudo y exit 1
indistinguible de cualquier error.

**Escenario**: un desinstalador o script de mantenimiento intenta automatizar
el paso 1 de la «Desinstalación completa» documentada en USAGE.md
(`cleanup --all`) y obtiene un traceback.

**Propuesta**: añadir `--yes` que omita la confirmación, y capturar `EOFError`
en la confirmación tratándolo como cancelación limpia («Cancelado: no se borró
nada»).

**Tradeoffs**: ninguno; `--dry-run` ya existe como complemento natural.

#### N-09 — El ciclo de vida del daemon imprime progreso por stdout

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `daemon/daemon.py:55,121,152-155,192-199` (`print()` sin `file=sys.stderr`) |

«Esperando que el daemon esté listo (timeout=120.0s)...», «Daemon listo»,
«Daemon ya está corriendo», «Deteniendo daemon...» van a stdout, violando el
contrato del docstring de cli.py (diagnósticos a stderr).

**Escenario**: un orquestador que capture stdout de `daemon start` para
confirmar el arranque recibe ruido de progreso mezclado con la confirmación.

**Propuesta**: redirigir los mensajes de progreso de `DaemonManager` a stderr,
dejando en stdout solo las confirmaciones de resultado de `cmd_daemon`.

#### N-11 — Tres semánticas de límite de texto según el estado del daemon

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `daemon/protocol.py:10` (hard limit 5000), `cli.py:150` (warning 2000), sin límite en modo directo |

Directo: ilimitado con warning >2000. Vía daemon: >5000 → 422 de pydantic cuyo
detalle llega como `DaemonIPCError` con el JSON de validación crudo, y con
**exit 5** («daemon inalcanzable») cuando la causa real es entrada inválida
(exit 4).

**Escenario**: el mismo `speak --text <6000 chars>` devuelve exit 0 con
truncamiento, o exit 5 con un JSON críptico, según haya un daemon corriendo.

**Propuesta**: validar la longitud en el CLI antes del despacho (mismo límite
que el daemon, exit 4), dejando el límite del daemon como defensa en
profundidad.

---

## Dimensión 3 — Daemon

### Veredicto **[LISTO CON RESERVAS]**

Qué está production-ready: bind exclusivo a loopback (`run.py:132`), validación
de rutas con canonicalización única sin ventana TOCTOU (`server.py:85-117`),
lock de síntesis que evita el cruce de voces (`server.py:65`), endpoint
síncrono despachado al threadpool (health responde durante síntesis, con test),
kill por PID solo tras verificar el cmdline propio (`daemon.py:224-236`, con
test), y modelo de amenaza documentado con honestidad en SECURITY.md.

### Hallazgos

#### N-02 — La sandbox de rutas del daemon rompe el ejemplo documentado de `--voice-audio`

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `server.py:99-106` (solo `voices_root`, `factory_voices_root` y tempdir); `USAGE.md:273` (ejemplo con audios del directorio del usuario); restricción ausente en USAGE.md y DAEMON-MODE.md |

USAGE documenta `speak --text "Hola" --voice-audio timbre.wav --speech-audio
condicion.wav` con archivos del directorio de trabajo del usuario — y **con un
daemon activo, el sondeo automático enruta ese comando al daemon**, que
responde 400 «la ruta no está en un directorio permitido». El mismo comando
funciona con `--no-daemon`.

**Escenario**: el usuario sigue el flujo recomendado (`daemon start` →
`speak --voice-audio ...`) y recibe un error inexplicable que desaparece
«mágicamente» al apagar el daemon. El error no menciona ni la causa ni la
salida.

**Propuesta**: (a) documentar la restricción en USAGE/DAEMON-MODE, (b) mejorar
el mensaje de error del cliente con las alternativas («registra la voz con
`voice add`, usa `--no-daemon`, o coloca el audio en el directorio de voces»),
y (c) opcionalmente, que el CLI detecte el caso antes del despacho (ruta fuera
de los directorios permitidos + daemon activo → modo directo o error
accionable).

**Tradeoffs**: relajar la sandbox reabriría WARNING-02 (lectura arbitraria del
FS por procesos locales); la dirección correcta es documentar + degradar con
un mensaje accionable, no ampliar la superficie.

#### N-13 — Ventana ciega de 30-90 s durante la carga del modelo

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `run.py:84-139` (el modelo se carga **antes** del bind del puerto); `daemon.py:117-121` (stop sin puerto → «no está corriendo») |

En esa ventana, `daemon status` dice «no está en ejecución», `daemon stop`
reporta éxito sin matar nada (no hay puerto que resolver a PID y no hay PID
file), y el daemon aparece después.

**Escenario**: un orquestador que haga start→(timeout)→stop→start puede acabar
con dos procesos compitiendo por el puerto.

**Propuesta**: escribir un PID file al arrancar `serve` (antes de cargar el
modelo) y que `stop`/`status` lo consulten como segunda fuente. Complementa la
carrera start-start ya aceptada (SUGGESTION-03).

**Tradeoffs**: introduce el archivo de estado multiplataforma que la primera
auditoría evitó; la alternativa mínima es documentar la ventana en
DAEMON-MODE.md.

#### N-10 — `--compute-backend` se ignora en silencio vía daemon

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `daemon/protocol.py:22-24` (la petición no lleva backend, por diseño); `USAGE.md:259` («lo usa durante toda la sesión», sin la excepción del daemon) |

**Escenario**: `speak --compute-backend cuda` con daemon CPU activo sintetiza
en CPU sin ningún aviso.

**Propuesta**: warning por stderr cuando se pasa `--compute-backend` explícito
y la síntesis va vía daemon; nota en USAGE.

---

## Dimensión 4 — Modelo, estado en disco y ciclo de vida de los datos

### Veredicto **[LISTO]**

Qué está production-ready: gate `is_model_cached` con validación del header
safetensors (caché truncada detectada; R-04 cerrado con tests), provisión
explícita de `ve.safetensors` (R-12), resolución determinista de snapshots
(refs/main → mtime), `cleanup` quirúrgico con defensa en profundidad
(`models--ResembleAI--*`), `setup --force-update` (R-13), pre-chequeo de disco
con ascenso al primer ancestro existente (R-14), y respeto de
`HF_HUB_CACHE`/`HF_HOME` delegando en `huggingface_hub.constants` (R-10).

### Hallazgos

#### N-17 — `setup` carga el modelo completo en RAM cuando solo necesita descargarlo

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `cli.py:612-613` (`ChatterboxEngine.get_instance(...)` como mecanismo de descarga) |

**Escenario**: en la máquina de 4 GB que USAGE declara como mínimo, la
provisión puede paginar o fallar cuando un `snapshot_download` habría bastado.

**Propuesta**: en `cmd_setup`, descargar con `snapshot_download` +
`hf_hub_download` (ve.safetensors) sin instanciar el motor; `doctor`/primer
`speak` validan la carga real.

**Tradeoffs**: se pierde la verificación implícita de que el modelo *carga*
(no solo existe) al terminar setup; se compensa parcialmente con el chequeo de
header ya existente.

#### N-16 — Actualización de versión sin documentar; symlink AppImage apunta a la versión vieja

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `cli.py:472-501` (symlink a la ruta absoluta de `$APPIMAGE`); USAGE.md sin sección de actualización |

**Escenario**: el usuario Linux descarga `tts-sidecar-0.2.0-x86_64.AppImage`;
`~/.local/bin/tts-sidecar` sigue apuntando al 0.1.0 hasta re-ejecutar `setup`
desde el nuevo archivo. En Windows el upgrade in-place funciona (AppId fijo);
en macOS, re-arrastrar el .app + re-ejecutar el .command. Nada de esto está
documentado.

**Propuesta**: sección «Actualizar de versión» en USAGE con los tres caminos;
en Linux, mencionar que `setup` del nuevo AppImage re-apunta el symlink.

---

## Dimensión 5 — Instalación/desinstalación end-to-end y equivalencia entre SO

### Veredicto **[PARCIALMENTE LISTO]**

Qué está production-ready: el diseño de paridad es genuino — PATH en los tres
SO con reversión testeada (Inno `[Code]`, symlink `--remove-path`, `.command`
de desinstalación), consola persistente post-instalación (`cmd /k` /
Terminal), oferta de `setup` en la instalación de los tres SO, naming
`uname -m` unificado, y la ruta de desinstalación completa documentada en
USAGE.md:402-413.

### Hallazgos

- **N-01** deja a Windows sin instalador (ver Dimensión 1): el recorrido
  usuario-nuevo → descarga → instala no puede ni empezar en Windows.

#### N-08 — La página InfoAfter afirma incluir el código fuente (falso), con typo y referencia a archivo inexistente

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `create_installer_windows.py:249-251`: «El instalador incluye el código fuente accompanido (ver LICENSE.txt junto a este programa)» |

Tres defectos en una frase: el bundle **no** incluye el código fuente (incluye
`LICENSE` y `THIRD-PARTY-LICENSES.md`); el archivo se llama `LICENSE`, no
`LICENSE.txt`; y «accompanido» es un typo visible para todo usuario. La
obligación GPLv3 §6 queda cubierta por el enlace al repositorio (§6d), pero el
texto debe decir eso, no afirmar algo falso.

**Propuesta**: reescribir el párrafo: «El código fuente completo está
disponible públicamente bajo GPLv3 en el repositorio: …» y corregir la
referencia a `LICENSE`.

#### N-12 — `--output` a un directorio inexistente: directo crea, daemon falla

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `engine.py:621` (`_save_wav` hace `mkdir(parents=True)`) vs `cli.py:91` (`_emit_audio` abre sin crear) |

**Escenario**: `speak --output out/nuevo/a.wav` funciona sin daemon y devuelve
exit 3 con daemon.

**Propuesta**: `_emit_audio` debe crear los padres igual que `_save_wav`
(o ambos deben rechazar igual; lo importante es la simetría).

---

## Dimensión 6 — Tests y CI

### Veredicto **[LISTO CON RESERVAS]**

Qué está production-ready: 185 tests verdes, triple puerta nativa
(test-linux/test-windows/test-macos) que bloquea los 4 builds, cobertura real
de las rutas de error del CLI (exit codes, degradación de audio, Ctrl+C,
cleanup interactivo), del daemon (validación de rutas, health durante
síntesis, kill selectivo, canonicalización) y de la caché de modelo (headers
truncados, refs/main, precedencias). CI instala con `--require-hashes` y corre
`compileall` como red de sintaxis.

### Hallazgos

- Los tests de los scripts de build cubren solo las **funciones puras**
  (templates ISS/AppRun/.desktop/Info.plist); ningún test ejercita el flujo
  `main()` de `create_installer_windows.py` — exactamente donde vivía N-01.
  La propuesta del test de humo con ISCC mockeado forma parte del cierre de
  N-01.
- El step de staging de PowerShell debería fallar duro si el artefacto no
  existe (segunda red de N-01).

#### N-14 — Documentación desincronizada con el estado real

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `docs/GOAL.md:140,156` y `CLAUDE.md` («162 tests»; son 185); `USAGE.md:506` vs `BUILD.md:302` (tamaños contradictorios, ver N-05); `CHANGELOG.md` con «[No publicado]» + 0.1.0 fechado 2026-07-03 sin tag git |

**Propuesta**: actualizar los conteos, unificar los tamaños tras medir (N-05),
y decidir el corte del 0.1.0 antes de taggear (¿incluye lo de «No publicado»?).

---

## Dimensión 7 — Gobernanza de release, licenciamiento y cadena de suministro

### Veredicto **[PARCIALMENTE LISTO]**

Qué está production-ready: cadena de suministro sobresaliente (lock universal
con hashes, pines de Chocolatey/pip/appimagetool con SHA-256, política
documentada de actualización deliberada), gobernanza presente (CHANGELOG con
Keep-a-Changelog + SemVer, CONTRIBUTING, SECURITY con canal privado de
reporte), licencias empaquetadas en los tres artefactos
(`copy_license_files`), THIRD-PARTY-LICENSES verificado, y la sección de uso
ético del watermark bypaseado explicada con honestidad en README/USAGE/SECURITY.

### Hallazgos

#### N-04 — No existe camino de publicación para los binarios que README promete

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | README.md:40 y SECURITY.md remiten a GitHub Releases; `git tag` vacío pese al 0.1.0 fechado en CHANGELOG; `.circleci/config.yml` solo hace `store_artifacts` (artefactos efímeros internos); ningún documento describe el flujo de publicación; no se generan checksums |

No hay tag, no hay release publicado, no hay job ni runbook de publicación
(tag → build → checksums → subida a Releases). Agravante: al no haber firma de
código (R-38, reserva aceptada), los **checksums SHA-256 publicados** son la
única verificación de integridad posible para el usuario — y no se generan en
ninguna parte. SECURITY.md pide «verifica que descargas desde el repositorio
oficial» sin dar el mecanismo.

**Escenario**: hoy no existe nada que un usuario pueda descargar; y cuando
exista, no podrá verificar su integridad.

**Propuesta**: (a) definir el flujo de release, aunque sea manual, documentado
en BUILD.md o RELEASING.md: taggear `vX.Y.Z`, correr el pipeline, descargar
los 4 artefactos, generar `SHA256SUMS.txt`, publicar en GitHub Releases con
las notas del CHANGELOG; (b) añadir al CI un step que emita el SHA-256 de cada
artefacto en el log del job (verificable de punta a punta); (c) crear el tag
`v0.1.0` cuando se cierre el gate de esta auditoría.

**Tradeoffs**: automatizar la publicación desde CircleCI exige un token de
GitHub en el CI (superficie de secretos); el flujo manual documentado es
suficiente para 0.1.0.

#### N-15 — `voice add --compute-backend` es una flag muerta

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `cli.py:803-806` (la flag existe); `cmd_voice_add` → `register_voice_files` no instancia el motor |

Desde que el registro es ligero (precomputación diferida al primer `speak`),
la flag no tiene efecto.

**Propuesta**: eliminarla del subparser (los argumentos desconocidos fallan
ruidosamente, lo que es correcto) o documentar que se ignora.

---

## Tabla resumen de hallazgos

| ID | Severidad | Hallazgo | Evidencia principal |
|----|-----------|----------|---------------------|
| N-01 | **Bloqueante** | `main()` del instalador Windows truncada; el `.exe` nunca se compila y el build reporta éxito falso | `create_installer_windows.py:165-223` vs `256-315` |
| N-02 | Mayor | El daemon rechaza los `--voice-audio` del ejemplo documentado; restricción sin documentar | `server.py:99-106`, `USAGE.md:273` |
| N-03 | Mayor | `cleanup` sin `--yes`: `input()` + `EOFError` sin capturar rompe el uso programático | `cli.py:680`, `cli.py:892-900` |
| N-04 | Mayor | Sin proceso de release: sin tags, sin publicación a Releases, sin checksums SHA-256 | `.circleci/config.yml`, `git tag` vacío |
| N-05 | Mayor | AppImage x86_64 arrastra CUDA completo; tamaños declarados contradictorios | `requirements-lock.txt`, `USAGE.md:506` vs `BUILD.md:302` |
| N-06 | Mayor | Baseline glibc 2.35 ni validada ni documentada | CI: `cimg/python:3.13` / `ubuntu-2204` |
| N-07 | Mayor | `LSMinimumSystemVersion=12.0` sin respaldo del toolchain (pyenv en Xcode 26.4) | `build_macos.py:299`, CI |
| N-08 | Menor | InfoAfter afirma incluir el código fuente (falso) + typo + «LICENSE.txt» inexistente | `create_installer_windows.py:249-251` |
| N-09 | Menor | Ciclo de vida del daemon imprime progreso por stdout | `daemon.py:55,121,192-199` |
| N-10 | Menor | `--compute-backend` ignorado en silencio vía daemon | `protocol.py:22-24`, `USAGE.md:259` |
| N-11 | Menor | Límites de texto divergentes (2000 warn / 5000 hard / ∞) y exit 5 para entrada inválida vía daemon | `protocol.py:10`, `cli.py:150` |
| N-12 | Menor | `--output` a directorio inexistente: directo crea, daemon falla | `engine.py:621` vs `cli.py:91` |
| N-13 | Menor | Ventana ciega start/stop/status durante la carga del modelo (sin PID file) | `run.py:84-139`, `daemon.py:117-121` |
| N-14 | Menor | Docs desincronizadas: «162 tests» (son 185), CHANGELOG sin decisión de corte para 0.1.0 | `GOAL.md:140`, `CLAUDE.md` |
| N-15 | Menor | `voice add --compute-backend` flag muerta | `cli.py:803-806` |
| N-16 | Menor | Actualización de versión sin documentar; symlink AppImage queda apuntando a la versión vieja | `cli.py:472-501`, USAGE |
| N-17 | Menor | `setup` carga el modelo en RAM cuando solo necesita descargarlo | `cli.py:612-613` |

---

## Gate mínimo de release

1. **N-01** — Reconstruir `main()` del instalador + test que ejercite `main()`
   con ISCC mockeado + endurecer el step de staging del CI.
2. **N-04** — Taggear `v0.1.0`, documentar el flujo de publicación (manual es
   suficiente) y generar/publicar SHA-256 de los 4 artefactos.
3. **N-02** — Documentar la restricción de directorios del daemon en
   USAGE/DAEMON-MODE y dar un mensaje de error accionable.
4. **N-03** — Añadir `cleanup --yes` y capturar `EOFError` como cancelación.
5. **N-05/N-06** — Medir el AppImage real, decidir CPU-only vs. CUDA, y
   declarar los requisitos reales (tamaño y glibc) en README/USAGE.

---

## Recomendación global

### **NO LISTO** (a corta distancia de listo-con-reservas)

La distancia al release es corta pero real. La ironía central de esta ronda es
instructiva: el commit que cerraba los hallazgos menores del gate anterior
(`8a18fad`) **rompió el artefacto principal de Windows**, y las tres redes de
seguridad existentes (tests, log del build, CI) lo dejaron pasar porque todas
validan las partes puras y ninguna el flujo completo. N-01 es un fix de
minutos; N-04 es el trabajo estructural que falta para que «publicado y
distribuible» sea verdad — hoy no hay nada publicado que un usuario pueda
descargar ni verificar.

Con el gate de 5 puntos cerrado, la evaluación pasaría a
**listo-con-reservas**, siendo las reservas las ya conocidas y honestamente
documentadas: validación end-to-end por SO pendiente (criterios 1-3 y 9 de
GOAL.md) y binarios sin firma (R-38).

Respecto a la promesa de GOAL.md («API de voz unificada, nativa, invocable
desde cualquier lenguaje»): el **diseño** la cumple — contrato de exit codes
congelado, JSON versionado, UTF-8 forzado, daemon en loopback, paridad de UX
entre SO cuidada hasta el detalle. Lo que aún no la cumple es la **entrega**:
sin instalador de Windows funcional, sin releases publicados y con los claims
de compatibilidad (glibc, macOS 12) sin validar, la promesa está implementada
pero no distribuida.

---

## Decisiones del propietario

Resueltas interactivamente con el propietario el 2026-07-03 (fase de resolución
previa al plan de corrección). Los 10 hallazgos no listados aquí tienen
corrección autoevidente y pasan al plan como requisitos directos.

| ID | Decisión | Enfoque elegido |
|----|----------|-----------------|
| N-04 | Flujo de release | **Flujo manual documentado + SHA-256 en CI**: runbook (tag `vX.Y.Z` → pipeline → descargar artefactos → `SHA256SUMS.txt` → GitHub Release) más un step de CI que emite el SHA-256 de cada artefacto en el log. Sin publicación automatizada ni secretos nuevos en CI. |
| N-05 | Torch del build Linux | **Torch CPU-only en Linux** (homogeneizar hacia abajo): el AppImage empaqueta torch del índice CPU de PyTorch; Windows y Linux quedan idénticos (CPU-only) y macOS conserva `mps`. `--compute-backend cuda` deja de funcionar en el AppImage; la vía GPU-NVIDIA se documenta como instalación desde código fuente. Exige lock/índice específico para el build Linux. |
| N-06 | Baseline glibc | **Documentar «glibc ≥ 2.35»** (Ubuntu 22.04+, Debian 12+, Fedora 36+) en README/USAGE, con el error `GLIBC_2.35 not found` en solución de problemas. CI intacto. |
| N-07 | Claim de macOS mínimo | **Subir `LSMinimumSystemVersion` al target real del toolchain** y alinear GOAL/README. No se recompila CPython con target 12.0. |
| N-13 | Ventana ciega del daemon | **Documentar la ventana en DAEMON-MODE.md** (30-90 s donde status/stop no ven el proceso; esperar el «Daemon listo» de start). Sin PID file, coherente con SUGGESTION-03. |
| N-15 | Flag muerta `voice add --compute-backend` | **Eliminarla del subparser**: los usos existentes fallan ruidosamente (argumento desconocido), que es el comportamiento honesto. |
| N-17 | Provisión en `setup` | **Descargar con `snapshot_download` + `hf_hub_download` (ve.safetensors) sin instanciar el motor**; la validación de carga real queda en `doctor`/primer `speak` más el chequeo de header safetensors existente. |
