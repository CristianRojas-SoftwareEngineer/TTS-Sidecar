# Publicación de una versión (RELEASING.md)

`tts-sidecar` no tiene publicación automática: sin firma de código (R-38), el
runbook manual y el cotejo de checksums SHA-256 contra el log del pipeline son
la única cadena de verificación de integridad disponible para el usuario final.
Este documento es el flujo que ejecuta el propietario del repositorio para
cortar y publicar una versión.

## Prerequisitos

- El gate de la auditoría vigente (`docs/PROJECT-REVIEW.md`) está cerrado: sin
  hallazgos Bloqueantes ni Mayores abiertos.
- `CHANGELOG.md` tiene la sección de la versión a publicar cortada (no
  "No publicado"), con las entradas reales de esa versión.
- La suite pasa en los tres SO (`test-linux`, `test-windows`, `test-macos` en
  verde en CircleCI para el commit a taggear).

## 1. Corte: crear y publicar el tag

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

El push del tag dispara el workflow `build-all` en CircleCI sobre ese commit
(mismo pipeline que corre en cada push: triple puerta de tests + 4 builds).

## 2. Build: esperar el pipeline verde

Espera a que los 4 jobs de build (`build-windows`, `build-linux-x64`,
`build-linux-arm64`, `build-darwin-arm64`) terminen en verde. Cada uno emite en
su step **"Emit artifact SHA-256"** el hash del artefacto que acaba de generar
— anota estos 4 valores del log del pipeline; son la referencia contra la que
se cotejan los artefactos descargados en el paso 4.

## 3. Recolección: descargar los 4 artefactos

Desde la pestaña **Artifacts** de cada job en CircleCI, descarga:

| Job | Artefacto |
|-----|-----------|
| `build-windows` | `tts-sidecar-win32-x86_64-setup.exe` |
| `build-linux-x64` | `tts-sidecar-linux-x86_64.AppImage` |
| `build-linux-arm64` | `tts-sidecar-linux-aarch64.AppImage` |
| `build-darwin-arm64` | `tts-sidecar-darwin-arm64.dmg` |

Renómbralos localmente a su nombre de release (`tts-sidecar-X.Y.Z-x86_64-setup.exe`,
`tts-sidecar-X.Y.Z-x86_64.AppImage`, `tts-sidecar-X.Y.Z-aarch64.AppImage`,
`tts-sidecar-X.Y.Z-arm64.dmg`).

## 4. Checksums: generar y cotejar `SHA256SUMS.txt`

```bash
sha256sum tts-sidecar-X.Y.Z-* > SHA256SUMS.txt
cat SHA256SUMS.txt
```

Cada línea debe coincidir exactamente con el hash emitido por el job
correspondiente en el paso 2. Si algún hash no coincide, **no publiques**: el
artefacto se corrompió en la descarga o el build no es el que se probó — repite
la descarga o investiga antes de continuar.

## 5. Publicación: GitHub Release

Crea el Release sobre el tag `vX.Y.Z`:

```bash
gh release create vX.Y.Z \
  tts-sidecar-X.Y.Z-x86_64-setup.exe \
  tts-sidecar-X.Y.Z-x86_64.AppImage \
  tts-sidecar-X.Y.Z-aarch64.AppImage \
  tts-sidecar-X.Y.Z-arm64.dmg \
  SHA256SUMS.txt \
  --title "vX.Y.Z" \
  --notes-from-tag
```

Las notas del Release deben incluir (o enlazar) la sección correspondiente de
`CHANGELOG.md`.

## 6. Verificación del usuario final

El usuario final puede verificar la integridad de su descarga contra
`SHA256SUMS.txt` publicado en el Release:

```bash
# Linux/macOS
sha256sum -c SHA256SUMS.txt --ignore-missing

# Windows (PowerShell)
Get-FileHash tts-sidecar-X.Y.Z-x86_64-setup.exe -Algorithm SHA256
# comparar manualmente contra la línea correspondiente de SHA256SUMS.txt
```

Ver también `SECURITY.md` para el modelo de amenaza y la nota sobre binarios
sin firmar.
