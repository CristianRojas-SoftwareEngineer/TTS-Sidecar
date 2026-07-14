# Plugin de Claude Code: narración por voz con TTS-Sidecar

> **Estado**: implementado. Este documento especifica la arquitectura de un
> plugin de Claude Code que narra por voz la actividad de la sesión usando
> TTS-Sidecar. El plugin es un **consumidor** del CLI: vive en su propio
> repositorio, con su propio ciclo de vida, y no requiere ningún cambio en
> TTS-Sidecar.
>
> **Ubicación durante el desarrollo**: la implementación reside temporalmente en
> el subdirectorio `claude-code-plugin/` de este repo (por cohesión y visión
> completa del CLI mientras madura). Es autocontenida y no acopla al código
> fuente de TTS-Sidecar —interactúa solo vía la CLI pública—, por lo que se
> extraerá completa a su repositorio propio (`tts-sidecar-narrator`) sin cambios.
> Lo temporal es la ubicación, no la implementación.

## Objetivo

Que Claude Code narre por voz sus mensajes de forma automática. El usuario
trabaja normalmente; al final de cada turno (y en avisos relevantes), escucha
un mensaje conversacional corto — no el texto en bruto del asistente, que
contiene código, rutas y markdown que no se narran bien, sino un mensaje
procesado por un constructor dedicado.

**Requisitos:**

1. **Automático**: disparado por hooks de Claude Code, sin intervención del
   modelo ni del usuario.
2. **No intrusivo**: la narración jamás bloquea ni retrasa el turno de Claude
   Code, y falla en silencio si TTS-Sidecar no está disponible.
3. **Multiplataforma**: paridad completa Windows / Linux / macOS, igual que
   TTS-Sidecar.
4. **Sin prerequisitos de runtime adicionales**: los scripts del plugin corren
   sobre Node.js — el runtime que Claude Code ya trae consigo — escritos en
   TypeScript. No se exige Python ni ningún otro intérprete: la misma filosofía
   por la que TTS-Sidecar se compila nativo por SO, aplicada al plugin.
5. **Costo cero**: la generación del mensaje conversacional usa exclusivamente
   niveles gratuitos de LLM (Gemini free como principal, modelos `:free` de
   OpenRouter como fallback) y degrada a un modo local determinista — nunca
   una API de pago.
6. **Controlable**: el usuario puede activar/desactivar la narración sin
   desinstalar el plugin.

## Ubicación de la implementación: repositorio independiente

El plugin se implementa en un **repositorio propio** (`tts-sidecar-narrator`),
no dentro de este repo. No es una preferencia estética sino la consecuencia de
cuatro hechos:

1. **El acoplamiento real es solo el contrato público del CLI.** El plugin
   depende exclusivamente de `tts-sidecar` en PATH y de la interfaz de `speak`
   / `doctor` / `daemon` — el mismo contrato que cualquier otro consumidor
   (scripts de usuario, otros editores). No importa el paquete `tts_sidecar`,
   no comparte código, no necesita el árbol fuente. Alojarlo aquí codificaría
   en la estructura del repo un acoplamiento que el diseño precisamente evita.

2. **Ciclos de vida y versionado disjuntos.** TTS-Sidecar versiona releases de
   un motor de síntesis (binarios por SO, PyPI, lockfiles, gates de cobertura);
   el plugin versiona con el campo `version` de `plugin.json` y evoluciona al
   ritmo de Claude Code (nuevos eventos de hook, cambios de esquema), no al del
   motor. Un fix del plugin no debería esperar —ni disparar— un release de
   TTS-Sidecar, y viceversa.

3. **El modelo de distribución de plugins asume un repo git.** Los
   marketplaces de Claude Code (propios o el comunitario de Anthropic)
   apuntan a repositorios y fijan commits (el marketplace comunitario pinea el
   SHA y lo actualiza con cada push del repo del plugin). Un repo dedicado
   hace que instalar, pinear y actualizar sea el camino estándar; incrustarlo
   como subdirectorio de este repo es posible pero convierte cada commit del
   motor en "versión nueva" aparente del plugin y complica la sumisión al
   marketplace.

