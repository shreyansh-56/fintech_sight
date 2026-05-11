"""Core orchestrator for FinSight CAVM runtime."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict

from .variable_space import Variable, VariableMetadata, VariableSpace
from .code_executor import CodeExecutor, ExecutionResult


class Orchestrator:
    """Manages variable space, registered tools, and agent code execution."""

    def __init__(self, log_path: Path | None = None) -> None:
        self.variable_space = VariableSpace()
        self.tools: Dict[str, Callable[..., Any]] = {}
        self.code_executor = CodeExecutor()
        self.log_path = log_path
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def register_tool(self, name: str, func: Callable[..., Any], description: str = "") -> str:
        metadata = VariableMetadata(name=name, type="tool", description=description)
        variable = Variable(metadata=metadata, value=func)
        uid = self.variable_space.register(variable)
        self.tools[name] = func
        self._log_event("register_tool", uid, metadata.__dict__)
        return uid

    def register_data(
        self,
        name: str,
        value: Any,
        description: str = "",
        source: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        metadata = VariableMetadata(
            name=name,
            type="data",
            description=description,
            source=source,
            tags=tags or [],
        )
        variable = Variable(metadata=metadata, value=value)
        uid = self.variable_space.register(variable)
        self._log_event(
            "register_data",
            uid,
            {
                "name": name,
                "description": description,
                "source": source,
                "tags": tags or [],
            },
        )
        return uid

    def register_agent(self, name: str, agent_obj: Any, description: str = "") -> str:
        metadata = VariableMetadata(name=name, type="agent", description=description)
        variable = Variable(metadata=metadata, value=agent_obj)
        uid = self.variable_space.register(variable)
        self._log_event("register_agent", uid, metadata.__dict__)
        return uid

    def execute_agent_code(self, code: str, context: Dict[str, Any] | None = None) -> ExecutionResult:
        initial_globals = {"variable_space": self.variable_space, "tools": self.tools}
        if context:
            initial_globals.update(context)
        result = self.code_executor.run(code, initial_globals=initial_globals)
        self._log_event(
            "execute_agent_code",
            payload={
                "code": code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.success,
            },
        )
        return result

    def _log_event(self, event: str, uid: str | None = None, payload: Dict[str, Any] | None = None) -> None:
        if not self.log_path:
            return
        entry = {
            "event": event,
            "uid": uid,
            "payload": payload or {},
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
