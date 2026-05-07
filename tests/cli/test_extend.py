"""Tests for optagent CLI extend command."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from optagent.cli.commands.extend import run_extend_command
from optagent.cli.commands.init import run_init_command
from optagent.cli.main import parse_args, main
from optagent.storage.jsonl import JsonlRunStore


class TestCliExtendCommand:
    """``optagent extend`` creates PredictionPlans from predicted states."""

    def _create_run(self, store_dir: Path, run_id: str = "test_run") -> str:
        result = run_init_command(
            requirement_id="req_test",
            target_type="code",
            target_id="module_a",
            run_id=run_id,
            store_dir=str(store_dir),
        )
        return result["run_id"]

    def test_extend_creates_prediction_plan(self):
        """extend should create a PredictionPlan from a predicted state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_dir = Path(tmpdir) / "runs"
            run_id = self._create_run(store_dir)

            result = run_extend_command(
                run_id=run_id,
                state_id="s_pred_0000",
                planner="default",
                max_plans=1,
                store_dir=str(store_dir),
            )
            assert len(result["plans"]) == 1
            assert result["plans"][0]["plan_kind"] == "prediction"
            assert result["plans"][0]["from_predicted_state_id"] == "s_pred_0000"

    def test_extend_persists_plan(self):
        """extend should save the prediction plan to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_dir = Path(tmpdir) / "runs"
            run_id = self._create_run(store_dir)

            run_extend_command(
                run_id=run_id,
                state_id="s_pred_0000",
                planner="default",
                max_plans=1,
                store_dir=str(store_dir),
            )

            store = JsonlRunStore(store_dir)
            loaded = store.load_run(run_id)
            assert len(loaded.prediction_dag.plans) == 1

    def test_extend_rejects_observed_state(self):
        """extend should refuse an observed state_id (use 'plan' instead)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_dir = Path(tmpdir) / "runs"
            run_id = self._create_run(store_dir)

            with pytest.raises(KeyError, match="not a predicted state"):
                run_extend_command(
                    run_id=run_id,
                    state_id="s_obs_0000",
                    planner="default",
                    max_plans=1,
                    store_dir=str(store_dir),
                )

    def test_extend_unknown_run_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_dir = Path(tmpdir) / "runs"
            with pytest.raises(KeyError):
                run_extend_command(
                    run_id="nonexistent",
                    state_id="s_pred_0000",
                    planner="default",
                    max_plans=1,
                    store_dir=str(store_dir),
                )

    def test_cli_parse_args_extend(self):
        """argparse should require --state-id and accept --run."""
        args = parse_args([
            "extend",
            "--run", "my_run",
            "--state-id", "s_pred_0001",
        ])
        assert args.command == "extend"
        assert args.run == "my_run"
        assert args.state_id == "s_pred_0001"
        assert args.planner == "default"

    def test_cli_parse_args_extend_requires_state_id(self):
        """argparse should fail without --state-id."""
        with pytest.raises(SystemExit):
            parse_args(["extend", "--run", "my_run"])

    def test_main_extend_command(self, capsys):
        """main() should run extend end-to-end and print JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_dir = Path(tmpdir) / "runs"
            run_id = self._create_run(store_dir)

            exit_code = main([
                "extend",
                "--run", run_id,
                "--state-id", "s_pred_0000",
                "--store-dir", str(store_dir),
            ])
            assert exit_code == 0
            captured = capsys.readouterr()
            plans = json.loads(captured.out)
            assert len(plans) == 1
            assert plans[0]["plan_kind"] == "prediction"
