"""Smoke tests for FinSight runtime components."""
from __future__ import annotations

from Finsight.runtime.variable_space import Variable, VariableMetadata, VariableSpace
from Finsight.runtime.orchestrator import Orchestrator


def test_variable_space_register_and_retrieve() -> None:
    space = VariableSpace()
    metadata = VariableMetadata(name="sample", type="data", description="demo")
    variable = Variable(metadata=metadata, value={"hello": "world"})
    uid = space.register(variable)

    retrieved = space.get(uid)
    assert retrieved.metadata.name == "sample"
    assert retrieved.value["hello"] == "world"


def test_orchestrator_tool_execution() -> None:
    orchestrator = Orchestrator()

    def tool_echo(message: str) -> str:
        return message.upper()

    uid = orchestrator.register_tool("echo", tool_echo, description="Uppercases text")
    assert uid in orchestrator.variable_space.snapshot()

    result = orchestrator.tools["echo"]("finsight")
    assert result == "FINSIGHT"