4. **CI e infraestructura no comparten nada.** El CI de este repo compila
   binarios PyInstaller, corre ~559 tests y gates de cobertura por módulo; el
   plugin necesita otra cosa: toolchain TypeScript (compilación a `dist/`,
   `claude plugin validate`) y una matriz mínima de smoke de los scripts en
   los tres SO. Mezclarlos infla ambos pipelines sin beneficio.

El costo de la separación es menor y acotado: mantener sincronizada la
referencia cruzada en la documentación (este documento enlaza al repo del
plugin cuando exista; el README del plugin declara la versión mínima de
TTS-Sidecar que requiere). Dado que el contrato entre ambos es la CLI pública
—estable por definición—, la deriva entre repos es un riesgo bajo.

Lo único que vive en este repo es **este documento de diseño**, porque registra
una decisión de producto de TTS-Sidecar (cómo se integra con Claude Code) y
sirvió de especificación inicial. Cuando el plugin exista, este documento
pasará a ser un puntero: resumen + enlace al repo del plugin, que será la
fuente de verdad.

## Fundamentos de la plataforma

Tres hechos de Claude Code determinan la arquitectura:

- **Los hooks son deterministas y síncronos.** Claude Code ejecuta el
  `command` declarado en `hooks.json` cuando ocurre el evento, le pasa un JSON
  por stdin y **espera a que el proceso termine** antes de continuar. El
  modelo no participa: ningún hook lee skills ni instrucciones.
- **Las skills son model-invoked.** Son instrucciones que Claude carga cuando
  decide usarlas o cuando el usuario las invoca (`/plugin:skill`). Sirven para
  capacidades conscientes, no para automatización.
- **Claude Code corre sobre Node.js.** Toda máquina con Claude Code instalado
  tiene `node` disponible; es el único runtime cuya presencia el plugin puede
  asumir sin añadir prerequisitos. Además, `node` es un ejecutable real en los
  tres SO, lo que habilita el *exec form* de los hooks (ver más abajo) sin las
  limitaciones que tienen los shims `.cmd`/`.bat` en Windows.

De ahí las tres decisiones estructurales del diseño:

