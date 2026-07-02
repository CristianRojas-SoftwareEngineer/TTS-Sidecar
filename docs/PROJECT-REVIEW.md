# Revisión: auditoría sistémica de tts-sidecar (corrección · compatibilidad · mantenibilidad · seguridad)

## Resumen ejecutivo

Se auditó todo el repositorio `tts-sidecar` bajo una lente combinada de corrección/bugs,
compatibilidad multiplataforma, mantenibilidad/deuda técnica y seguridad, con perfil
**preventivo**. Se partió de una auditoría previa (`CRITICAL-01`, `CRITICAL-02`, `WARNING-02`,
`WARNING-03` del histórico en `git show HEAD:docs/PROJECT-REVIEW.md`) cuyas correcciones se
verificaron **todas vigentes** (sin regresiones). Esta ronda encontró **1 defecto crítico**
que rompe la promesa de funcionamiento offline para el modelo `multilingual`, **1 advertencia**
sobre el mecanismo de auto-restart del daemon, y **4 sugerencias** de limpieza/mantenibilidad.
No se hallaron problemas de seguridad nuevos (path traversal, `shell=True`, deserialización)
tras revisar `voices.py`, `daemon/server.py` y los scripts de build.

| ID | Título | Grupo | Área/plataforma | Decisión requerida |
|----|--------|-------|-----------------|--------------------|
| CRITICAL-01 | `_download_model` re-descarga el modelo `multilingual` aunque esté cacheado | Crítico | Engine / todas | No |
| WARNING-01 | `--auto-restart` del daemon no recarga el modelo tras un crash (caché de clase persiste) | Advertencia | Daemon / todas | No |
| SUGGESTION-01 | Ruta del voice-encoder de fallback hardcodea la caché de HF en vez de reusar `hub_cache_path()` | Sugerencia | Engine | No |
| SUGGESTION-02 | `AudioPlayer` no soporta plataformas fuera de Win/Linux/macOS sin diagnóstico en `doctor` | Sugerencia | Audio / otras plataformas | No |
| SUGGESTION-03 | Handlers de señal en `daemon/run.py` quedan sin efecto claro tras arrancar uvicorn | Sugerencia | Daemon | No |
| SUGGESTION-04 | Traducción redundante de alias de modelo en `_download_model` (código confuso, no alcanzable) | Sugerencia | Engine | No |

## Hallazgos por grupo

### Críticos

#### CRITICAL-01 — `_download_model` re-descarga el modelo `multilingual` aunque esté cacheado
- **Área/plataforma**: `src/chatterbox_tts/engine.py`; todas las plataformas.
- **Evidencia**: `engine.py:240-248`. La rama que acepta un snapshot cacheado y evita la
  descarga solo retorna explícitamente cuando el modelo es `es-mx-latam` (verifica
  `t3_es_mx_latam.safetensors`, línea 245). Para cualquier otro modelo (p. ej. `multilingual`),
  si `cached is not None`, el `if` de la línea 244 no cubre ese caso y el flujo cae igual hacia
  el bloque de descarga (líneas 249+). Esto contradice `is_model_cached()`
  (`src/chatterbox_tts/model_cache.py:63-81`), que sí acepta cualquier snapshot no vacío para
  modelos distintos de `es-mx-latam` (línea 81: `return True`).
- **Causa**: al añadir la verificación específica de `es-mx-latam` no se generalizó el `return`
  del snapshot cacheado para el resto de modelos.
- **Impacto**: con `--model multilingual`, el motor descarga desde HuggingFace en **cada**
  instanciación (cada `speak`/`daemon start`) aunque el modelo ya esté en caché local. Si no hay
  red disponible, la síntesis falla pese a que `tts-sidecar doctor`/`is_model_cached` reportan el
  modelo como "cacheado" — rompe la promesa de funcionamiento offline documentada en `CLAUDE.md`
  para ese modelo, y desperdicia ancho de banda/tiempo en el caso con red.
- **Corrección(es) propuesta(s)**:
  1. *(recomendada)* En `_download_model`, cuando `cached is not None` y el modelo no es
     `es-mx-latam`, retornar `cached` directamente (igual que ya hace `is_model_cached`), en vez
     de dejar caer el flujo hacia la descarga.
- **Decisión requerida**: No — corrección evidente (alinear con `is_model_cached`).

### Advertencias

#### WARNING-01 — `--auto-restart` del daemon no recarga el modelo tras un crash
- **Área/plataforma**: `src/chatterbox_tts/daemon/run.py` + `src/chatterbox_tts/engine.py`;
  todas las plataformas.
- **Evidencia**: `run.py:79-93` reintenta `ChatterboxEngine.get_instance(model="es-mx-latam",
  device="cpu")` dentro del bucle `while True:` de `serve()`, pero `get_instance`
  (`engine.py:136-151`) usa una caché **a nivel de clase** (`_cache`, línea 134) que persiste
  durante todo el proceso; con la misma `cache_key`, devuelve la instancia ya existente sin
  reconstruirla (líneas 149-150).
