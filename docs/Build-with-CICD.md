# CircleCI Build Pipeline

> **OBSOLETO — Proyecto migrado a Python + Nuitka.** Este documento describía el pipeline CircleCI para la arquitectura Rust. El proyecto actual usa Python + Nuitka (ver `BUILD.md`). Se mantiene por referencia histórica.

Este documento describe el pipeline de CircleCI para compilar `tts-sidecar` en múltiples plataformas.

## Arquitectura del Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                      Pipeline                                 │
│                   (multijob)                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │build-win64  │  │build-lin64  │  │build-linarm │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                 │                 │                 │
│         ▼                 ▼                 ▼                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │build-darwin │  │build-darwin │                          │
│  │    x64      │  │   arm64     │                          │
│  └─────────────┘  └─────────────┘                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Plataformas Soportadas

| Job | Plataforma | Target Rust | Executor | Notas |
|-----|------------|-------------|----------|-------|
| `build-windows` | Windows x64 | `x86_64-pc-windows-msvc` | `windows-server` | MSVC toolchain |
| `build-linux-x64` | Linux x64 | `x86_64-unknown-linux-gnu` | `ubuntu` | GCC |
| `build-linux-arm64` | Linux ARM64 | `aarch64-unknown-linux-gnu` | `ubuntu` | Cross-compile |
| `build-darwin-x64` | macOS Intel | `x86_64-apple-darwin` | `macos` | Clang |
| `build-darwin-arm64` | macOS Apple Silicon | `aarch64-apple-darwin` | `macos` | Cross-compile |

## Configuración

### Configuración básica del proyecto

1. Ve a CircleCI dashboard → Project Settings → Environment Variables
2. Agrega las siguientes variables si es necesario:
   - `CARGO_HOME`: Directorio de Cargo (generalmente auto-configurado)
   - `RUST_BACKTRACE`: `1` para mejor debugging en errores

### Pasos para configurar

1. Crea el archivo `.circleci/config.yml` en la raíz del proyecto
2. Configura los workflows según se describe abajo
3. Conecta el proyecto con CircleCI
4. Haz push del archivo de configuración
5. Los artifacts se almacenarán automáticamente en CircleCI

## Estructura del Workflow

