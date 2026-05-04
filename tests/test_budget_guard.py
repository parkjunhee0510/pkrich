from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from src.utils.budget_guard import BudgetGuardConfig, evaluate_budget_guard
from src.utils.model_config import load_budget_guard_config


class BudgetGuardTests(unittest.TestCase):
    def test_shadow_mode_records_would_block_but_allows(self) -> None:
        config = BudgetGuardConfig(
            mode="shadow",
            daily_cap_usd=0.25,
            monthly_cap_usd=5.0,
            on_exceed="log_only",
            guarded_profiles=("standard", "deep"),
            guarded_paths=("ensemble_deep",),
        )

        decision = evaluate_budget_guard(
            config=config,
            path="ensemble_deep",
            profile="deep",
            estimated_incremental_cost_usd=0.05,
            run_cost_so_far_usd=0.23,
        )

        self.assertEqual(decision.decision, "would_block")
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.would_block)

    def test_enforce_mode_blocks_guarded_profile_when_cap_exceeded(self) -> None:
        config = BudgetGuardConfig(
            mode="enforce",
            daily_cap_usd=0.25,
            monthly_cap_usd=5.0,
            on_exceed="skip_deep",
            guarded_profiles=("standard", "deep"),
            guarded_paths=("ensemble_deep",),
        )

        decision = evaluate_budget_guard(
            config=config,
            path="ensemble_deep",
            profile="deep",
            estimated_incremental_cost_usd=0.05,
            run_cost_so_far_usd=0.23,
        )

        self.assertEqual(decision.decision, "blocked")
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.would_block)

    def test_unguarded_path_is_allowed(self) -> None:
        config = BudgetGuardConfig(
            mode="enforce",
            daily_cap_usd=0.01,
            monthly_cap_usd=5.0,
            on_exceed="skip_deep",
            guarded_profiles=("deep",),
            guarded_paths=("ensemble_deep",),
        )

        decision = evaluate_budget_guard(
            config=config,
            path="macro_free_path",
            profile="deep",
            estimated_incremental_cost_usd=1.0,
            run_cost_so_far_usd=1.0,
        )

        self.assertEqual(decision.decision, "allow")
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.would_block)

    def test_load_budget_guard_config_reads_yaml_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "models.yaml"
            path.write_text(
                "\n".join(
                    [
                        "budget_guard:",
                        "  mode: enforce",
                        "  daily_cap_usd: 0.12",
                        "  monthly_cap_usd: 4.5",
                        "  on_exceed: skip_deep",
                        "  guarded_profiles: [deep]",
                        "  guarded_paths: [ensemble_deep]",
                        "profiles:",
                        "  economy:",
                        "    model: gpt-5.4-mini",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_budget_guard_config(str(path))

        self.assertEqual(config.mode, "enforce")
        self.assertEqual(config.daily_cap_usd, 0.12)
        self.assertEqual(config.monthly_cap_usd, 4.5)
        self.assertEqual(config.on_exceed, "skip_deep")
        self.assertEqual(config.guarded_profiles, ("deep",))
        self.assertEqual(config.guarded_paths, ("ensemble_deep",))


if __name__ == "__main__":
    unittest.main()