1. La automatización vive **íntegramente en hooks + scripts**; la skill es un
   componente separado y opcional para el caso de uso consciente ("léeme esto
   en voz alta", toggles de configuración).
2. Como una síntesis tarda segundos (decenas, en frío) y el hook es síncrono,
   el script del hook es un **launcher fire-and-forget**: lanza un worker
   desanclado y retorna en <100 ms. Todo el trabajo pesado ocurre fuera del
   ciclo de vida del hook.
3. Los scripts se escriben en **TypeScript** y se distribuyen **compilados a
   JavaScript** en `dist/`, invocados con `node`. Autoría con tipos, ejecución
   sin toolchain: el usuario final no necesita `tsc`, `npm install` ni
   `node_modules` (los scripts usan solo la stdlib de Node y se empaquetan con
   un bundler —esbuild— a un archivo JS autocontenido por entry point).

## Arquitectura

### Estructura del plugin

```
tts-sidecar-narrator/                  # plugin root (repositorio propio)
├── .claude-plugin/
│   └── plugin.json                    # manifiesto: name, description, version
├── hooks/
│   └── hooks.json                     # eventos → launcher (via node)
├── src/                               # fuente TypeScript (solo desarrollo)
│   ├── narrate-hook.ts                # LAUNCHER: stdin → detach worker → exit 0
│   ├── narrate-worker.ts              # WORKER: single-instance, construye y narra
│   ├── health-check.ts                # chequeo de SessionStart (aviso único)
│   ├── message/                       # constructor del mensaje conversacional
│   │   ├── build-message.ts           # orquestador: cadena LLM → local → estático
│   │   ├── provider-chain.ts          # primario → fallback (composición genérica)
│   │   ├── gemini-provider.ts         # Gemini API (free tier)
│   │   ├── openrouter-provider.ts     # OpenRouter (modelos :free)
│   │   ├── local-builder.ts           # modo determinista sin red
│   │   ├── prompts.ts                 # system prompts por modo (prompt/summary)
│   │   └── sanitize.ts                # normalización del texto para voz
│   └── lib/
│       ├── state-dir.ts               # state dir por SO
│       ├── config.ts                  # config.json: toggle, modo, API keys
│       └── spawn.ts                   # desanclaje y terminación de workers
├── dist/                              # JS compilado (lo que ejecutan los hooks)
│   ├── narrate-hook.js                # bundles autocontenidos, sin node_modules
│   ├── narrate-worker.js
│   └── health-check.js
├── commands/                          # comandos invocados por el usuario
│   └── install.md                     # /tts-sidecar-narrator:install (runbook)
├── skills/                            # componente OPCIONAL (uso consciente)
│   └── narrate/
│       └── SKILL.md                   # /tts-sidecar-narrator:narrate
├── package.json                       # devDependencies (typescript, esbuild)
├── tsconfig.json
└── README.md                          # prerequisitos e instalación
```

Convenciones de Claude Code respetadas: solo `plugin.json` va dentro de
`.claude-plugin/`; `hooks/`, `src/`, `dist/` y `skills/` van en el plugin root.
Todas las rutas internas se referencian con `${CLAUDE_PLUGIN_ROOT}`, que Claude
Code sustituye por la ruta de instalación real en cualquier SO.

**`dist/` se commitea** (o se publica como artefacto zip vía `--plugin-url`):
como los plugins se instalan clonando el repo, el JS compilado debe estar en el
árbol para que los hooks funcionen sin paso de build en la máquina del usuario.
Un check de CI verifica que `dist/` está sincronizado con `src/`.

### Pipeline en tiempo de ejecución

```
Claude Code dispara el evento (Stop / Notification)
        ↓  JSON por stdin: session_id, cwd, last_assistant_message, …
narrate-hook.js            [launcher — dentro del hook, <100 ms]
        │  1. lee stdin completo
        │  2. consulta el toggle enabled (si está off → exit 0)
        │  3. persiste el payload en el state dir
        │  4. lanza narrate-worker.js DESANCLADO
        ↓  exit 0 — Claude Code continúa de inmediato
narrate-worker.js          [proceso independiente del hook]
        │  5. single-instance: interrumpe al worker anterior si existe
        │  6. build-message → mensaje conversacional
        │       Gemini (free) → OpenRouter (:free) → constructor local
        ↓
tts-sidecar speak --text "<mensaje>" --daemon
        ↓  daemon caliente (arranque en frío solo la primera vez)
audio reproducido
```

La separación de responsabilidades es estricta: el launcher no sabe de
narración, el constructor no sabe de audio, el CLI no sabe de Claude Code.

### Componentes

#### `narrate-hook.ts` — launcher

Su única misión es salir rápido. Lee el stdin, decide si narrar (toggle), y
lanza el worker desanclado con el payload. Sin dependencias, sin red, sin
espera. Presupuesto: <100 ms (el arranque de Node en frío son ~50 ms).
Adicionalmente, `hooks.json` fija `timeout` corto como red de seguridad: si el
launcher se colgara, Claude Code lo mata sin afectar la sesión más que unos
segundos.

El desanclaje en Node es multiplataforma con una sola API — sin rama por SO:

```typescript
import { spawn } from "node:child_process";

export function spawnDetached(cmd: string, args: string[]): void {
  const child = spawn(cmd, args, {
    detached: true,        // nuevo process group (POSIX) / consola propia (Windows)
    stdio: "ignore",
    windowsHide: true,     // sin ventana de consola en Windows; no-op en POSIX
  });
  child.unref();           // el launcher puede salir sin esperar al hijo
}
```

#### `narrate-worker.ts` — worker

Proceso independiente que hace todo el trabajo con latencia:

1. **Single-instance con interrupción**: escribe su PID en
   `stateDir()/worker.pid`; si ya había un worker vivo, lo termina antes de
   continuar. Política: *la narración más reciente gana* — en un asistente
   conversacional, lo viejo ya caducó cuando llega un turno nuevo. Terminar al
   worker anterior corta también su `speak` en curso: en POSIX se mata el
   process group (`process.kill(-pid)`, posible porque `detached: true` creó
   uno), en Windows el árbol completo (`taskkill /PID <pid> /T /F`). Esta es
   la única bifurcación por SO del plugin, encapsulada en `lib/spawn.ts`.
2. **Construcción del mensaje**: invoca el módulo `build-message` con el
   payload.
3. **Narración**: resuelve el CLI buscando `tts-sidecar` en el PATH (con
   `.exe` en Windows) — cubre los dos canales de distribución en los tres SO
   (binario nativo en PATH vía Inno Setup / symlink AppImage / symlink macOS,
   y `uv tool install`) — y ejecuta `speak --text … --daemon`.
4. **Degradación silenciosa**: cualquier fallo (CLI ausente, modelo no
   cacheado — `speak` falla rápido por diseño —, daemon caído, audio device
   ocupado) termina el worker sin ruido. El diagnóstico con aviso pertenece al
   chequeo de `SessionStart`, no al camino caliente de cada turno. Los errores
   se registran en `stateDir()/worker.log` para depuración.

#### `message/` — constructor del mensaje conversacional

Recibe los datos del evento y produce el mensaje corto a narrar. Para el resto
del pipeline es una función `payload → texto` que **siempre resuelve**: la
degradación entre niveles (LLM gratuito → constructor local → texto estático)
ocurre dentro del módulo. Su diseño completo está en la sección
[Generación del mensaje conversacional](#generación-del-mensaje-conversacional).

#### `health-check.ts` — chequeo de arranque

Hook de `SessionStart`. Verifica una sola vez por sesión que la cadena está
completa: `tts-sidecar` en PATH y modelo cacheado (`doctor --json`). Si algo
falta, informa al usuario mediante el campo `systemMessage` del JSON de salida
del hook (el mecanismo portable de notificación: los hooks no tienen terminal
controlante, y en Windows nunca existió `/dev/tty`) con la acción correctiva
(`tts-sidecar setup`). Nunca falla la sesión: exit 0 siempre.

Además, cuando la cadena está completa (CLI + modelo en caché) y la narración
está activada, **deja el daemon en marcha**: si `daemon status --json` reporta
que no corre, lo arranca de forma **desanclada** (fire-and-forget, sin bloquear
el inicio de sesión mientras el modelo se carga en segundo plano). Como
`speak --daemon` requiere el daemon vivo y este no sobrevive a un reinicio del
equipo, este auto-arranque elimina el paso manual `daemon start` en el uso
cotidiano: la primera sesión tras un reinicio lo vuelve a levantar sola.
Respeta el toggle (`enabled: false` → no arranca nada) y solo actúa con el
modelo confirmado en caché (`lib/daemon.ts`).

#### `skills/narrate/SKILL.md` — skill opcional

Segundo caso de uso, independiente de la automatización: permite a Claude
narrar a demanda ("léeme este resumen"), expone los toggles
(`/tts-sidecar-narrator:narrate on|off`) que escriben `enabled` en
`stateDir()/config.json`, y guía la configuración de las API keys de los
proveedores gratuitos (`narrate setup`). La skill documenta el uso del CLI
**para Claude**, no para los hooks.

#### `commands/install.md` — comando de instalación guiada

Comando invocado por el usuario (`/tts-sidecar-narrator:install`), no
model-invoked: su cuerpo es un *runbook* que el agente principal ejecuta de forma
interactiva. Materializa el flujo de dos pasos del usuario final —**instalar el
plugin** desde el marketplace y luego **invocar el comando**— para dejar operativo
el motor sin que el usuario memorice el procedimiento. El runbook, idempotente y
multiplataforma: (1) diagnostica el estado (`doctor --json`); (2) instala el
binario detectando el canal (`uv`/`pipx` si están, u ofrece instalar `uv` o el
instalador nativo por SO); (3) descarga el modelo (`setup`); (4) deja el daemon en
marcha (`daemon start`, requisito de `speak --daemon`); (5) activa la narración y,
opt-in, el modo LLM con sus claves; (6) verifica de extremo a extremo con una
narración de prueba. No acopla nada: conduce al motor solo por su CLI pública, con
las mismas reglas de seguridad del resto del plugin (sin `sudo`, sin claves en el
chat, degradación y avisos claros ante acciones manuales).

### Eventos de hook

| Evento | Rol en el plugin | Justificación |
|--------|------------------|---------------|
| `Stop` | **Narración principal** (una vez por turno) | El input incluye `last_assistant_message`; es la cadencia natural de "Claude terminó de responder". |
| `Notification` | **Narración de avisos** | El input trae `message` ya redactado y corto (espera de permiso, input requerido, idle); pasa por el mismo launcher con procesamiento mínimo. |
| `SessionStart` | **Chequeo de salud** | Aviso único si falta el CLI o el modelo; nunca en el camino de cada turno. |

`PostToolUse` se descarta deliberadamente: su frecuencia (cada tool call) es
demasiado alta para narración.

### `hooks/hooks.json`

Se usa el **exec form** (`command` + `args`): al ser `node` un ejecutable real
en los tres SO, el hook se lanza sin pasar por shell alguna — sin depender de
Git Bash vs PowerShell en Windows, sin diferencias de quoting entre shells, y
con las rutas resueltas por `${CLAUDE_PLUGIN_ROOT}` como argumentos literales:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node",
            "args": ["${CLAUDE_PLUGIN_ROOT}/dist/narrate-hook.js"],
            "timeout": 10
          }
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node",
            "args": ["${CLAUDE_PLUGIN_ROOT}/dist/narrate-hook.js"],
            "timeout": 10
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node",
            "args": ["${CLAUDE_PLUGIN_ROOT}/dist/health-check.js"],
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

El launcher distingue el evento por el campo `hook_event_name` del payload, así
un único script sirve a `Stop` y `Notification`.

## Generación del mensaje conversacional

El texto en bruto de Claude no se narra: contiene markdown, código y rutas.
El subsistema `message/` lo transforma en una locución breve y natural en
español. El diseño adapta las ideas de una implementación de referencia previa
(el módulo TTS de *EvolutiveX Agent Orchestrator*, que genera locuciones por
hook con una cadena Gemini → OpenRouter → fallback estático); se toman las
ideas validadas allí — no el código — y se ajustan a los requisitos de este
plugin (autocontenido, multiplataforma, costo cero, degradación total sin red).

### Proveedores: gratuitos por diseño

La generación usa LLMs solo en sus niveles gratuitos, con una cadena de dos
proveedores porque sus límites difieren:

| Prioridad | Proveedor | Modelo | Por qué |
|-----------|-----------|--------|---------|
| 1 (principal) | **Gemini API** (free tier) | Flash/Flash-Lite vigente | Mejor calidad/latencia, pero rate limit pequeño en el nivel gratuito (pocas RPM/RPD). |
| 2 (fallback) | **OpenRouter** | Modelos `:free` | Límites mucho más holgados; absorbe los 429 de Gemini y sus caídas. |
| 3 (degradación) | **Constructor local** | — (determinista, sin red) | Garantiza narración sin keys, sin red o con ambos proveedores caídos. |

Reglas de la cadena (`provider-chain.ts`):

- Un proveedor sin API key configurada se salta de inmediato (cuenta como
  fallo, sin request).
- Cualquier fallo — HTTP ≥ 400 (incluido 429 por rate limit), timeout,
  respuesta vacía — pasa al siguiente nivel. El **timeout por request es
  corto** (~8 s, `AbortSignal.timeout`): el worker ya corre desanclado, pero
  una locución que llega 30 s tarde ya no es conversacional.
- Las llamadas usan `fetch` nativo de Node — sin SDKs de proveedor, coherente
  con "cero dependencias en runtime".
- Parámetros de las requests: salida acotada (~512 tokens máx.) y *thinking*
  desactivado donde el proveedor lo soporte (en Gemini, `thinkingBudget: 0`) —
  optimiza latencia y consumo de cuota.

El **constructor local** (`local-builder.ts`) es el último nivel y también un
modo de primera clase (ver privacidad): produce el mensaje sin red, en dos
capas — primero un resumen determinista del `last_assistant_message` (strip de
markdown/código, primera(s) oración(es) prosa, truncado a largo narrable); si
no hay material utilizable, un texto estático por evento ("El asistente
terminó su turno", "Claude espera tu confirmación", …). Con esto la cadena
completa **nunca falla**: siempre hay algo que narrar.

### Modos de generación

El mensaje que se pide al LLM depende del evento; cada modo tiene su propio
system prompt (`prompts.ts`):

| Modo | Eventos | Qué genera |
|------|---------|------------|
| `summary` | `Stop` | Síntesis en alto nivel de lo realizado en el turno, una o dos frases, primera persona, parafraseado — no enumeración de pasos. |
| `notice` | `Notification` | El `message` del payload ya es corto y redactado: pasa directo al constructor local (limpieza ligera), **sin LLM** — no gasta cuota ni añade latencia. |

Contrato de salida común a todos los modos, impuesto por los system prompts y
verificado por `sanitize.ts`: texto plano apto para leerse en voz alta — sin
markdown, asteriscos, comillas, guiones ni símbolos; español; una o dos
oraciones. La sanitización se aplica también a la salida del LLM (los modelos
free no siempre obedecen el formato) antes de pasar el texto a `speak`.

*Extensión futura documentada*: la referencia valida también un modo `prompt`
sobre `UserPromptSubmit` (acuse de recibo por voz: "voy a investigar eso…"),
con una tríada curada de contexto (petición anterior + última respuesta +
prompt actual). Queda fuera del alcance inicial — duplica el consumo de cuota
por turno — pero el diseño de modos lo admite sin cambios estructurales.

### Contexto: payload primero, transcript como enriquecimiento

- **Fuente primaria**: `last_assistant_message` del payload de `Stop` — llega
  en el propio evento, sin I/O extra.
- **Enriquecimiento opcional**: los últimos N mensajes (N≈3) del transcript
  JSONL (`transcript_path`), leídos en streaming línea a línea, extrayendo
  solo bloques de texto de roles user/assistant y descartando líneas
  malformadas. Da al LLM el hilo de la conversación para resúmenes menos
  genéricos. Como el transcript puede ir retrasado respecto al turno, es
  complemento — nunca sustituto — del payload; si falta o falla la lectura, se
  continúa solo con el payload.

### Configuración y claves

`lib/config.ts` lee `stateDir()/config.json`; las variables de entorno
(`GEMINI_API_KEY`, `OPENROUTER_API_KEY`) tienen precedencia sobre el archivo:

```json
{
  "enabled": true,
  "messageMode": "llm",
  "geminiApiKey": "…",
  "openRouterApiKey": "…"
}
```

- `messageMode`: `"llm"` (cadena completa) o `"local"` (solo constructor
  determinista, sin red). Sin ninguna key configurada, `"llm"` degrada a
  `"local"` de facto.
- Las claves son del usuario (su suscripción free de Gemini, su cuenta de
  OpenRouter); el plugin nunca incluye claves propias. La skill opcional guía
  la configuración (`/tts-sidecar-narrator:narrate setup`).
- El archivo se crea con permisos restrictivos (0600 en POSIX) por contener
  credenciales.

### Privacidad

El modo `llm` envía contenido de la sesión (mensajes del asistente, extracto
del transcript) a un tercero (Google u OpenRouter). Es un cambio de postura
relevante respecto a TTS-Sidecar, cuya síntesis es 100 % offline. Por eso:

1. El modo `llm` solo se activa cuando el usuario configura sus claves — un
   acto explícito de opt-in que la skill de setup acompaña con este aviso.
2. `messageMode: "local"` ofrece la experiencia completa sin que ningún dato
   salga de la máquina, con mensajes menos elaborados.
3. El README del plugin documenta exactamente qué se envía y a quién.

## Estrategia multiplataforma

La paridad Windows / Linux / macOS es un requisito de primer orden, igual que
en TTS-Sidecar. Decisiones que la garantizan:

1. **Node.js como runtime, TypeScript como lenguaje.** Node está presente en
   toda instalación de Claude Code — es el runtime del propio CLI —, así que
   el plugin no añade **ningún** prerequisito de intérprete. Es la misma
   filosofía por la que TTS-Sidecar se compila nativo por SO (no obligar al
   usuario a instalar Python), trasladada al plugin: el usuario de Claude Code
   ya tiene Node; Python sería una exigencia extra. TypeScript aporta tipos en
   desarrollo (el payload de cada evento de hook se modela con interfaces) y
   desaparece en distribución: los hooks ejecutan JS compilado.

2. **Distribución compilada y autocontenida.** `src/*.ts` se bundlea con
   esbuild a un JS por entry point en `dist/`, sin `node_modules` en runtime
   (solo stdlib de Node: `child_process`, `fs`, `path`, `os`, y `fetch`
   nativo para los proveedores LLM). Instalar el
   plugin es clonar el repo; no hay `npm install` ni build en la máquina del
   usuario.

3. **Exec form en `hooks.json`.** `node` es un ejecutable real en los tres SO,
   así que los hooks se lanzan sin shell intermedia: se elimina la variable
   "¿qué shell hay en esta máquina?" (Git Bash vs PowerShell en Windows, sh en
   POSIX) y con ella toda una clase de bugs de quoting. Un único `hooks.json`
   sirve idéntico en los tres SO.

4. **Desanclaje sin ramas por SO.** `spawn(..., { detached: true, stdio:
   "ignore" })` + `unref()` es la semántica correcta en los tres SO con una
   sola API. La única bifurcación del plugin es la terminación del worker
   anterior (`process.kill(-pid)` en POSIX vs `taskkill /T` en Windows),
   encapsulada en `lib/spawn.ts` — mismo principio que aplica TTS-Sidecar en
   `paths.py` y `audio.py`.

5. **Rutas siempre vía `${CLAUDE_PLUGIN_ROOT}`** (portable por definición) y,
   dentro de los scripts, `node:path` — nunca separadores literales.

6. **State dir por convención de cada SO**, calculado en `lib/state-dir.ts`
   (equivalente en miniatura al `data_root()` de TTS-Sidecar, sin depender de
   él):

   | SO | `stateDir()` |
   |----|--------------|
   | Windows | `%LOCALAPPDATA%\tts-sidecar-narrator` |
   | Linux | `${XDG_STATE_HOME:-~/.local/state}/tts-sidecar-narrator` |
   | macOS | `~/Library/Application Support/tts-sidecar-narrator` |

   Contiene: `config.json` (toggle, `messageMode`, API keys),
   `worker.pid` (single-instance), `payload.json` (traspaso launcher→worker),
   `worker.log` (depuración).

7. **Resolución del CLI por PATH**, no por rutas de instalación: los tres
   instaladores nativos de TTS-Sidecar y el canal PyPI dejan `tts-sidecar` en
   el PATH, así que un único mecanismo cubre las seis combinaciones SO ×
   canal (en Windows se resuelve `tts-sidecar.exe`).

8. **Notificaciones al usuario vía `systemMessage`** en el JSON de salida del
   hook — el único mecanismo de aviso que Claude Code garantiza en los tres SO.

## Prerequisitos e instalación

El plugin no instala TTS-Sidecar (un plugin de Claude Code no gestiona
software del sistema); lo declara como prerequisito y lo verifica en
`SessionStart`:

1. **TTS-Sidecar** instalado por cualquiera de sus canales (instalador nativo
   o `uv tool install tts-sidecar`) y aprovisionado (`tts-sidecar setup`).
2. *(Opcional)* **API keys gratuitas** para los mensajes generados por LLM:
   Gemini (free tier) y/u OpenRouter (modelos `:free`). Sin ellas, el plugin
   funciona en modo local determinista.

Y nada más: Node ya está presente por ser el runtime de Claude Code, y los
scripts se distribuyen compilados. Instalación del plugin: durante el
desarrollo, `claude --plugin-dir ./tts-sidecar-narrator`; para distribución,
un marketplace propio (repo git) o el marketplace comunitario de Anthropic. El
versionado usa el campo `version` de `plugin.json`.

## Decisiones de diseño (registro)

| Decisión | Alternativas descartadas | Razón |
|----------|--------------------------|-------|
| Repositorio independiente para el plugin | Subdirectorio dentro de este repo | El acoplamiento real es solo la CLI pública; ciclos de vida y versionado disjuntos; la distribución de plugins (marketplaces) asume un repo git propio; CI sin nada en común. Ver [Ubicación de la implementación](#ubicación-de-la-implementación-repositorio-independiente). |
| TypeScript sobre Node como runtime de los scripts | Python; bash/PowerShell; binarios por SO | Node está garantizado en toda máquina con Claude Code (es su runtime); Python sería un prerequisito extra — la misma razón por la que TTS-Sidecar se compila nativo. bash/PowerShell no son multiplataforma. Binarios por SO: complejidad de build desproporcionada para scripts. |
| Distribuir JS compilado en `dist/` (commiteado) | Ejecutar TS directamente (`--experimental-strip-types`); build post-instalación | El type stripping nativo exige versiones recientes de Node y aún cambia entre versiones; un paso de build en la máquina del usuario rompería "instalar = clonar". Compilar en desarrollo y commitear `dist/` da ejecución universal con `node` a secas. |
| Exec form (`command: "node"` + `args`) en `hooks.json` | Shell form | `node` es un `.exe`/binario real en los tres SO, así que el exec form es portable y elimina la dependencia de la shell disponible (Git Bash vs PowerShell en Windows) y los bugs de quoting. |
| Launcher fire-and-forget + worker desanclado | Hook síncrono que espera la síntesis | El hook bloquea el turno de Claude Code; una síntesis tarda segundos (decenas en frío). |
| Scripts en `src/`→`dist/` del plugin root | Script dentro del directorio de la skill | Los hooks no leen skills; colgar el pipeline de la skill comunica una relación que no existe. La skill queda como componente opcional independiente. |
| Política *última narración gana* (interrumpir) | Encolar; descartar la nueva | En un asistente, el turno viejo caduca al llegar el nuevo; encolar acumula retraso creciente. |
| `speak --daemon` como camino por defecto | Modo directo en cada narración | El daemon amortiza la carga del modelo; es exactamente el caso de uso para el que existe (`docs/DAEMON-MODE.md`). |
| Constructor de mensajes como módulo TS del plugin | Reusar la implementación de referencia (EvolutiveX) vía subproceso o copia | Se adaptan sus ideas (cadena de providers, modos, fallbacks), no su código: la referencia es un orquestador con otro alcance; el plugin necesita una versión autocontenida y a medida de sus requisitos. |
| Cadena Gemini (free) → OpenRouter (`:free`) → local | Un solo proveedor; APIs de pago | Requisito de costo cero. Gemini free tiene mejor calidad pero rate limit pequeño; OpenRouter free absorbe los 429. El nivel local garantiza narración sin red/keys. Patrón validado en la implementación de referencia. |
| `Notification` sin LLM (modo `notice` local) | Pasar todos los eventos por el LLM | El `message` del payload ya es corto y redactado; el LLM solo añadiría latencia y gasto de cuota sin mejorar la locución. |
| `fetch` nativo sin SDKs de proveedor | SDKs oficiales (`@google/genai`, etc.) | Dos endpoints REST simples no justifican dependencias; preserva los bundles autocontenidos sin `node_modules`. |
| LLM invocado en el worker desanclado | Generar el mensaje en el launcher | Cualquier latencia de red en el launcher bloquearía el turno; en el worker es invisible para Claude Code (con timeout ~8 s para que la locución siga siendo oportuna). |
| Modo `llm` como opt-in explícito (keys del usuario) + modo `local` | LLM activo por defecto | El modo `llm` envía contenido de la sesión a terceros — postura opuesta al offline-first de TTS-Sidecar; debe ser una decisión informada del usuario. |
| Degradación silenciosa en el camino caliente + diagnóstico en `SessionStart` | Reportar errores en cada turno | Un hook ruidoso por turno arruina la sesión; el aviso único al arrancar es suficiente y accionable. |
| `last_assistant_message` como fuente primaria; transcript solo como enriquecimiento | Depender de `transcript_path` como fuente | El transcript puede ir retrasado respecto al turno actual; el campo del payload es la fuente canónica del evento `Stop`. El transcript aporta contexto conversacional al LLM, pero su ausencia o retraso nunca impide narrar. |

## Referencias

- [Create plugins](https://code.claude.com/docs/en/plugins) — estructura del plugin, `--plugin-dir`, distribución.
- [Plugins reference](https://code.claude.com/docs/en/plugins-reference) — esquema de `plugin.json`, `${CLAUDE_PLUGIN_ROOT}`.
- [Hooks reference](https://code.claude.com/docs/en/hooks) — eventos, JSON por stdin, timeouts, exit codes, exec form vs shell form en Windows.
- `docs/DAEMON-MODE.md` — daemon de TTS-Sidecar, la pieza que hace viable la latencia por turno.
- `docs/PARITY.md` — el estándar de paridad entre SO que este plugin hereda.
- *EvolutiveX Agent Orchestrator* (repo local, módulo TTS: `ITtsTextProvider`,
  `TtsTextProviderChain`, providers Gemini/OpenRouter, extractor de transcript
  y handler de hooks) — implementación de referencia de la que se adaptan las
  ideas de generación de mensajes conversacionales; no se reutiliza su código.
- [Gemini API — rate limits del free tier](https://ai.google.dev/gemini-api/docs/rate-limits) y
  [OpenRouter — modelos `:free`](https://openrouter.ai/models?max_price=0) — límites que motivan el orden de la cadena.
