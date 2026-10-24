import unittest
from atlas_controller import ATLAS_VERSION, plan_asset


class AtlasControllerTests(unittest.TestCase):
    def test_friendly_guardian_plan_uses_shared_contract(self):
        plan = plan_asset({"family":"guardian_friendly","description":"small meadow guardian with leaflike ears","context":{"region":"Elyndor"}})
        request = plan["generation_request"]
        self.assertEqual(plan["assistant_name"], "Atlas")
        self.assertEqual(plan["controller_version"], ATLAS_VERSION)
        self.assertTrue(plan["generation_supported"])
        self.assertEqual(request["creature_family"], "guardian_friendly")
        self.assertEqual(request["guardian_composition_family"], "guardian_friendly")
        self.assertIn("creature first and textile biology second", request["prompt"])
        self.assertIn("fully enclosed exterior body", request["prompt"])
        self.assertIn("visible skeleton", request["negative_prompt"])
        self.assertEqual(plan["conditioning"]["pose_guide"], "required")
        self.assertEqual(plan["conditioning"]["project_creature_reference"], "evidence_only_not_body_conditioning")
        self.assertEqual(plan["conditioning"]["style_anchor"], "clean_noncreature_plushbound_anchor_required")
        self.assertTrue(plan["visual_gate_blocked"])
        self.assertEqual(len(plan["atlas_job_id"]), 24)
        self.assertEqual(len(plan["plan_digest"]), 64)
        self.assertEqual(plan["ledger_record"]["atlas_job_id"], plan["atlas_job_id"])
        self.assertEqual(plan["ledger_record"]["state"], "planned")
        self.assertFalse(plan["automatic_full_production_authorized"])

    def test_corrupt_guardian_is_bounded_conditioning_candidate(self):
        plan = plan_asset({"family":"guardian_corrupt","description":"old woodland guardian overtaken by roots","context":{"region":"Elyndor"},"seed":44})
        self.assertEqual(plan["conditioning"]["project_creature_reference"], "approved_bounded_lineage_style_candidate")
        self.assertEqual(plan["conditioning"]["production_state"], "bounded_candidate_only")
        self.assertFalse(plan["visual_gate_blocked"])
        self.assertIn("cotton-like inner fiber", plan["generation_request"]["prompt"])

    def test_enemy_and_boss_remain_visual_gate_blocked(self):
        enemy = plan_asset({"family":"enemy_creature","description":"feral woodland prowler","context":{"region":"Elyndor"},"seed":45})
        boss = plan_asset({"family":"guardian_boss","description":"ancient grove warden","context":{"region":"Elyndor"},"seed":46})
        self.assertTrue(enemy["visual_gate_blocked"])
        self.assertTrue(boss["visual_gate_blocked"])
        self.assertEqual(enemy["conditioning"]["project_creature_reference"], "evidence_only_not_body_conditioning")
        self.assertEqual(boss["conditioning"]["project_creature_reference"], "evidence_only_not_body_conditioning")
        self.assertIn("wild hostile Plushtopia species", enemy["generation_request"]["prompt"])
        self.assertIn("large imposing nonhuman Guardian boss", boss["generation_request"]["prompt"])

    def test_missing_required_context_fails_before_generation(self):
        with self.assertRaisesRegex(ValueError, "region"):
            plan_asset({"family":"guardian_friendly","description":"meadow guardian","context":{}})

    def test_human_enemy_is_planned_without_creature_conditioning(self):
        plan = plan_asset({"family":"enemy_human","description":"hostile relic hunter","context":{"region":"Elyndor","faction":"Ash Thread","role":"relic hunter","guardian_relationship":"captures Guardians"}})
        self.assertFalse(plan["generation_supported"])
        self.assertIsNone(plan["generation_request"])
        self.assertIsNone(plan["conditioning"])
        self.assertFalse(plan["visual_gate_blocked"])

    def test_plan_identity_is_deterministic_and_changes_with_seed(self):
        intent={"family":"guardian_boss","description":"ancient woodland warden","context":{"region":"Elyndor"}}
        first=plan_asset(intent); second=plan_asset(intent)
        self.assertEqual(first["atlas_job_id"], second["atlas_job_id"])
        self.assertEqual(first["plan_digest"], second["plan_digest"])
        altered=plan_asset({**intent,"seed":first["seed"]+1})
        self.assertNotEqual(first["atlas_job_id"], altered["atlas_job_id"])


if __name__ == "__main__": unittest.main()
