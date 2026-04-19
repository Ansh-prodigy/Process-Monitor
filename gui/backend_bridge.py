# -*- coding: utf-8 -*-
"""
backend_bridge.py - Production-quality bridge between the C++ Process Monitor
backend and a Python GUI (Tkinter).

Responsibilities:
    - Execute the compiled C++ binary via subprocess.
    - Parse JSON / plain-text output from the backend.
    - Return well-typed results to the GUI layer.
    - Handle every failure mode without raising into the GUI event loop.

Typical usage:

    from backend_bridge import BackendBridge

    bridge = BackendBridge()                          # auto-detects binary
    processes = bridge.list_processes()                # List[Dict[str, Any]]
    ok        = bridge.kill_process(1234)              # bool
    ok        = bridge.change_priority(1234, value=-5) # bool

    # Non-blocking call for Tkinter integration:
    bridge.list_processes_async(root, on_done=my_callback)

Architecture notes:

* BackendBridge is the public interface.  All configuration (binary path,
  timeout, retry policy, cache TTL, log level) is injected through the
  constructor -- no global state.
* Every public method returns a deterministic type and never raises.
  Errors are logged and surfaced through empty results or False returns.
* _execute is the single chokepoint for subprocess calls, making it easy
  to mock for testing.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────
_IS_WINDOWS: bool = platform.system() == "Windows"
_BACKEND_NAME: str = "backend.exe" if _IS_WINDOWS else "backend"
_DEFAULT_TIMEOUT_SECONDS: float = 10.0
_DEFAULT_RETRY_ATTEMPTS: int = 2
_DEFAULT_RETRY_DELAY_SECONDS: float = 0.5
_DEFAULT_CACHE_TTL_SECONDS: float = 1.0  # keep process list for 1 s

# Whitelist of commands recognised by the C++ backend (from main.cpp).
_VALID_COMMANDS: frozenset[str] = frozenset(
    {"list", "kill", "pause", "resume", "priority"}
)

# Pattern for validating numeric arguments (PIDs, priority values).
_INT_ARG_RE: re.Pattern[str] = re.compile(r"^-?\d+$")


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class BackendResult:
    """Immutable container returned by every backend call.

    Attributes:
        success:   ``True`` when the subprocess returned exit-code 0 and
                   output was parsed correctly.
        data:      Parsed JSON data (usually ``list[dict]`` for ``list``
                   command; ``str`` for action commands).
        error_msg: Human-readable explanation of what went wrong, or
                   ``None`` on success.
        raw:       Unprocessed stdout (useful for debugging).
    """

    success: bool
    data: Any = None
    error_msg: Optional[str] = None
    raw: str = ""


@dataclass
class _CacheEntry:
    """Internal cache entry with a timestamp."""

    timestamp: float
    data: List[Dict[str, Any]]


# ──────────────────────────────────────────────────────────────────────
# Helper – locate the backend binary
# ──────────────────────────────────────────────────────────────────────
def _resolve_backend_path(hint: Optional[Union[str, Path]] = None) -> Path:
    """Attempt to locate the backend binary.

    Resolution order:
        1. Explicit *hint* (if provided and exists).
        2. ``PROCESS_MONITOR_BACKEND`` environment variable.
        3. ``../backend/<binary>`` relative to **this** file.
        4. ``PATH`` lookup via :func:`shutil.which`.

    Returns:
        Resolved :class:`Path` to the binary.

    Raises:
        FileNotFoundError: When the binary cannot be found anywhere.
    """
    candidates: List[Path] = []

    # 1. Explicit hint
    if hint is not None:
        candidates.append(Path(hint).resolve())

    # 2. Environment variable
    env_path = os.environ.get("PROCESS_MONITOR_BACKEND")
    if env_path:
        candidates.append(Path(env_path).resolve())

    # 3. Relative to this file
    this_dir = Path(__file__).resolve().parent
    candidates.append(this_dir.parent / "backend" / _BACKEND_NAME)

    # 4. PATH lookup
    which_result = shutil.which(_BACKEND_NAME)
    if which_result:
        candidates.append(Path(which_result).resolve())

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    searched = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"Backend binary '{_BACKEND_NAME}' not found. Searched: {searched}"
    )


# ──────────────────────────────────────────────────────────────────────
# Input validation helpers
# ──────────────────────────────────────────────────────────────────────
def _validate_command(command: str) -> None:
    """Raise ``ValueError`` if *command* is not in the known set."""
    if command not in _VALID_COMMANDS:
        raise ValueError(
            f"Unknown command '{command}'. "
            f"Valid commands: {', '.join(sorted(_VALID_COMMANDS))}"
        )


def _validate_int_arg(value: Any, name: str = "argument") -> str:
    """Return *value* as a validated string suitable for subprocess args.

    Raises:
        ValueError: If *value* is not a valid integer representation.
    """
    s = str(value).strip()
    if not _INT_ARG_RE.match(s):
        raise ValueError(
            f"Invalid {name}: '{value}'. Expected an integer."
        )
    return s


# ──────────────────────────────────────────────────────────────────────
# BackendBridge
# ──────────────────────────────────────────────────────────────────────
class BackendBridge:
    """High-level, thread-safe bridge to the C++ process-monitor backend.

    Parameters:
        backend_path:   Explicit path to the compiled binary.  When
                        ``None``, the constructor will auto-resolve using
                        :func:`_resolve_backend_path`.
        timeout:        Maximum seconds to wait for each subprocess call.
        retries:        How many times to retry a failed command (total
                        attempts = 1 + retries).
        retry_delay:    Seconds to sleep between retry attempts.
        cache_ttl:      How long (seconds) to cache the ``list`` result.
                        Set to ``0`` or negative to disable caching.
        log_level:      Logging level (e.g. ``logging.DEBUG``).  Defaults
                        to ``logging.WARNING`` so that only problems are
                        printed in production.

    Example::

        bridge = BackendBridge(
            backend_path="/opt/pm/backend",
            timeout=5,
            retries=3,
            cache_ttl=2.0,
            log_level=logging.DEBUG,
        )
    """

    def __init__(
        self,
        backend_path: Optional[Union[str, Path]] = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        retries: int = _DEFAULT_RETRY_ATTEMPTS,
        retry_delay: float = _DEFAULT_RETRY_DELAY_SECONDS,
        cache_ttl: float = _DEFAULT_CACHE_TTL_SECONDS,
        log_level: int = logging.WARNING,
    ) -> None:
        # ── Logging ──────────────────────────────────────────────────
        self._log: logging.Logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )
        if not self._log.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self._log.addHandler(handler)
        self._log.setLevel(log_level)

        # ── Backend binary ───────────────────────────────────────────
        try:
            self._backend_path: Path = _resolve_backend_path(backend_path)
        except FileNotFoundError as exc:
            self._log.error("Backend resolution failed: %s", exc)
            # Store None so public methods can fail gracefully instead
            # of blowing up during construction.
            self._backend_path = None  # type: ignore[assignment]

        self._log.info("Backend binary: %s", self._backend_path)

        # ── Configuration ────────────────────────────────────────────
        self._timeout: float = max(timeout, 0.5)
        self._retries: int = max(retries, 0)
        self._retry_delay: float = max(retry_delay, 0.0)
        self._cache_ttl: float = cache_ttl

        # ── Cache (only for "list") ──────────────────────────────────
        self._cache: Optional[_CacheEntry] = None
        self._cache_lock: threading.Lock = threading.Lock()

    # ─────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────
    @property
    def backend_path(self) -> Optional[Path]:
        """Resolved path to the backend binary (``None`` if unresolved)."""
        return self._backend_path

    @property
    def is_available(self) -> bool:
        """``True`` when the backend binary exists on disk."""
        return self._backend_path is not None and self._backend_path.is_file()

    # ─────────────────────────────────────────────────────────────
    # Low-level execution
    # ─────────────────────────────────────────────────────────────
    def _execute(
        self,
        command: str,
        args: Sequence[str] = (),
    ) -> BackendResult:
        """Run the backend binary with *command* and optional *args*.

        This is the **single chokepoint** for all subprocess invocations.
        It handles timeout, non-zero exit codes, missing binary, and
        retries.  It never raises.

        Args:
            command: Backend command (``list``, ``kill``, …).
            args:    Additional string arguments (e.g. PID).

        Returns:
            A :class:`BackendResult` with raw stdout on success.
        """
        # ── Pre-flight checks ────────────────────────────────────────
        if self._backend_path is None:
            msg = "Backend binary path is not configured."
            self._log.error(msg)
            return BackendResult(success=False, error_msg=msg)

        if not self._backend_path.is_file():
            msg = f"Backend binary not found at '{self._backend_path}'."
            self._log.error(msg)
            return BackendResult(success=False, error_msg=msg)

        try:
            _validate_command(command)
        except ValueError as exc:
            self._log.error("Command validation error: %s", exc)
            return BackendResult(success=False, error_msg=str(exc))

        cmd_list: List[str] = [str(self._backend_path), command, *args]
        self._log.debug("Executing: %s", " ".join(cmd_list))

        # ── Execute with retries ─────────────────────────────────────
        last_error: str = ""
        for attempt in range(1, self._retries + 2):  # 1-indexed
            try:
                proc = subprocess.run(
                    cmd_list,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                    shell=False,  # explicit for security
                )

                if proc.returncode != 0:
                    stderr_text = proc.stderr.strip()
                    last_error = (
                        f"Backend exited with code {proc.returncode}"
                        + (f": {stderr_text}" if stderr_text else "")
                    )
                    self._log.warning(
                        "Attempt %d/%d failed — %s",
                        attempt,
                        self._retries + 1,
                        last_error,
                    )
                else:
                    self._log.debug(
                        "Command '%s' succeeded (attempt %d).",
                        command,
                        attempt,
                    )
                    return BackendResult(
                        success=True,
                        raw=proc.stdout,
                    )

            except subprocess.TimeoutExpired:
                last_error = (
                    f"Backend timed out after {self._timeout}s "
                    f"(attempt {attempt}/{self._retries + 1})."
                )
                self._log.warning(last_error)

            except FileNotFoundError:
                last_error = (
                    f"Backend binary not found: '{self._backend_path}'."
                )
                self._log.error(last_error)
                # No point retrying if the binary is missing.
                return BackendResult(success=False, error_msg=last_error)

            except PermissionError:
                last_error = (
                    f"Permission denied executing '{self._backend_path}'. "

                    "Check file permissions."
                )
                self._log.error(last_error)
                return BackendResult(success=False, error_msg=last_error)

            except OSError as exc:
                last_error = f"OS error running backend: {exc}"
                self._log.error(last_error)
                return BackendResult(success=False, error_msg=last_error)

            # Sleep before next retry (but not after the last attempt).
            if attempt <= self._retries and self._retry_delay > 0:
                time.sleep(self._retry_delay)

        # All retries exhausted.
        return BackendResult(success=False, error_msg=last_error)

    # ─────────────────────────────────────────────────────────────
    # JSON parsing
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_json(raw: str) -> Tuple[Optional[Any], Optional[str]]:
        """Parse *raw* as JSON.

        Returns:
            ``(parsed_data, None)`` on success, or
            ``(None, error_message)`` on failure.
        """
        if not raw or not raw.strip():
            return None, "Empty response from backend."
        try:
            data = json.loads(raw)
            return data, None
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON from backend: {exc}"

    # ─────────────────────────────────────────────────────────────
    # Cache helpers
    # ─────────────────────────────────────────────────────────────
    def _get_cached_list(self) -> Optional[List[Dict[str, Any]]]:
        """Return the cached process list if still valid, else ``None``."""
        if self._cache_ttl <= 0:
            return None
        with self._cache_lock:
            if self._cache is None:
                return None
            age = time.monotonic() - self._cache.timestamp
            if age < self._cache_ttl:
                self._log.debug("Cache hit (age=%.3fs).", age)
                return self._cache.data
            self._log.debug("Cache expired (age=%.3fs).", age)
            return None

    def _set_cached_list(self, data: List[Dict[str, Any]]) -> None:
        """Store *data* in the list cache."""
        if self._cache_ttl <= 0:
            return
        with self._cache_lock:
            self._cache = _CacheEntry(
                timestamp=time.monotonic(),
                data=data,
            )

    def invalidate_cache(self) -> None:
        """Explicitly clear the process-list cache.

        Call this after performing a mutating action (kill, pause, …)
        so the next ``list_processes`` call fetches fresh data.
        """
        with self._cache_lock:
            self._cache = None
        self._log.debug("Cache invalidated.")

    # ─────────────────────────────────────────────────────────────
    # Public API — synchronous
    # ─────────────────────────────────────────────────────────────
    def list_processes(self) -> List[Dict[str, Any]]:
        """Fetch and return the list of running processes.

        Returns:
            A list of dictionaries, each containing:

            .. code-block:: python

                {
                    "pid":    int,    # Process ID
                    "name":   str,    # Executable name
                    "state":  str,    # e.g. "S" (sleeping), "R" (running)
                    "cpu":    float,  # CPU usage percentage
                    "memory": float,  # Memory usage percentage
                }

            Returns an **empty list** on any error (never raises).
        """
        # Try cache first.
        cached = self._get_cached_list()
        if cached is not None:
            return cached

        result = self._execute("list")
        if not result.success:
            self._log.error(
                "list_processes failed: %s", result.error_msg
            )
            return []

        data, parse_err = self._parse_json(result.raw)
        if parse_err is not None:
            self._log.error("list_processes parse error: %s", parse_err)
            return []

        if not isinstance(data, list):
            self._log.error(
                "list_processes expected a JSON array, got %s.",
                type(data).__name__,
            )
            return []

        # Normalise each entry into a well-typed dict.
        processes: List[Dict[str, Any]] = []
        for entry in data:
            if not isinstance(entry, dict):
                self._log.warning("Skipping non-dict entry: %r", entry)
                continue
            processes.append(
                {
                    "pid": int(entry.get("pid", 0)),
                    "name": str(entry.get("name", "")),
                    "state": str(entry.get("state", "")),
                    "cpu": float(entry.get("cpu", 0.0)),
                    "memory": float(entry.get("memory", 0.0)),
                }
            )

        self._set_cached_list(processes)
        self._log.debug("Fetched %d processes.", len(processes))
        return processes

    def kill_process(self, pid: int) -> bool:
        """Send SIGKILL to process *pid*.

        Args:
            pid: Target process ID.

        Returns:
            ``True`` on success, ``False`` on failure (logged).
        """
        return self._action("kill", pid)

    def pause_process(self, pid: int) -> bool:
        """Send SIGSTOP to process *pid*.

        Args:
            pid: Target process ID.

        Returns:
            ``True`` on success, ``False`` on failure (logged).
        """
        return self._action("pause", pid)

    def resume_process(self, pid: int) -> bool:
        """Send SIGCONT to process *pid*.

        Args:
            pid: Target process ID.

        Returns:
            ``True`` on success, ``False`` on failure (logged).
        """
        return self._action("resume", pid)

    def change_priority(self, pid: int, value: int) -> bool:
        """Change the scheduling priority of process *pid*.

        Args:
            pid:   Target process ID.
            value: Nice value (typically −20 to 19).

        Returns:
            ``True`` on success, ``False`` on failure (logged).
        """
        try:
            pid_str = _validate_int_arg(pid, "PID")
            val_str = _validate_int_arg(value, "priority value")
        except ValueError as exc:
            self._log.error("change_priority validation: %s", exc)
            return False

        result = self._execute("priority", args=(pid_str, val_str))
        if not result.success:
            self._log.error(
                "change_priority(%d, %d) failed: %s",
                pid,
                value,
                result.error_msg,
            )
            return False

        self.invalidate_cache()
        self._log.info(
            "Priority of PID %d changed to %d.", pid, value
        )
        return True

    def run_command(
        self, command: str, args: Sequence[str] = ()
    ) -> BackendResult:
        """Execute an arbitrary backend command.

        This is the escape-hatch for commands that don't have a
        dedicated wrapper method.  The caller is responsible for
        interpreting the result.

        Args:
            command: Backend command name.
            args:    Additional arguments to pass after the command.

        Returns:
            A :class:`BackendResult`.
        """
        # Validate each arg is a safe integer string.
        sanitised_args: List[str] = []
        for arg in args:
            try:
                sanitised_args.append(_validate_int_arg(arg, "argument"))
            except ValueError as exc:
                self._log.error("run_command arg validation: %s", exc)
                return BackendResult(success=False, error_msg=str(exc))

        return self._execute(command, args=tuple(sanitised_args))

    # ─────────────────────────────────────────────────────────────
    # Public API — asynchronous (for Tkinter integration)
    # ─────────────────────────────────────────────────────────────
    def list_processes_async(
        self,
        tk_root: Any,
        on_done: Callable[[List[Dict[str, Any]]], None],
    ) -> None:
        """Fetch the process list in a background thread and deliver
        the result on the Tkinter main-loop thread via ``after()``.

        This prevents the GUI from freezing during the subprocess call.

        Args:
            tk_root: The Tkinter root (or any widget); used to schedule
                     the callback via ``tk_root.after()``.
            on_done: Callback receiving the process list.  It is
                     **always** called on the main thread.

        Example::

            def refresh(processes: list[dict]) -> None:
                table.update(processes)

            bridge.list_processes_async(root, on_done=refresh)
        """

        def _worker() -> None:
            processes = self.list_processes()
            # Schedule callback on the main thread.
            tk_root.after(0, on_done, processes)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        self._log.debug("list_processes_async: spawned worker thread.")

    def action_async(
        self,
        tk_root: Any,
        action: str,
        pid: int,
        on_done: Optional[Callable[[bool], None]] = None,
        priority_value: Optional[int] = None,
    ) -> None:
        """Execute a mutating action (kill/pause/resume/priority) in a
        background thread and optionally report success/failure back to
        the Tkinter main thread.

        Args:
            tk_root:        Tkinter root/widget for ``after()`` callback.
            action:         One of ``"kill"``, ``"pause"``, ``"resume"``,
                            ``"priority"``.
            pid:            Target process ID.
            on_done:        Optional callback ``(success: bool) -> None``
                            invoked on the main thread.
            priority_value: Required when *action* is ``"priority"``.
        """

        def _worker() -> None:
            if action == "priority":
                if priority_value is None:
                    self._log.error(
                        "action_async: 'priority' requires priority_value."
                    )
                    success = False
                else:
                    success = self.change_priority(pid, priority_value)
            elif action in ("kill", "pause", "resume"):
                success = self._action(action, pid)
            else:
                self._log.error("action_async: unknown action '%s'.", action)
                success = False

            if on_done is not None:
                tk_root.after(0, on_done, success)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        self._log.debug(
            "action_async: spawned worker thread for %s(%d).", action, pid
        )

    # ─────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────
    def _action(self, command: str, pid: int) -> bool:
        """Shared implementation for kill / pause / resume.

        Validates *pid*, executes the command, invalidates cache on
        success, and returns a boolean.
        """
        try:
            pid_str = _validate_int_arg(pid, "PID")
        except ValueError as exc:
            self._log.error("%s validation: %s", command, exc)
            return False

        result = self._execute(command, args=(pid_str,))
        if not result.success:
            self._log.error(
                "%s(%d) failed: %s", command, pid, result.error_msg
            )
            return False

        self.invalidate_cache()
        self._log.info("%s(%d) succeeded.", command, pid)
        return True

    # ─────────────────────────────────────────────────────────────
    # Repr
    # ─────────────────────────────────────────────────────────────
    def __repr__(self) -> str:
        return (
            f"<BackendBridge "
            f"path={self._backend_path!r} "
            f"timeout={self._timeout}s "
            f"retries={self._retries} "
            f"cache_ttl={self._cache_ttl}s>"
        )


# ──────────────────────────────────────────────────────────────────────
# Module-level convenience functions (thin wrappers around a default
# BackendBridge instance).  These allow simple usage without requiring
# callers to instantiate the class themselves:
#
#     from backend_bridge import list_processes, kill_process
#     procs = list_processes()
# ──────────────────────────────────────────────────────────────────────
_default_bridge: Optional[BackendBridge] = None
_default_lock: threading.Lock = threading.Lock()


def _get_default_bridge() -> BackendBridge:
    """Lazily create and return a module-level default bridge."""
    global _default_bridge
    with _default_lock:
        if _default_bridge is None:
            _default_bridge = BackendBridge()
        return _default_bridge


def list_processes() -> List[Dict[str, Any]]:
    """Convenience wrapper — fetch process list using the default bridge.

    Returns:
        List of process dictionaries (empty list on error).
    """
    return _get_default_bridge().list_processes()


def kill_process(pid: int) -> bool:
    """Convenience wrapper — kill a process using the default bridge."""
    return _get_default_bridge().kill_process(pid)


def pause_process(pid: int) -> bool:
    """Convenience wrapper — pause a process using the default bridge."""
    return _get_default_bridge().pause_process(pid)


def resume_process(pid: int) -> bool:
    """Convenience wrapper — resume a process using the default bridge."""
    return _get_default_bridge().resume_process(pid)


def change_priority(pid: int, value: int) -> bool:
    """Convenience wrapper — change priority using the default bridge."""
    return _get_default_bridge().change_priority(pid, value)


# Backward-compatible aliases used by table.py, actions.py and other existing modules.
get_processes = list_processes
boost_priority = change_priority


# ──────────────────────────────────────────────────────────────────────
# Self-test / demo
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    bridge = BackendBridge(log_level=logging.DEBUG)
    print(bridge)
    print(f"Available: {bridge.is_available}")

    if bridge.is_available:
        procs = bridge.list_processes()
        print(f"Found {len(procs)} processes.")
        for p in procs[:5]:
            print(f"  PID {p['pid']:>6}  {p['name']:<25}  "
                  f"CPU {p['cpu']:5.1f}%  MEM {p['memory']:5.1f}%")
    else:
        print("Backend binary not found -- skipping live test.")
