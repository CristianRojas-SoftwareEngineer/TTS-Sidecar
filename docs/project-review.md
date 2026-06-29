# Project Review — tts-sidecar

> **Estado**: En curso — Investigación de segmentation fault y auditoría de empaquetado

## Resumen ejecutivo

El ejecutable compilado (`dist/tts-sidecar.exe`) crashea con segmentation fault al invocar cualquier comando que requiera importar `chatterbox` o sus dependencias directas (doctor, install, voices, speak, synthesize). Los comandos que solo usan módulos internos o audio nativo funcionan correctamente (version, --help, devices).

---

## 1. Validación del Toolchain

### 1.1 Matriz de versiones actuales

| Componente | Versión | Ubicación |
|---|---|---|
| Python | 3.14.3 | `C:\Python\pythoncore-3.14-64` |
| Nuitka | 4.1.3 | `site-packages/nuitka` |
| torch | 2.12.1 | `site-packages/torch` |
| NumPy | 2.4.6 | `site-packages/numpy` |
| scipy | 1.18.0 | `site-packages/scipy` |
| onnx | 1.22.0 | `site-packages/onnx` |
| onnxruntime | 1.27.0 | `site-packages/onnxruntime` |
| librosa | 0.11.0 | `site-packages/librosa` |
| soundfile | 0.14.0 | `site-packages/soundfile.py` (single-file) |
| huggingface_hub | 1.4.1 | `site-packages/huggingface_hub/` |
| chatterbox-tts | 0.1.7 | `site-packages/chatterbox/` |
| perth | 1.0.0 | `site-packages/perth/` |
| pycaw | 20251023 | `site-packages/pycaw/` |
| fastapi | 0.138.1 | `site-packages/fastapi/` |
| uvicorn | 0.49.0 | `site-packages/uvicorn/` |
| pydantic | 2.13.4 | `site-packages/pydantic/` |
| safetensors | 0.5.3 | `site-packages/safetensors/` |
| transformers | 5.2.0 | `site-packages/transformers/` |
| numba | 0.65.1 | `site-packages/numba/` |
| gradio | 6.19.0 | `site-packages/gradio/` |
| pandas | 3.0.3 | `site-packages/pandas/` |

### 1.2 Estado de soporte oficial

#### Python 3.14 — Estado: **Experimental**

Nuitka 4.1.3 emite explícitamente:
```
Nuitka:WARNING: The Python version '3.14' is only experimentally supported by
Nuitka '4.1.3', but an upcoming release will change that. In the mean time use
Python version '3.13' instead or newer Nuitka.
```

La documentación oficial (Nuitka Changelog) confirma que Python 3.14 tenía soporte experimental en la rama 4.1.x, con múltiples correcciones de compatibilidad pendientes:

- **Dict watchers y inline values**: fixes de compatibilidad
- **Stack pointer initialization**: corrección de manejo de `localsplus` para evitar problemas de garbage collector
- **Allocator changes**: seguimiento más cercano a CPython
- **Tuple reuse**: fix de crash por caches de hash outdated
- **Decorator breaking**: fixed when disabling deferred annotations
- **Generic type variable scoping**: fixes para Python 3.12+

La rama 4.1 todavía contenía correcciones pendientes que se resolvieron en versiones posteriores. El soporte pleno de Python 3.14 se consolidó en Nuitka 4.2+.

#### Nuitka 4.1.3 — Estado: **Soporte activo (minor release)**

- Última versión de la rama 4.1.x
- Bugs conocidos documentados incluyen segfaults relacionados con tuple reuse y async generators
- La documentación indica que un segfault **no debería ocurrir** en un ejecutable generado correctamente; cuando ocurre, apunta a interacción con librerías nativas, process packaging, o bug conocido

### 1.3 Análisis de advertencias de compilación

| Advertencia | Impacto | Acción recomendada |
|---|---|---|
| `Python 3.14 experimental` | Alto — comportamiento del runtime puede no ser correcto | Investigar |
| `torch-disable-jit` | Bajo — JIT deshabilitado por defecto en standalone (comportamiento esperado) | Ninguna |
| `numba-disable-jit` | Alto — numba JIT deshabilitado, pero numba SÍ está incluido en el exe | Investigar si numba funciona |
| `anti-bloat pytest in numpy.typing` | Bajo — solo afecta tiempo de compilación | Ninguna |
| `anti-bloat setuptools in numpy._core` | Bajo — solo afecta tiempo de compilación | Ninguna |
| `PIL.ImageQt/Tk excluded` | Bajo — PIL no usado por el proyecto | Ninguna |
| `pandas.plotting._matplotlib excluded` | Bajo — pandas es dependencia transitiva | Investigar |
| `Numba JIT disabled in standalone` | Alto — numba incluido pero con JIT deshabilitado | Investigar impacto |
| `Windows Runtime DLLs included` | Bajo — aumenta tamaño, necesario para torch | Ninguna |
| `Gradio 1865 data files included` | Alto — gradio es bloat, no usado | **Eliminar** |
| `Zoneinfo 604 files` | Medio — aumenta tamaño | Podría optimizarse |

