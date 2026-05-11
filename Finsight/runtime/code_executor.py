"""Code execution harness for CAVM agents."""
from __future__ import annotations

import contextlib
import io
from typing import Any, Dict


class ExecutionResult:
    """Represents the outcome of a code execution step."""

    def __init__(self, globals_state: Dict[str, Any], stdout: str, stderr: str, error: Exception | None) -> None:
        self.globals_state = globals_state
        self.stdout = stdout
        self.stderr = stderr
        self.error = error

    @property
    def success(self) -> bool:
        return self.error is None


class CodeExecutor:
    """Simple sandbox for executing agent-generated Python code."""

    def __init__(self, allowed_builtins: Dict[str, Any] | None = None) -> None:
        self.allowed_builtins = allowed_builtins or {}

    def run(self, code: str, initial_globals: Dict[str, Any] | None = None) -> ExecutionResult:
        globals_dict = {"__builtins__": self.allowed_builtins}
        if initial_globals:
            globals_dict.update(initial_globals)

        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        error: Exception | None = None

        try:
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                exec(code, globals_dict)
        except Exception as exc:  # pylint: disable=broad-except
            error = exc

        stdout = stdout_buffer.getvalue()
        stderr = stderr_buffer.getvalue()

        return ExecutionResult(globals_state=globals_dict, stdout=stdout, stderr=stderr, error=error)
