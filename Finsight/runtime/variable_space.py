"""Variable space implementation for the FinSight CAVM runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import datetime
import uuid


@dataclass
class VariableMetadata:
    """Metadata attached to every variable in the CAVM space."""

    name: str
    type: str  # e.g., "data", "tool", "agent"
    description: str = ""
    created_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    source: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = datetime.datetime.utcnow()


@dataclass
class Variable:
    """Represents a single entry in the variable space."""

    metadata: VariableMetadata
    value: Any
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))

    def update_value(self, new_value: Any, source: Optional[str] = None) -> None:
        self.value = new_value
        if source:
            self.metadata.source = source
        self.metadata.touch()


class VariableSpace:
    """Unified storage for data, tool, and agent variables."""

    def __init__(self) -> None:
        self._variables: Dict[str, Variable] = {}

    def register(self, variable: Variable) -> str:
        if variable.uid in self._variables:
            raise ValueError(f"Variable UID collision: {variable.uid}")
        self._variables[variable.uid] = variable
        return variable.uid

    def get(self, uid: str) -> Variable:
        if uid not in self._variables:
            raise KeyError(f"Variable {uid} not found")
        return self._variables[uid]

    def update(self, uid: str, value: Any, source: Optional[str] = None) -> None:
        variable = self.get(uid)
        variable.update_value(value, source=source)

    def find_by_name(self, name: str) -> list[Variable]:
        return [var for var in self._variables.values() if var.metadata.name == name]

    def snapshot(self) -> Dict[str, Any]:
        """Return a serialisable view of current variable space."""
        snapshot: Dict[str, Any] = {}
        for uid, variable in self._variables.items():
            snapshot[uid] = {
                "metadata": {
                    "name": variable.metadata.name,
                    "type": variable.metadata.type,
                    "description": variable.metadata.description,
                    "source": variable.metadata.source,
                    "created_at": variable.metadata.created_at.isoformat(),
                    "updated_at": variable.metadata.updated_at.isoformat(),
                    "tags": list(variable.metadata.tags),
                },
                "value": variable.value,
            }
        return snapshot

    def list_variables(self, var_type: Optional[str] = None) -> list[Variable]:
        if var_type is None:
            return list(self._variables.values())
        return [var for var in self._variables.values() if var.metadata.type == var_type]