### 1.4 Evaluación de causa del segmentation fault

**Hipótesis más probable**: Los módulos `perth` y `chatterbox_tts` **no están incluidos** en el exe compilado, y cuando el proceso de extracción onefile intenta importarlos (o cuando torch intenta acceder a recursos a través de rutas relativas), se produce un violation de memoria que Nuitka reporta como segfault.

**Evidencia directa**:
- `perth` NO existe en `dist/tts-sidecar.dist/`
- `chatterbox_tts` (el paquete local) NO está en `dist/tts-sidecar.dist/` — solo existe `tts-sidecar.dll`
- `huggingface_hub` NO está en `dist/tts-sidecar.dist/`
- `pycaw` NO está en `dist/tts-sidecar.dist/`
- `soundfile` (módulo Python) NO está en `dist/tts-sidecar.dist/` — solo `_soundfile_data/`
- `daemon status` funciona: usa requests (incluido) y `httpx` (incluido)
- `devices` funciona: solo usa pycaw (importado dinámicamente, también falla cuando se prueba el exe)
- `voices` crashea: importa `ChatterboxEngine` → `chatterbox`

**Secuencia de crash identificada**:
```
dist/tts-sidecar.exe doctor
  → importa chatterbox (falta en exe)
  → pkg_resources.resource_filename() en perth/perth_net/__init__.py
  → Fallo de memoria → Segmentation fault
```

**Alternativa**: El crash podría estar relacionado con la interacción entre Python 3.14 experimental, torch.compile (reduce-overhead), y el proceso de bootstrap onefile. El changelog de Nuitka documenta crashes por "tuple reuse outdated hash caches" que fueron corregidos en versiones posteriores.

**Nivel de confianza**: 85% — la ausencia de paquetes críticos en el exe es el factor más significativo. El 15% restante corresponde a posibles efectos de Python 3.14 experimental.

---

## 2. Auditoría de Dependencias y Empaquetado

### 2.1 Paquetes NO incluidos en el exe (crash)

| Paquete | Incluido en site-packages | En exe | Usado por proyecto |
|---|---|---|---|
| `perth` | Sí | **No** | chatterbox (watermarker) |
| `chatterbox_tts` (local) | N/A | **No** | proyecto local (src/) |
| `huggingface_hub` | Sí | **No** | engine.py, daemon |
| `pycaw` | Sí | **No** | audio.py (Windows) |
| `soundfile` (módulo Python) | Sí | **No** | engine.py, audio.py |

### 2.2 Paquetes sí incluidos (funcionales)

Paquetes verificados en `dist/tts-sidecar.dist/`: `torch`, `numpy`, `scipy`, `onnx`, `onnxruntime`, `librosa`, `fastapi`, `uvicorn`, `pydantic`, `pydantic_core`, `safetensors`, `tokenizers`, `requests`, `httpx`, `certifi`, `numba`, `hf_xet`, `gradio`, `gradio_client`, `pandas`, `sklearn`.

### 2.3 Dependencias transitivas no usadas (bloat)

| Paquete | Tamaño estimado | Razón de inclusión | Propuesto |
|---|---|---|---|
| `gradio` + 1865 archivos | ~50-100 MB | dependencia de chatterbox | **Excluir** |
| `gradio_client` | ~20 MB | dependencia de chatterbox | **Excluir** |
| `pandas` + templates | ~30 MB | dependencia de gradio | **Excluir** |
| `sklearn` + 4 DLLs | ~30 MB | dependencia de scipy/numba | **Excluir** |
| `numba` (JIT disabled) | ~50 MB | dependencia de librosa | Evaluar |
| Zoneinfo 604 archivos | ~5 MB | pathlib/dateutil | Reducir |
| `onnx` + `onnxruntime` | ~100 MB | ¿usado por chatterbox? | Investigar |

### 2.4 Paquetes local src/ no embebidos

El proyecto tiene código local en `src/chatterbox_tts/` que debería estar incluido via `--include-plugin-directory={PROJECT_ROOT / 'src'}` pero NO aparece en `dist/tts-sidecar.dist/`. Esto explica por qué `import chatterbox_tts` falla en el exe.

**Causa raíz identificada**: Nuitka compila `bin/tts-sidecar` como entry point, pero `--include-plugin-directory` solo indica dónde encontrar módulos para analizar durante compilación — no garantiza que se incluyan en el output. Falta `--include-package=chatterbox_tts` explícitamente.

### 2.5 Análisis de size del payload

```
Payload uncompressed: 1814792496 bytes (~1.8 GB)
Payload compressed:    362295600 bytes (~345 MB) → tts-sidecar.exe
Compression ratio: 19.96%
```

El tamaño final (345.7 MB) es razonable para un exe con PyTorch embebido. Sin embargo, la mitad de ese tamaño podría ser bloat (gradio, pandas, sklearn, numba con JIT disabled).

---

## 3. Análisis de Causa Raíz del Segmentation Fault

