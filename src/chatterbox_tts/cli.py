"""
CLI interface for Chatterbox TTS.
Consumable from any programming language via subprocess.
"""

import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

import argparse
import sys
import os
import platform
from pathlib import Path

from .timing import timed_command, StageTimer, log

# Lazy imports - only loaded when commands are executed
# This allows --help to work without dependencies installed


def _resolve_voice_paths(args):
    """Resolve voice audio paths from voice name WITHOUT loading the model."""
    import os
    from pathlib import Path

    voice_audio = getattr(args, 'voice_audio', None)
    speech_audio = getattr(args, 'speech_audio', None)

    if getattr(args, 'voice', None):
        # Resolve from filesystem directly - no model needed
        voices_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "voices",
            args.voice
        )
        ref_path = os.path.join(voices_dir, "reference.wav")
        speech_path = os.path.join(voices_dir, "speech.wav")
        if not os.path.exists(ref_path):
            raise FileNotFoundError(f"Voice '{args.voice}': reference.wav not found at {ref_path}")
        if not os.path.exists(speech_path):
            raise FileNotFoundError(f"Voice '{args.voice}': speech.wav not found at {speech_path}")
        voice_audio = ref_path
        speech_audio = speech_path

    return voice_audio, speech_audio


def _speak_via_daemon(args, voice_audio, speech_audio):
    """Try to speak via daemon, return True if successful."""
    import time
    import traceback

    try:
        from .daemon import DaemonIPCClient, is_daemon_running
        if not is_daemon_running():
            log("[Daemon] Daemon no está corriendo")
            return False

        synth_start = time.time()
        log("[Daemon] Enviando solicitud de síntesis...")
        client = DaemonIPCClient()
        audio_bytes = client.synthesize(
            text=args.text,
            voice_audio=voice_audio,
            speech_audio=speech_audio,
            model=args.model,
            device=args.device,
            compile_mode=getattr(args, 'compile', None),
        )
        elapsed = time.time() - synth_start
        log(f"[Daemon] Síntesis completada ({elapsed:.1f}s)")

        if args.output:
            with open(args.output, 'wb') as f:
                f.write(audio_bytes)
            log(f"[I/O] Audio guardado: {args.output}")
        else:
            log("[Playback] Reproduciendo audio...")
            from .audio import AudioPlayer
            player = AudioPlayer()
            player.play(audio_bytes)
            log("[Playback] Reproducción finalizada")
        return True
    except Exception as e:
        log(f"[Daemon] Error: {e}")
        traceback.print_exc()
        return False


@timed_command
def cmd_speak(args):
    """Synthesize text and play audio."""

    try:
        # Resolve voice audio paths WITHOUT loading model
        voice_audio, speech_audio = _resolve_voice_paths(args)

        # Try daemon if --daemon flag is set (default: try if available)
        use_daemon = getattr(args, 'daemon', False) or os.getenv('TTS_DAEMON_AUTOSTART')
        no_daemon = getattr(args, 'no_daemon', False)

        if use_daemon and not no_daemon:
            if _speak_via_daemon(args, voice_audio, speech_audio):
                return

        # Use direct mode - imports only loaded when daemon not used
        from .engine import ChatterboxEngine
        from .audio import AudioPlayer

        compile_mode = getattr(args, 'compile', None)
        engine = ChatterboxEngine.get_instance(model=args.model, device=args.device, compile_mode=compile_mode)

        audio_bytes = engine.speak(
            text=args.text,
            voice_audio=voice_audio,
            speech_audio=speech_audio,
        )

        if args.output:
            with open(args.output, 'wb') as f:
                f.write(audio_bytes)
            print(f"Audio saved to: {args.output}")
        else:
            log("[Playback] Reproduciendo audio...")
            player = AudioPlayer()
            player.play(audio_bytes)
            log("[Playback] Reproducción finalizada")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run 'tts-sidecar install' first.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _synthesize_via_daemon(args, voice_audio, speech_audio):
    """Try to synthesize via daemon, return True if successful."""
    import time

    try:
        from .daemon import DaemonIPCClient, is_daemon_running
        if not is_daemon_running():
            return False

        synth_start = time.time()
        log("[Daemon] Enviando solicitud de síntesis...")
        client = DaemonIPCClient()
        audio_bytes = client.synthesize(
            text=args.text,
            voice_audio=voice_audio,
            speech_audio=speech_audio,
            model=args.model,
            device=args.device,
            compile_mode=getattr(args, 'compile', None),
        )
        elapsed = time.time() - synth_start
        log(f"[Daemon] Síntesis completada ({elapsed:.1f}s)")

        with open(args.output, 'wb') as f:
            f.write(audio_bytes)
        log(f"[I/O] Audio guardado: {args.output}")
        return True
    except Exception:
        return False


