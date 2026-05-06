"""Protocols for the rebuild architecture."""

from __future__ import annotations

from typing import Protocol

from optagent.core.schema import ActionResult, Evidence, ExecutionPlan, Observation, Plan, StateNode


class SearchPolicy(Protocol):
    """Proposes one or more plans from a state."""

    def propose(self, state: StateNode) -> list[Plan]:
        ...


class Executor(Protocol):
    """Runs a grounded execution plan and returns raw execution results."""

    def execute(self, plan: ExecutionPlan) -> ActionResult:
        ...


class Evaluator(Protocol):
    """Converts observations into normalized evidence."""

    def evaluate(self, observation: Observation) -> Evidence:
        ...