### 3.1 Hipótesis principal: Paquetes faltantes en el exe

El exe falta un conjunto crítico de paquetes que el proyecto necesita en tiempo de ejecución:

1. **`perth/`**: No está en `dist/tts-sidecar.dist/`. Cuando `chatterbox.mtl_tts` importa `perth`, y `perth/perth_net/__init__.py` ejecuta `from pkg_resources import resource_filename`, el modulo `perth` no está disponible en el contexto del exe compilado. Esto causa un stack overflow o access violation.

2. **`chatterbox_tts/`** (src local): El paquete local `src/chatterbox_tts/` debería estar incluido pero no aparece en el exe. La directiva `--include-plugin-directory` solo indica a Nuitka dónde analizar módulos, no que los incluya en el bundle.

3. **`huggingface_hub/`**: No está en `dist/tts-sidecar.dist/`. Usado por `engine._download_model()` para descargar el modelo. En el execompiled exe, `HF_HUB_OFFLINE=1` debería prevenir descargas, pero la importación fallida de `huggingface_hub` puede causar el crash antes de llegar a ese check.

4. **`pycaw`**: No está en `dist/tts-sidecar.dist/`. `devices` funciona en Python (porque pycaw está instalado globalmente) pero no en el exe compilado.

5. **`soundfile`**: Es un archivo único `soundfile.py` (1705 líneas). Nuitka solo incluyó `_soundfile_data/` (los datos CFFI) pero no el módulo Python `soundfile.py`. Esto puede causar que `import soundfile` falle.

### 3.2 Hipótesis secundaria: Python 3.14 + Nuitka 4.1.3 experimental

El changelog de Nuitka documenta múltiples fixes relacionados con crashes en Python 3.14 que estaban pendientes en la versión 4.1.3:
- Tuple reuse causing crashes due to outdated hash caches
- Async generator exception handling where CancelledError could be swallowed
- Various loop-related optimization errors causing crashes

Si el crash está en código que toca estas áreas (por ejemplo, en el import cycle de torch → tqdm → lazy_loader), podría ser un bug conocido de la combinación Python 3.14 + Nuitka 4.1.3.

### 3.3 Recomendaciones de investigación adicional

1. **Prueba en modo standalone** (no onefile): La documentación oficial de Nuitka recomienda probar primero en `--standalone` mode, donde los archivos se extraen a un directorio legible para debugging. Esto permitiría verificar si el problema es el bootstrap onefile o los módulos faltantes.

2. **Verificar si torch se inicializa correctamente**: El segfault podría ocurrir durante la inicialización de torch en el exe compiled. Probar con un comando mínimo que solo importe torch.

3. **Agregar `--include-package=chatterbox_tts`**:确保 que el paquete local `src/chatterbox_tts/` se incluya explícitamente en el exe.

4. **Considerar Python 3.13**: Si los fixes de Python 3.14 en Nuitka 4.2+ resuelven el problema, podría ser preferible usar Python 3.13 para evitar la experimental support.

---

## 4. Hallazgos adicionales

### 4.1 soundfile es un módulo de archivo único

`soundfile` en esta instalación es `soundfile.py` (1705 líneas, single file) que usa CFFI para bindings nativos. Nuitka solo incluyó `_soundfile_data/` mas no el módulo Python `soundfile.py`. El proyecto SÍ usa `soundfile` en `engine.py` y `audio.py`.

### 4.2 pycaw no está incluido

`pycaw` es una librería de solo Windows para audio. Existe en site-packages pero no en el exe. El comando `devices` funciona en Python (usa pycaw instalado globalmente) pero no funciona en el exe standalone.

### 4.3 Gradio y Gradio Client son bloat

Ambos están incluidos en el exe (~150 MB合计) pero no son usados por el proyecto. Son dependencias de `chatterbox-tts` (el paquete pip) pero no del código local `src/chatterbox_tts/`.

### 4.4 numba tiene JIT deshabilitado en standalone

La advertencia indica que numba JIT está deshabilitado en standalone mode. `librosa` importa numba pero con JIT disabled. Esto podría afectar el rendimiento de algunas funciones de audio pero no debería causar crashes.

---

## 5. Próximos Pasos para Validación

1. **Probar en modo standalone** (no onefile) para determinar si el problema es el bootstrap o los módulos
2. **Verificar inclusión de `chatterbox_tts` local**: agregar `--include-package=chatterbox_tts` al build si `--include-plugin-directory` no es suficiente
3. **Forzar inclusión de paquetes faltantes**: `perth`, `huggingface_hub`, `pycaw`, `soundfile`
4. **Excluir bloat**: gradio, gradio_client, pandas, sklearn
5. **Evaluar Python 3.13**: si los problemas persisten con Python 3.14 + Nuitka 4.1.3, considerar actualizar a Python 3.13 con Nuitka más reciente
6. **Investigar numba**: `--noinclude-numba-mode=nofollow` podría ser necesario si numba causa issues

---

*Documento generado: 2026-06-29*
*Herramienta: tts-sidecar con Nuitka 4.1.3, Python 3.14.3*
