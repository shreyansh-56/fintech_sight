"""Enhanced Variable Space with Φ() function from FinSight paper."""
from __future__ import annotations

import json
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
    """
    Unified variable space V = V_data ∪ V_tool ∪ V_agent
    Shared across all agents in the FinSight pipeline.
    Supports checkpointing for resumable runs.
    
    Implements the Φ() function from paper eq (1):
    - At t=0 returns Info(V_0)
    - At t>0 returns Φ(V_{t-1}) ⊕ Info(V_t \ V_{t-1})
    """

    def __init__(self) -> None:
        self._variables: Dict[str, Variable] = {}
        self._previous_snapshot: Optional[Dict[str, Any]] = None
        self.interaction_history: list[dict] = field(default_factory=list)

    def register(self, variable: Variable) -> str:
        """Register a new variable in the space."""
        if variable.uid in self._variables:
            raise ValueError(f"Variable UID collision: {variable.uid}")
        self._variables[variable.uid] = variable
        return variable.uid

    def get(self, uid: str) -> Variable:
        """Get a variable by UID."""
        if uid not in self._variables:
            raise KeyError(f"Variable {uid} not found")
        return self._variables[uid]

    def update(self, uid: str, value: Any, source: Optional[str] = None) -> None:
        """Update a variable's value."""
        variable = self.get(uid)
        variable.update_value(value, source=source)

    def find_by_name(self, name: str) -> list[Variable]:
        """Find variables by name."""
        return [var for var in self._variables.values() if var.metadata.name == name]

    def info(self, step: int = 0) -> str:
        """
        Φ(V_t) function from paper eq (1):
        At t=0 returns Info(V_0), at t>0 returns Φ(V_{t-1}) ⊕ Info(V_t \ V_{t-1})
        Converts variable space to a readable prompt string for agents.
        """
        current_snapshot = self._get_variable_info_dict()
        
        if step == 0 or self._previous_snapshot is None:
            # Initial state: return full info
            self._previous_snapshot = current_snapshot
            return self._format_info(current_snapshot)
        else:
            # Subsequent state: return delta info
            delta = self._compute_delta(self._previous_snapshot, current_snapshot)
            self._previous_snapshot = current_snapshot
            return self._format_info(delta)

    def _get_variable_info_dict(self) -> Dict[str, Dict[str, Any]]:
        """Get a dictionary of variable info for comparison."""
        info_dict = {}
        for uid, variable in self._variables.items():
            info_dict[uid] = {
                "name": variable.metadata.name,
                "type": variable.metadata.type,
                "description": variable.metadata.description,
                "value_type": type(variable.value).__name__,
            }
            # Add shape info for DataFrames
            if hasattr(variable.value, 'shape'):
                info_dict[uid]["shape"] = variable.value.shape
            # Add length info for collections
            elif isinstance(variable.value, (dict, list)):
                info_dict[uid]["length"] = len(variable.value)
        return info_dict

    def _compute_delta(self, previous: Dict[str, Dict[str, Any]], current: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Compute the delta between two snapshots."""
        delta = {}
        
        # New variables
        for uid, info in current.items():
            if uid not in previous:
                delta[uid] = info
        
        # Updated variables (simplified check - in practice would track value changes)
        for uid, info in current.items():
            if uid in previous:
                prev_info = previous[uid]
                if info != prev_info:
                    delta[uid] = info
        
        return delta

    def _format_info(self, info_dict: Dict[str, Dict[str, Any]]) -> str:
        """Format variable info into a readable string."""
        lines = []
        
        # Group by type
        by_type: Dict[str, list] = {}
        for uid, info in info_dict.items():
            var_type = info.get("type", "unknown")
            if var_type not in by_type:
                by_type[var_type] = []
            by_type[var_type].append((uid, info))
        
        # Format data variables
        if "data" in by_type:
            lines.append("=== Available Data ===")
            for uid, info in by_type["data"]:
                dtype = info.get("value_type", "unknown")
                if "shape" in info:
                    lines.append(f"  [{info['name']}]: DataFrame shape={info['shape']}")
                elif "length" in info:
                    lines.append(f"  [{info['name']}]: {dtype} with {info['length']} entries")
                else:
                    lines.append(f"  [{info['name']}]: {dtype}")
        
        # Format tool variables
        if "tool" in by_type:
            lines.append("=== Available Tools ===")
            for uid, info in by_type["tool"]:
                lines.append(f"  [{info['name']}]: callable tool")
        
        # Format agent variables
        if "agent" in by_type:
            lines.append("=== Available Sub-Agents ===")
            for uid, info in by_type["agent"]:
                lines.append(f"  [{info['name']}]: agent")
        
        return "\n".join(lines) if lines else "Variable space is empty."

    def snapshot(self) -> Dict[str, Any]:
        """Return a serializable view of current variable space."""
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
        """List variables, optionally filtered by type."""
        if var_type is None:
            return list(self._variables.values())
        return [var for var in self._variables.values() if var.metadata.type == var_type]

    def save_checkpoint(self, path: str):
        """Serialize non-callable data to JSON for resumable runs."""
        checkpoint_data = {
            "variables": {},
            "interaction_history": self.interaction_history,
        }
        
        for uid, variable in self._variables.items():
            # Try to serialize the value
            try:
                value_repr = repr(variable.value) if not self._is_serializable(variable.value) else variable.value
            except:
                value_repr = f"<{type(variable.value).__name__} object (not serializable)>"
            
            checkpoint_data["variables"][uid] = {
                "metadata": {
                    "name": variable.metadata.name,
                    "type": variable.metadata.type,
                    "description": variable.metadata.description,
                    "source": variable.metadata.source,
                    "created_at": variable.metadata.created_at.isoformat(),
                    "updated_at": variable.metadata.updated_at.isoformat(),
                    "tags": list(variable.metadata.tags),
                },
                "value": value_repr,
            }
        
        with open(path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2, default=str)

    def load_checkpoint(self, path: str):
        """Load checkpoint from JSON."""
        with open(path, 'r') as f:
            checkpoint_data = json.load(f)
        
        self.interaction_history = checkpoint_data.get("interaction_history", [])
        
        # Note: We can't fully restore variables with non-serializable values
        # This is a simplified checkpoint for metadata recovery
        for uid, var_data in checkpoint_data.get("variables", {}).items():
            metadata_data = var_data["metadata"]
            metadata = VariableMetadata(
                name=metadata_data["name"],
                type=metadata_data["type"],
                description=metadata_data["description"],
                source=metadata_data["source"],
                tags=metadata_data["tags"],
            )
            # Parse timestamps
            if "created_at" in metadata_data:
                metadata.created_at = datetime.datetime.fromisoformat(metadata_data["created_at"])
            if "updated_at" in metadata_data:
                metadata.updated_at = datetime.datetime.fromisoformat(metadata_data["updated_at"])
            
            # Create variable with placeholder value
            variable = Variable(
                metadata=metadata,
                value=var_data["value"],
                uid=uid,
            )
            self._variables[uid] = variable

    def _is_serializable(self, obj: Any) -> bool:
        """Check if an object is JSON serializable."""
        try:
            json.dumps(obj)
            return True
        except (TypeError, ValueError):
            return False