@timed_command
def cmd_synthesize(args):
    """Synthesize text and save to file."""

    try:
        # Resolve voice audio paths WITHOUT loading model
        voice_audio, speech_audio = _resolve_voice_paths(args)

        # Try daemon if --daemon flag is set (default: try if available)
        use_daemon = getattr(args, 'daemon', False) or os.getenv('TTS_DAEMON_AUTOSTART')
        no_daemon = getattr(args, 'no_daemon', False)

        if use_daemon and not no_daemon:
            if _synthesize_via_daemon(args, voice_audio, speech_audio):
                return

        # Use direct mode - import only loaded when daemon not used
        from .engine import ChatterboxEngine

        compile_mode = getattr(args, 'compile', None)
        engine = ChatterboxEngine.get_instance(model=args.model, device=args.device, compile_mode=compile_mode)

        audio_bytes = engine.speak(
            text=args.text,
            output_path=args.output,
            voice_audio=voice_audio,
            speech_audio=speech_audio,
        )
        print(f"Audio saved to: {args.output}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run 'tts-sidecar install' first.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


@timed_command
def cmd_voice_add(args):
    """Add a voice clone from reference audio."""
    from .engine import ChatterboxEngine

    try:
        engine = ChatterboxEngine(device=args.device)
        ref_path, speech_path = engine.add_voice(
            name=args.name,
            reference_audio=args.reference,
            speech_audio=args.speech,
        )
        print(f"Voice '{args.name}' registered:")
        print(f"  timbre (reference): {ref_path}")
        print(f"  speech (conditioning): {speech_path}")

    except Exception as e:
        print(f"Error adding voice: {e}", file=sys.stderr)
        sys.exit(1)


@timed_command
def cmd_voice_remove(args):
    """Remove a registered voice."""
    from .engine import ChatterboxEngine

    try:
        engine = ChatterboxEngine(device=args.device)
        if engine.remove_voice(args.name):
            print(f"Voice '{args.name}' removed.")
        else:
            print(f"Voice '{args.name}' not found.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error removing voice: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_voices(args):
    """List all registered voices."""
    from .engine import ChatterboxEngine

    try:
        engine = ChatterboxEngine(device=args.device)
        voice_list = engine.list_voices()

        if voice_list:
            print("Registered voices:")
            for voice in voice_list:
                print(f"  - {voice}")
        else:
            print("No voices registered. Run:")
            print("  tts-sidecar voice-add --name myvoice --reference audio.wav")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run 'tts-sidecar install' first.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error listing voices: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_devices(args):
    """List audio output devices."""
    from .audio import get_audio_devices

    devices = get_audio_devices()
    print("Audio output devices:")
    for dev in devices:
        print(f"  [{dev['id']}] {dev['name']} (latency: {dev['latency']*1000:.1f}ms)")


def cmd_doctor(args):
    """Run diagnostic checks."""
    print("=== Chatterbox TTS Doctor ===\n")

    checks_passed = 0
    checks_failed = 0

    # Check Python version
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.system()} {platform.release()}")
    print()

    # Check Chatterbox
    try:
        import chatterbox
        print(f"[PASS] Chatterbox TTS: {chatterbox.__version__}")
        checks_passed += 1
    except ImportError:
        print("[FAIL] Chatterbox TTS: NOT INSTALLED")
        print("  Run: pip install chatterbox-tts")
        checks_failed += 1

    # Check audio library
    try:
        if platform.system() == "Windows":
            import pycaw
            print(f"[PASS] pycaw (Windows audio): installed")
        elif platform.system() == "Linux":
            import sounddevice
            print(f"[PASS] sounddevice (Linux audio): installed")
        elif platform.system() == "Darwin":
            import subprocess
            subprocess.run(["afplay"], check=True, capture_output=True)
            print(f"[PASS] afplay (macOS audio): available")
        checks_passed += 1
    except ImportError:
        print("[FAIL] Audio library: NOT INSTALLED")
        checks_failed += 1
    except Exception as e:
        print(f"[FAIL] Audio library: {e}")
        checks_failed += 1

    # Check model - verify Chatterbox can load (uses HF cache)
    try:
        from chatterbox.tts import ChatterboxTTS
        tts = ChatterboxTTS.from_pretrained(device="cpu")
        print(f"[PASS] Chatterbox model: loaded from cache")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] Chatterbox model: {e}")
        print("  Run: tts-sidecar install")
        checks_failed += 1

    # Check voices directory
    voices_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "voices"
    )
    if os.path.exists(voices_path):
        voices = [d for d in os.listdir(voices_path)
                  if os.path.isdir(os.path.join(voices_path, d))]
        print(f"[PASS] Voices directory: {len(voices)} voice(s) registered")
        checks_passed += 1
    else:
        print(f"[SKIP] Voices directory: not created yet (optional)")
        checks_passed += 1

    print()
    print(f"Checks: {checks_passed} passed, {checks_failed} failed")

    if checks_failed > 0:
        sys.exit(1)


