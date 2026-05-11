"""Abstract base classes for FinSight agents."""
from __future__ import annotations

import abc
from typing import Any, Dict


class Agent(abc.ABC):
    """Base FinSight agent operating over the CAVM runtime."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description

    @abc.abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Execute the agent and return a structured result."""


class ToolCallable(abc.ABC):
    """Interface for tool callables registered inside the variable space."""

    @abc.abstractmethod
    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - interface
        raise NotImplementedError
