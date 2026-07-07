# Descripción

<!-- Qué problema resuelve este PR y cómo. Enlaza el Issue relacionado si existe. -->

## Cómo verificarlo

<!-- Comandos o pasos para comprobar el cambio. -->

## Checklist

- [ ] `pytest tests/ -v` pasa en local (la suite corre en CI en Linux, Windows y macOS).
- [ ] Añadí tests para todo comportamiento nuevo o corregido.
- [ ] La documentación afectada (`USAGE.md`, `docs/`, `CLAUDE.md`) quedó sincronizada con el cambio.
- [ ] Si cambié `pyproject.toml`, regeneré `requirements-lock.txt` (y el lock CPU-only si aplica) y revisé el diff.
- [ ] Si cambiaron las dependencias empaquetadas, actualicé `THIRD-PARTY-LICENSES.md`.
- [ ] Mensajes de commit en español, con prefijo de tipo (`feat:`, `fix:`, `docs:`, …).