```yaml
version: 2.1

orbs:
  rust: circleci/rust@1.0.0

jobs:
  build-windows:
    executor: windows-server
    steps:
      - checkout
      - rust/install:
          version: stable
      - run:
          name: Add target
          command: rustup target add x86_64-pc-windows-msvc
      - run:
          name: Build
          command: cargo build --release --target x86_64-pc-windows-msvc
      - run:
          name: Strip symbols
          command: |
            if [ -f "target/x86_64-pc-windows-msvc/release/tts-sidecar.exe" ]; then
              strip target/x86_64-pc-windows-msvc/release/tts-sidecar.exe
            fi
      - store_artifacts:
          path: target/x86_64-pc-windows-msvc/release/tts-sidecar.exe
          destination: tts-sidecar-win32-x64.exe

  build-linux-x64:
    executor: ubuntu
    steps:
      - checkout
      - rust/install:
          version: stable
      - run:
          name: Add target
          command: rustup target add x86_64-unknown-linux-gnu
      - run:
          name: Build
          command: cargo build --release --target x86_64-unknown-linux-gnu
      - run:
          name: Strip symbols
          command: |
            if [ -f "target/x86_64-unknown-linux-gnu/release/tts-sidecar" ]; then
              strip target/x86_64-unknown-linux-gnu/release/tts-sidecar
            fi
      - store_artifacts:
          path: target/x86_64-unknown-linux-gnu/release/tts-sidecar
          destination: tts-sidecar-linux-x64

  build-linux-arm64:
    executor: ubuntu
    steps:
      - checkout
      - rust/install:
          version: stable
      - run:
          name: Install cross-compile toolchain
          command: |
            sudo apt-get update
            sudo apt-get install -y gcc-aarch64-linux-gnu g++-aarch64-linux-gnu
      - run:
          name: Add target
          command: rustup target add aarch64-unknown-linux-gnu
      - run:
          name: Configure cross-compile
          command: |
            echo '[target.aarch64-unknown-linux-gnu]
            linker = "aarch64-linux-gnu-gcc"' >> .cargo/config.toml
      - run:
          name: Build
          command: cargo build --release --target aarch64-unknown-linux-gnu
      - run:
          name: Strip symbols
          command: |
            if [ -f "target/aarch64-unknown-linux-gnu/release/tts-sidecar" ]; then
              aarch64-linux-gnu-strip target/aarch64-unknown-linux-gnu/release/tts-sidecar
            fi
      - store_artifacts:
          path: target/aarch64-unknown-linux-gnu/release/tts-sidecar
          destination: tts-sidecar-linux-arm64

  build-darwin-x64:
    executor: macos
    steps:
      - checkout
      - rust/install:
          version: stable
      - run:
          name: Add target
          command: rustup target add x86_64-apple-darwin
      - run:
          name: Build
          command: cargo build --release --target x86_64-apple-darwin
      - run:
          name: Strip symbols
          command: |
            if [ -f "target/x86_64-apple-darwin/release/tts-sidecar" ]; then
              strip target/x86_64-apple-darwin/release/tts-sidecar
            fi
      - store_artifacts:
          path: target/x86_64-apple-darwin/release/tts-sidecar
          destination: tts-sidecar-darwin-x64

  build-darwin-arm64:
    executor: macos
    steps:
      - checkout
      - rust/install:
          version: stable
      - run:
          name: Add target
          command: rustup target add aarch64-apple-darwin
      - run:
          name: Build
          command: cargo build --release --target aarch64-apple-darwin
      - run:
          name: Strip symbols
          command: |
            if [ -f "target/aarch64-apple-darwin/release/tts-sidecar" ]; then
              strip target/aarch64-apple-darwin/release/tts-sidecar
            fi
      - store_artifacts:
          path: target/aarch64-apple-darwin/release/tts-sidecar
          destination: tts-sidecar-darwin-arm64

workflows:
  build-all:
    jobs:
      - build-windows
      - build-linux-x64
      - build-linux-arm64
      - build-darwin-x64
      - build-darwin-arm64
```

## Descarga de Artifacts

Después de que el pipeline complete:

1. Ve a CircleCI Dashboard → Jobs
2. Selecciona el job completado
3. Click en el artifact o usa la API para descargar:

```bash
# Usando CircleCI CLI
circleci workflow output <workflow-id> <job-name> --destination ./artifacts/

# API de CircleCI
curl -X GET "https://circleci.com/api/v2/project/<project-slug>/<job-id>/artifacts" \
  -H "Circle-Token: <token>"
```

## Distribución Manual de Binarios

Los binarios compilados deben copiarse manualmente a `bin/<platform>/`:

```bash
# Crear estructura de directorios
mkdir -p bin/win32-x64 bin/linux-x64 bin/linux-arm64 bin/darwin-x64 bin/darwin-arm64

# Copiar binarios (ejemplo usando artifacts de CircleCI)
cp tts-sidecar-win32-x64.exe bin/win32-x64/tts-sidecar.exe
cp tts-sidecar-linux-x64 bin/linux-x64/tts-sidecar
cp tts-sidecar-linux-arm64 bin/linux-arm64/tts-sidecar
cp tts-sidecar-darwin-x64 bin/darwin-x64/tts-sidecar
cp tts-sidecar-darwin-arm64 bin/darwin-arm64/tts-sidecar

# Asegurar permisos de ejecución
chmod +x bin/linux-*/tts-sidecar bin/darwin-*/tts-sidecar

# Verificar estructura
ls -la bin/*/
```

## Configuración de Retención de Artifacts

Por defecto, CircleCI retiene artifacts por 30 días. Para cambiar esto:

1. Project Settings → Storage
2. Configura la política de retención según necesidades

## Notas Importantes

- **macOS**: Los jobs de macOS pueden tomar más tiempo debido a las limitaciones de recursos
- **Cross-compile ARM64**: Requiere toolchain adicional instalado en el executor
- **Strip symbols**: Reduce significativamente el tamaño del binario (de ~50MB a ~20MB)
- **Windows**: Usa MSVC toolchain que viene preinstalado en los ejecutores de CircleCI
