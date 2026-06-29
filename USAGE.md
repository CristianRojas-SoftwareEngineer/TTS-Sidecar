# Guía de Uso de TTS Sidecar

## Instalación

### 1. Instalar dependencias Python

```bash
pip install chatterbox-tts
```

### 2. Ejecutar

```bash
# En desarrollo
python bin/tts-sidecar <comando>

# En Windows (después de compilar)
tts-sidecar.exe <comando>
```

## Comandos

---

### `version`

Muestra la versión del programa.

```bash
tts-sidecar version
```

---

### `doctor`

Verifica que todos los componentes estén disponibles.

```bash
tts-sidecar doctor
```

---

### `voices`

Lista las voces clonadas disponibles.

```bash
tts-sidecar voices
```

---

### `voice-add`

Registra una nueva voz clonada a partir de dos archivos de audio.

```bash
tts-sidecar voice-add --name mi_voz --reference timbre.wav --speech condicion.wav
```

**Opciones:**
- `--name, -n` (requerido): Nombre para la voz
- `--reference, -r` (requerido): Audio para timbre (cualquier largo — el audio completo se usa para el embedding)
- `--speech, -s` (requerido): Audio para conditioning (10+ segundos de habla limpia)

**¿Por qué dos archivos?**
- `reference.wav` → Voice Encoder: captura el timbre de la voz (prosodia, tono)
- `speech.wav` → T3 conditioning + S3Gen decoder: provee el patrón de habla

**Requisitos del audio:**
- Duración: Mínimo 6 segundos para `speech`, `reference` puede ser cualquier largo
- Idioma: Español latinoamericano
- Calidad: Sin ruido de fondo, habla clara
- Formato: WAV 16-bit

---

### `voice-remove`

Elimina una voz clonada.

```bash
tts-sidecar voice-remove --name mi_voz
```

---

### `devices`

Lista los dispositivos de audio disponibles.

```bash
tts-sidecar devices
```

---

### `speak`

Sintetiza texto y lo reproduce inmediatamente.

```bash
tts-sidecar speak --text "Hola mundo"
```

**Opciones:**
- `--text, -t` (requerido): Texto a sintetizar
- `--voice, -v`: Nombre de la voz clonada a usar (auto-carga reference.wav + speech.wav)
- `--voice-audio`: Ruta a archivo de audio para timbre (usa --speech si no se especifica)
- `--speech-audio`: Ruta a archivo de audio para conditioning (usa --voice-audio si no se especifica)
- `--daemon`: Usar el daemon si está disponible (default: automático)
- `--no-daemon`: Forzar modo directo, ignorar daemon
- `--device, -d`: Device para inferencia (`cpu`, `cuda`, `mps`)

**Ejemplo completo:**
```bash
# Usando voz registrada
tts-sidecar speak --text "Hola mundo" --voice mi_voz

# Usando archivos directamente
tts-sidecar speak --text "Hola" --voice-audio timbre.wav --speech-audio condicion.wav

# Forzar modo directo
tts-sidecar speak --text "Hola" --voice mi_voz --no-daemon
```

---

### `synthesize`

Genera un archivo WAV sin reproducir audio.

```bash
tts-sidecar synthesize --text "Hola mundo" --output output.wav
```

**Opciones:**
- `--text, -t` (requerido): Texto a sintetizar
- `--output, -o` (requerido): Ruta del archivo de salida
- `--voice, -v`: Nombre de la voz clonada a usar
- `--voice-audio`: Ruta a archivo de audio para timbre
- `--speech-audio`: Ruta a archivo de audio para conditioning
- `--daemon`: Usar el daemon si está disponible (default: automático)
- `--no-daemon`: Forzar modo directo, ignorar daemon
- `--device, -d`: Device para inferencia (`cpu`, `cuda`, `mps`)

**Ejemplo:**
```bash
tts-sidecar synthesize --text "Hola mundo" --voice mi_voz --output audio.wav
```

---

## Modo Daemon

El daemon mantiene el modelo cargado en memoria, evitando el tiempo de carga en cada invocación (~15–30s de overhead).

### Gestión del daemon

```bash
# Iniciar daemon (background)
tts-sidecar daemon start

# Ver estado
tts-sidecar daemon status

# Reiniciar
tts-sidecar daemon restart

# Detener
tts-sidecar daemon stop

# Auto-reinicio en caso de crash
tts-sidecar daemon start --autorestart --max-retries 3
```

### Uso con daemon

Por defecto, `speak` y `synthesize` intentan usar el daemon si está corriendo:

```bash
# El daemon se usa automáticamente si está disponible
tts-sidecar speak --text "Hola" --voice mi_voz

# Forzar modo daemon
tts-sidecar speak --text "Hola" --voice mi_voz --daemon

# Forzar modo directo (sin daemon)
tts-sidecar speak --text "Hola" --voice mi_voz --no-daemon
```

### Parámetros internos de síntesis

El daemon aplica valores optimizados automáticamente:

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `max_new_tokens` | 500 | Limita el output del T3 (default: 1000) |
| `n_cfm_timesteps` | 4 | Pasos de flow matching (default: 10) |
| `exaggeration` | 0.75 | Expressiveness emocional (default: 0.5) |

Los tiempos de `[Stage 2a]` (T3 autoregresivo) y `[Stage 2b]` (S3Gen vocoder) se muestran en el output cuando se usa el daemon.

---

## Clonación de voz

### Ejemplo completo

```bash
# 1. Grabar tu voz (~10 segundos de habla clara en español)
# timbre.wav - cualquier largo, captura tu timbre
# speech.wav - 10+ segundos, habla limpia para conditioning

# 2. Registrar la voz
tts-sidecar voice-add --name mi_voz --reference timbre.wav --speech speech.wav

# 3. Listar voces
tts-sidecar voices

# 4. Sintetizar con tu voz clonada
tts-sidecar speak --text "Hola, esto es una prueba" --voice mi_voz

# 5. Generar archivo
tts-sidecar synthesize --text "Hola, esto es una prueba" --voice mi_voz --output mi_voz.wav
```

---

## Formato de Audio

- **Generación**: 24000 Hz, Mono
- **Exportación WAV**: 16-bit PCM, 24000 Hz, Mono
- **Playback**: winsound en Windows, afplay en macOS, sounddevice en Linux

## Solución de Problemas

### "At least one audio file is required"

Se requiere al menos `--voice` o `--voice-audio` para sintetizar.

```bash
tts-sidecar speak --text "Hola" --voice mi_voz
```

### "Voice 'x' not found"

Verifica que la voz existe:

```bash
tts-sidecar voices
```

### "reference.wav/speech.wav not found"

La voz no tiene los archivos necesarios. Puede que se registró con el formato antiguo. Vuelve a registrar:

```bash
tts-sidecar voice-add --name mi_voz --reference timbre.wav --speech condicion.wav
```

### Sin audio de salida

1. Verifica que `tts-sidecar devices` detecta tu dispositivo
2. Comprueba que el volumen del sistema no está en mute
3. Verifica que el dispositivo de audio predeterminado es correcto