- **Causa**: el mecanismo de reintento no invalida la caché de instancia antes de reintentar.
- **Impacto**: si el crash que dispara `--auto-restart` (`cli.py:557`) se debe a un estado
  interno corrupto del motor (p. ej. tras una excepción en `speak()`), el reinicio vuelve a
  levantar el mismo objeto potencialmente dañado en memoria en vez de recargar el modelo desde
  cero, anulando el propósito de la opción para esa clase de fallos.
- **Corrección(es) propuesta(s)**: invalidar explícitamente la entrada correspondiente de
  `ChatterboxEngine._cache` antes de reintentar en `run.py`, forzando una recarga real.
- **Decisión requerida**: No.

### Sugerencias

#### SUGGESTION-01 — Ruta del voice-encoder de fallback duplica la construcción de `hub_cache_path()`
- **Evidencia**: `engine.py:294-299` construye manualmente
  `~/.cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots`, en vez de reutilizar
  `hub_cache_path()` (`model_cache.py:28-30`), ya centralizada.
- **Impacto**: dos fuentes de verdad para la misma ruta; una futura corrección de
  `hub_cache_path()` (p. ej. soporte de `HF_HOME`) dejaría esta ruta desactualizada.
  **Corrección**: reemplazar por `hub_cache_path() / cache_folder_for(...) / "snapshots"`.
- **Decisión requerida**: No.

#### SUGGESTION-02 — `AudioPlayer` no soporta plataformas fuera de Win/Linux/macOS sin diagnóstico
- **Evidencia**: `audio.py:32-41` lanza `RuntimeError` para cualquier otra plataforma;
  `cli.py:264-300` (`_environment_checks`) no cubre esa rama en `doctor`.
- **Impacto**: laguna de diagnóstico (bajo, fuera del alcance declarado Win/Linux/macOS).
  **Corrección**: opcional, no prioritaria dado el alcance del proyecto.
- **Decisión requerida**: No.

#### SUGGESTION-03 — Handlers de señal en `daemon/run.py` quedan sin efecto claro tras uvicorn
- **Evidencia**: `run.py:72-77` registra `SIGTERM`/`SIGINT` antes de `uvicorn.Server.run()`
  (línea 123), que instala sus propios manejadores por defecto y puede sobrescribirlos.
- **Impacto**: deuda de claridad sobre qué mecanismo controla realmente el apagado (bajo,
  especulativo — no verificado en runtime). **Corrección**: documentar o unificar en una sola
  fuente de verdad para el apagado por señal.
- **Decisión requerida**: No.

#### SUGGESTION-04 — Traducción redundante de alias de modelo en `_download_model`
- **Evidencia**: `engine.py:251-252` reimplementa el mapeo de alias corto → repo-id completo que
  ya resuelve `self.MODELS.get(model, model)` en `__init__` (`engine.py:170`) antes de llegar a
  `_download_model`; ese branch normalmente no es alcanzable en el flujo actual.
- **Impacto**: código confuso, no un bug activo. **Corrección**: eliminar la traducción
  redundante o comentar que es una red de seguridad para llamadas directas hipotéticas.
- **Decisión requerida**: No.

## Orden de corrección recomendado

- **Fase 1 (corrección funcional)**: CRITICAL-01 (rompe offline para `multilingual`) y
  WARNING-01 (auto-restart no efectivo) — bajo esfuerzo, impacto alto en confiabilidad.
- **Fase 2 (limpieza)**: SUGGESTION-01, SUGGESTION-03, SUGGESTION-04 (consolidar rutas,
  clarificar señales, quitar código confuso).
- **Fase 3 (opcional)**: SUGGESTION-02 (fuera del alcance declarado del proyecto; no priorizar).

## Decisiones del propietario

Ningún hallazgo de esta ronda requirió decisión del propietario — todas las correcciones
propuestas son directas y de bajo riesgo (alinear ramas de código existentes, sin alternativas
de diseño en competencia). Se omite la Fase 4 (`resolve-open-decisions`) y los hallazgos pasan
directos a la Fase 5 como requisitos cerrados del plan.

Del histórico previo, quedan confirmados sin regresión (no requieren nueva decisión):
`CRITICAL-01` (deps del daemon declaradas en `pyproject.toml:16-23`/`requirements.txt:11-13`),
`CRITICAL-02` (`get_version()` centralizado en `scripts/build_utils.py:36-51`), `WARNING-02`
(`scripts/install.py` eliminado) y `WARNING-03` (`_resolve_cached_snapshot()` en
`model_cache.py:50-60` lee `refs/main`).

## Confirmación en CI

- **CRITICAL-01**: probado por lectura de código (comparación de ramas en `_download_model` vs.
  `is_model_cached`). Se confirma ejecutando `tts-sidecar speak --model multilingual` dos veces
  seguidas con red deshabilitada la segunda vez, o instrumentando un log de descarga.
- **WARNING-01**: probado por lectura (semántica de caché de clase). Se confirma provocando un
  crash controlado del daemon con `--auto-restart` y observando si el proceso reinicia con un
  motor nuevo (log de carga de modelo) o reutiliza el existente.
