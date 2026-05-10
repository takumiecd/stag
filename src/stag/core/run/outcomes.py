"""RunHandle.outcomes implementation."""

from __future__ import annotations


def outcomes_impl(self, input_transition_id: str) -> dict:
    """Return predictions / observations / active_observations / inactive_observations.

    Raises KeyError if the input_transition_id is unknown.
    """
    if input_transition_id not in self.run_graph.input_transitions:
        raise KeyError(f"unknown input_transition_id: {input_transition_id}")

    predictions = self.run_graph.output_ids_for_input(
        input_transition_id, kind="prediction", active_only=False
    )
    observations = self.run_graph.output_ids_for_input(
        input_transition_id, kind="result", active_only=False
    )
    active_observations = self.run_graph.output_ids_for_input(
        input_transition_id, kind="result", active_only=True
    )
    active_set = set(active_observations)
    inactive_observations = [ot_id for ot_id in observations if ot_id not in active_set]

    return {
        "input_transition_id": input_transition_id,
        "predictions": predictions,
        "observations": observations,
        "active_observations": active_observations,
        "inactive_observations": inactive_observations,
    }