def cmd_install(args):
    """Download and install the Chatterbox model."""
    print("=== Chatterbox TTS Installer ===\n")

    model_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "models",
        "chatterbox-multilingual"
    )
    Path(model_dir).mkdir(parents=True, exist_ok=True)

    print(f"Installing to: {model_dir}\n")

    try:
        from chatterbox.tts import ChatterboxTTS
        print("Downloading Chatterbox Multilingual V3 model...")
        print("(This may take several minutes on first run)\n")

        tts = ChatterboxTTS.from_pretrained(device="cpu")

        print("\n[PASS] Model downloaded successfully!")
        print(f"  Location: {model_dir}")

    except Exception as e:
        print(f"[FAIL] Installation failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_daemon(args):
    """Manage the tts-sidecar daemon."""
    from .daemon import DaemonManager

    manager = DaemonManager()

    if args.action == "start":
        success = manager.start(
            background=True,
            auto_restart=args.autorestart,
            max_retries=args.max_retries or 0,
        )
        if success:
            print("Daemon started successfully")
        else:
            print("Failed to start daemon", file=sys.stderr)
            sys.exit(1)

    elif args.action == "stop":
        if manager.stop():
            print("Daemon stopped")
        else:
            print("Failed to stop daemon", file=sys.stderr)
            sys.exit(1)

    elif args.action == "restart":
        if manager.restart():
            print("Daemon restarted")
        else:
            print("Failed to restart daemon", file=sys.stderr)
            sys.exit(1)

    elif args.action == "status":
        status = manager.status()
        if status.get("running"):
            print(f"Daemon running:")
            print(f"  Status: {status.get('status', 'unknown')}")
            print(f"  Model loaded: {status.get('model_loaded', False)}")
            print(f"  Uptime: {status.get('uptime_seconds', 0):.1f}s")
        else:
            print("Daemon not running")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="tts-sidecar",
        description="Chatterbox TTS - 100%% local voice cloning TTS"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # speak command
    speak_parser = subparsers.add_parser("speak", help="Synthesize and play audio")
    speak_parser.add_argument("--text", "-t", required=True, help="Text to synthesize")
    speak_parser.add_argument("--voice", "-v", help="Voice name to use (auto-loads reference.wav + speech.wav)")
    speak_parser.add_argument("--language", "-l", help="Language code (default: es)")
    speak_parser.add_argument("--output", "-o", help="Output WAV file path")
    speak_parser.add_argument("--device", "-d", default="cpu",
                              choices=["cpu", "cuda", "mps"],
                              help="Device for inference (default: cpu)")
    speak_parser.add_argument("--model", "-m", default="es-latam",
                              choices=["multilingual", "es-latam"],
                              help="Model to use: 'es-latam' (LatAm Spanish, RECOMMENDED) or 'multilingual' (default: es-latam)")
    speak_parser.add_argument("--voice-audio",
                              help="Audio file for Voice Encoder (full audio for timbre embedding)")
    speak_parser.add_argument("--speech-audio",
                              help="Audio file for T3 conditioning (6s) + S3Gen decoder (10s). "
                                   "Use a clean speech segment (10s+ recommended).")
    speak_parser.add_argument("--compile", "-c", nargs="?", const="default",
                              choices=["default", "reduce-overhead", "max-autotune"],
                              help="Enable torch.compile for faster CPU inference. "
                                   "Modes: default, reduce-overhead, max-autotune. "
                                   "Default mode is 'default' if flag is present without a value.")
    speak_parser.add_argument("--daemon", action="store_true",
                              help="Use daemon if available (default: auto)")
    speak_parser.add_argument("--no-daemon", action="store_true",
                              help="Force direct mode, ignore daemon")
    speak_parser.set_defaults(func=cmd_speak)

    # synthesize command
    synth_parser = subparsers.add_parser("synthesize", help="Synthesize and save audio")
    synth_parser.add_argument("--text", "-t", required=True, help="Text to synthesize")
    synth_parser.add_argument("--voice", "-v", help="Voice name to use (auto-loads reference.wav + speech.wav)")
    synth_parser.add_argument("--output", "-o", required=True, help="Output WAV file path")
    synth_parser.add_argument("--device", "-d", default="cpu",
                              choices=["cpu", "cuda", "mps"],
                              help="Device for inference (default: cpu)")
    synth_parser.add_argument("--model", "-m", default="es-latam",
                              choices=["multilingual", "es-latam"],
                              help="Model to use: 'es-latam' (LatAm Spanish, RECOMMENDED) or 'multilingual' (default: es-latam)")
    synth_parser.add_argument("--voice-audio",
                              help="Audio file for Voice Encoder (full audio for timbre embedding)")
    synth_parser.add_argument("--speech-audio",
                              help="Audio file for T3 conditioning (6s) + S3Gen decoder (10s). "
                                   "Use a clean speech segment (10s+ recommended).")
    synth_parser.add_argument("--compile", "-c", nargs="?", const="default",
                              choices=["default", "reduce-overhead", "max-autotune"],
                              help="Enable torch.compile for faster CPU inference. "
                                   "Modes: default, reduce-overhead, max-autotune. "
                                   "Default mode is 'default' if flag is present without a value.")
    synth_parser.add_argument("--daemon", action="store_true",
                              help="Use daemon if available (default: auto)")
    synth_parser.add_argument("--no-daemon", action="store_true",
                              help="Force direct mode, ignore daemon")
    synth_parser.set_defaults(func=cmd_synthesize)

    # voice-add command
    voice_add_parser = subparsers.add_parser("voice-add", help="Add a voice clone")
    voice_add_parser.add_argument("--name", "-n", required=True, help="Voice name")
    voice_add_parser.add_argument("--reference", "-r", required=True,
                                  help="Reference audio file for voice timbre (any length, full audio used)")
    voice_add_parser.add_argument("--speech", "-s", required=True,
                                  help="Speech audio file for T3 conditioning (10+ seconds of clean speech)")
    voice_add_parser.add_argument("--device", "-d", default="cpu",
                              choices=["cpu", "cuda", "mps"],
                              help="Device for inference (default: cpu)")
    voice_add_parser.set_defaults(func=cmd_voice_add)

    # voice-remove command
    voice_rm_parser = subparsers.add_parser("voice-remove", help="Remove a voice")
    voice_rm_parser.add_argument("--name", "-n", required=True, help="Voice name")
    voice_rm_parser.add_argument("--device", "-d", default="cpu",
                              choices=["cpu", "cuda", "mps"],
                              help="Device for inference (default: cpu)")
    voice_rm_parser.set_defaults(func=cmd_voice_remove)

    # voices command
    voices_parser = subparsers.add_parser("voices", help="List registered voices")
    voices_parser.add_argument("--device", "-d", default="cpu",
                              choices=["cpu", "cuda", "mps"],
                              help="Device for inference (default: cpu)")
    voices_parser.set_defaults(func=cmd_voices)

    # devices command
    devices_parser = subparsers.add_parser("devices", help="List audio devices")
    devices_parser.set_defaults(func=cmd_devices)

    # doctor command
    doctor_parser = subparsers.add_parser("doctor", help="Run diagnostics")
    doctor_parser.set_defaults(func=cmd_doctor)

    # install command
    install_parser = subparsers.add_parser("install", help="Install the TTS model")
    install_parser.set_defaults(func=cmd_install)

    # daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Daemon lifecycle management")
    daemon_subparsers = daemon_parser.add_subparsers(dest="action", help="Daemon actions")

    daemon_start = daemon_subparsers.add_parser("start", help="Start the daemon")
    daemon_start.add_argument("--autorestart", action="store_true", help="Auto-restart on crash")
    daemon_start.add_argument("--max-retries", type=int, help="Max restart attempts")
    daemon_start.set_defaults(func=cmd_daemon)

    daemon_stop = daemon_subparsers.add_parser("stop", help="Stop the daemon")
    daemon_stop.set_defaults(func=cmd_daemon)

    daemon_restart = daemon_subparsers.add_parser("restart", help="Restart the daemon")
    daemon_restart.set_defaults(func=cmd_daemon)

    daemon_status = daemon_subparsers.add_parser("status", help="Show daemon status")
    daemon_status.set_defaults(func=cmd_daemon)

    # version command
    version_parser = subparsers.add_parser("version", help="Show version")
    version_parser.set_defaults(func=lambda args: print("tts-sidecar 0.1.0"))

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
