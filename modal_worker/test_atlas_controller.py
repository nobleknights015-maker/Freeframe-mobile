import unittest
from atlas_controller import ATLAS_VERSION, plan_asset


class AtlasControllerTests(unittest.TestCase):
    def test_friendly_guardian_plan_uses_shared_contract(self):
        plan = plan_asset(
            {
                "family": "guardian_friendly",
                "description": "small meadow guardian with leaflike ears",
                "context": {"region": "Elyndor"},
            }
        )
        request = plan["generation_request"]
        self.assertEqual(plan["assistant_name"], "Atlas")
        self.assertEqual(plan["controller_version"], ATLAS_VERSION)
        self.assertTrue(plan["generation_supported"])
        self.assertEqual(request["creature_family"], "guardian_friendly")
        self.assertEqual(request["guardian_composition_family"], "guardian_friendly")
        self.assertIn("creature first and textile biology second", request["prompt"])
        self.assertIn("intact continuous textile integument", request["prompt"])
        self.assertIn("functional paws feet wings or other locomotor anatomy", request["prompt"])
        self.assertIn("retail plush toy", request["negative_prompt"])
        self.assertIn("random patches", request["negative_prompt"])
        self.assertEqual(len(plan["atlas_job_id"]), 24)
        self.assertEqual(len(plan["plan_digest"]), 64)
        self.assertEqual(plan["ledger_record"]["atlas_job_id"], plan["atlas_job_id"])
        self.assertEqual(plan["ledger_record"]["plan_digest"], plan["plan_digest"])
        self.assertEqual(plan["ledger_record"]["state"], "planned")
        self.assertFalse(plan["automatic_full_production_authorized"])
        self.assertFalse(plan["chat_model_attached"])

    def test_corrupt_guardian_and_enemy_do_not_share_wrong_family(self):
        corrupt_plan = plan_asset(
            {
                "family": "guardian_corrupt",
                "description": "old woodland guardian overtaken by roots",
                "context": {"region": "Elyndor"},
                "seed": 44,
            }
        )
        enemy_plan = plan_asset(
            {
                "family": "enemy_creature",
                "description": "feral woodland prowler",
                "context": {"region": "Elyndor"},
                "seed": 45,
            }
        )
        corrupt = corrupt_plan["generation_request"]
        enemy = enemy_plan["generation_request"]
        self.assertEqual(corrupt["creature_family"], "guardian_corrupt")
        self.assertEqual(corrupt["guardian_composition_family"], "guardian_corrupt")
        self.assertEqual(enemy["creature_family"], "enemy_creature")
        self.assertIn("torn anatomical seam wounds", corrupt["prompt"])
        self.assertIn("cotton-like inner fiber", corrupt["prompt"])
        self.assertIn("wild hostile Plushtopia species", enemy["prompt"])
        self.assertIn("no decorative patchwork repairs or exposed filling", enemy["prompt"])
        self.assertIn("smiling mascot face", enemy["negative_prompt"])

    def test_boss_plan_gets_boss_specific_nonhumanoid_guard(self):
        plan = plan_asset(
            {
                "family": "guardian_boss",
                "description": "ancient grove warden",
                "context": {"region": "Elyndor"},
                "seed": 46,
            }
        )
        request = plan["generation_request"]
        self.assertEqual(request["guardian_composition_family"], "guardian_boss")
        self.assertIn("large imposing nonhuman Guardian boss", request["prompt"])
        self.assertIn("massive but anatomically functional nonhuman body", request["prompt"])
        self.assertIn("clearly separated locomotor limbs", request["prompt"])
        self.assertIn("gorilla", request["negative_prompt"])
        self.assertIn("bodybuilder", request["negative_prompt"])

    def test_missing_required_context_fails_before_generation(self):
        with self.assertRaisesRegex(ValueError, "region"):
            plan_asset(
                {
                    "family": "guardian_friendly",
                    "description": "meadow guardian",
                    "context": {},
                }
            )

    def test_human_enemy_is_planned_but_not_forced_through_creature_renderer(self):
        plan = plan_asset(
            {
                "family": "enemy_human",
                "description": "hostile relic hunter",
                "context": {
                    "region": "Elyndor",
                    "faction": "Ash Thread",
                    "role": "relic hunter",
                    "guardian_relationship": "captures Guardians",
                },
            }
        )
        self.assertFalse(plan["generation_supported"])
        self.assertIsNone(plan["generation_request"])
        self.assertEqual(plan["production_state"], "planned")

    def test_plan_identity_is_deterministic_and_changes_with_seed(self):
        intent = {
            "family": "guardian_boss",
            "description": "ancient woodland warden",
            "context": {"region": "Elyndor"},
        }
        first = plan_asset(intent)
        second = plan_asset(intent)
        self.assertEqual(first["seed"], second["seed"])
        self.assertEqual(first["atlas_job_id"], second["atlas_job_id"])
        self.assertEqual(first["plan_digest"], second["plan_digest"])
        altered = plan_asset({**intent, "seed": first["seed"] + 1})
        self.assertNotEqual(first["atlas_job_id"], altered["atlas_job_id"])
        self.assertNotEqual(first["plan_digest"], altered["plan_digest"])


if __name__ == "__main__":
    unittest.main()
