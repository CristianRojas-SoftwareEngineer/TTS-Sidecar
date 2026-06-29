"""
Shared timing utilities for tts-sidecar.
"""

import time
from datetime import datetime
from functools import wraps


def log(msg: str, duration: float = None):
    """Print a log message with consistent formatting.

    Format: [HH:MM:SS] Message -> Done (Xs)
    If duration is None, just prints: [HH:MM:SS] Message...
    """
    now = datetime.now().strftime("%H:%M:%S")
    if duration is not None:
        print(f"[{now}] {msg} -> Done ({duration:.1f}s)")
    else:
        print(f"[{now}] {msg}...")


def timed_command(func):
    """Decorator to add timing info to CLI command functions.

    Logs command start and finish (no [HH:MM:SS] — timestamps are
    handled by StageTimer/log to avoid duplication).
    """
    @wraps(func)
    def wrapper(args):
        start_time = time.time()
        print(f"Starting {func.__name__.replace('cmd_', '')}...")
        try:
            result = func(args)
            elapsed = time.time() - start_time
            print(f"Finished in {elapsed:.1f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"Failed after {elapsed:.1f}s: {e}")
            raise
    return wrapper


def timed(stage_name: str):
    """Decorator that logs timing for a function as a stage.

    Usage:
        @timed("StageName")
        def my_function():
            print(f"[HH:MM:SS] [StageName] Doing stuff...")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            log(f"[{stage_name}]", duration)
            return result
        return wrapper
    return decorator


class StageTimer:
    """Context manager for timing a code block.

    Usage:
        with StageTimer("MyStage", "Description"):
            # code to time
            print(f"[HH:MM:SS] [MyStage] Doing stuff...")
    """

    def __init__(self, name: str, description: str = None):
        self.name = name
        self.description = description or name
        self.start = None

    def __enter__(self):
        self.start = time.time()
        log(f"[{self.name}] {self.description}...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start
        log(f"[{self.name}]", duration)
        return False
