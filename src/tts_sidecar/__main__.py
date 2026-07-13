"""Permite `python -m tts_sidecar` como vía de invocación equivalente al entry point.

Invoca la capa única de bootstrap explícitamente antes de importar el CLI,
simétrico con `bin/tts-sidecar` y `python -m tts_sidecar.daemon.run`.
"""

from . import bootstrap
bootstrap.apply()

from .cli import main

if __name__ == "__main__":
    main()
