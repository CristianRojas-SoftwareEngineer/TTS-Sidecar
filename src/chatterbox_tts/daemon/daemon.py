"""
Gestor del ciclo de vida del daemon de tts-sidecar.
Maneja los comandos start/stop/restart/status.
"""

import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import requests

from .. import paths


class DaemonManager:
    """
    Gestor del ciclo de vida del daemon de tts-sidecar.

    Maneja start/stop/restart/status. Funciona en Windows, Linux y macOS.
    """

    DEFAULT_PORT = 8765
    START_TIMEOUT = 120.0  # La carga del modelo + compilación tarda 30-90s

    def __init__(self, port: int = None):
        self.system = platform.system()
        self.port = port or self.DEFAULT_PORT
        self.base_url = f"http://127.0.0.1:{self.port}"

    def start(
        self,
        background: bool = True,
        auto_restart: bool = False,
        max_retries: int = 0,
    ) -> bool:
        """
        Inicia el daemon. Idempotente: si ya está corriendo, devuelve True.
        """
        # Si ya está corriendo no hay nada que hacer
        if self.is_running():
            print("Daemon ya está corriendo")
            return True

        # En modo congelado el ejecutable no acepta `-m módulo`,
        # así que se auto-invoca mediante su subcomando `daemon serve`.
        if paths.is_frozen():
            cmd = [sys.executable, "daemon", "serve", "--port", str(self.port)]
        else:
            cmd = [
                sys.executable,
                "-m", "chatterbox_tts.daemon.run",
                "--port", str(self.port),
            ]

        if auto_restart:
            cmd.append("--auto-restart")
        if max_retries > 0:
            cmd.extend(["--max-retries", str(max_retries)])

        if background:
            env = os.environ.copy()
            # Modo fuente: fijar PYTHONPATH para que el subproceso encuentre
            # chatterbox_tts. En modo congelado el ejecutable ya es autocontenido.
            if not paths.is_frozen():
                # __file__ es src/chatterbox_tts/daemon/daemon.py → 3 dirname = src/
                src_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                if os.path.exists(src_path):
                    env["PYTHONPATH"] = src_path

            if self.system == "Windows":
                subprocess.Popen(
                    cmd,
                    env=env,
                    creationflags=subprocess.DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

            # Esperar a que el daemon esté listo (la carga del modelo tarda)
            return self._wait_for_ready()
        else:
            # Modo primer plano (para depuración)
            subprocess.run(cmd)
            return True

    def stop(self, timeout: float = 10.0) -> bool:
        """
        Detiene el daemon. Devuelve True cuando el daemon ya no está corriendo.

        Intenta un cierre graceful vía HTTP; si el proceso sigue en el puerto
        tras el intento, lo mata por PID.
        """
        # Verificar si está corriendo
        if not self.is_running():
            # Aunque el health check falle, comprobar si algo ocupa el puerto
            pid = self._get_pid_from_port()
            if pid:
                self._kill_pid(pid)
            print("Daemon no está corriendo")
            return True

        # Cierre graceful vía HTTP
        try:
            requests.post(
                f"{self.base_url}/shutdown",
                timeout=timeout
            )
        except requests.RequestException:
            pass

        # Dar tiempo para que el cierre graceful termine
        time.sleep(0.5)

        # Si sigue corriendo, forzar terminación por PID
        if self.is_running():
            pid = self._get_pid_from_port()
            if pid:
                self._kill_pid(pid)

        return not self.is_running()

    def restart(self) -> bool:
        """Reinicia el daemon: detiene el existente y arranca uno nuevo."""
        print("Deteniendo daemon...")
        self.stop()
        time.sleep(1)
        print("Iniciando daemon...")
        return self.start()

    def status(self) -> dict:
        """Devuelve el estado del daemon."""
        if not self.is_running():
            return {"running": False}

        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "running": True,
                    "status": data.get("status"),
                    "model_loaded": data.get("model_loaded"),
                    "uptime_seconds": data.get("uptime_seconds"),
                }
        except requests.RequestException:
            pass

        return {"running": True, "status": "unknown"}

    def is_running(self) -> bool:
        """Comprueba si el daemon está corriendo y responde al health check."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False

    def _wait_for_ready(self, timeout: float = None) -> bool:
        """Espera hasta que el daemon esté listo para aceptar conexiones."""
        timeout = timeout or self.START_TIMEOUT
        start = time.time()

        print(f"Esperando que el daemon esté listo (timeout={timeout}s)...")
        while time.time() - start < timeout:
            if self.is_running():
                print("Daemon listo")
                return True
            time.sleep(1)

        print("Timeout esperando al daemon")
        return False

    def _get_pid_from_port(self) -> Optional[int]:
        """Devuelve el PID del proceso que escucha en el puerto del daemon."""
        try:
            if self.system == "Windows":
                # netstat -ano lista procesos con sus PIDs
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.splitlines():
                    if f":{self.port}" in line and "LISTENING" in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "LISTENING" and i < len(parts) - 1:
                                return int(parts[i + 1])
            else:
                # Unix: ss extrae el PID del campo "pid=NNNN"
                result = subprocess.run(
                    ["ss", "-tlnp"],
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.splitlines():
                    if f":{self.port}" in line:
                        import re
                        match = re.search(r"pid=(\d+)", line)
                        if match:
                            return int(match.group(1))
        except Exception:
            pass
        return None

    def _kill_pid(self, pid: int):
        """Mata un proceso por su PID."""
        try:
            if self.system == "Windows":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                             capture_output=True, timeout=5)
            else:
                os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
            pass
