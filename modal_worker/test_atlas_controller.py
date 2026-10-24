import unittest
from atlas_controller import ATLAS_VERSION, RESPONSIBILITY_BOUNDARY, plan_asset


class AtlasControllerTests(unittest.TestCase):
    def test_friendly_guardian_plan_uses_shared_contract_without_visual_conditioning(self):
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
        self.assertIsNone(plan["atlas_visual_conditioning"])
        self.assertEqual(plan["visual_generation_owned_by"], "Vera")
        self.assertEqual(plan["deterministic_compilation_owned_by"], "Atlas")
        self.assertEqual(len(plan["atlas_job_id"]), 24)
        self.assertEqual(len(plan["plan_digest"]), 64)
        self.assertEqual(plan["ledger_record"]["atlas_job_id"], plan["atlas_job_id"])
        self.assertEqual(plan["ledger_record"]["state"], "planned")
        self.assertFalse(plan["automatic_full_production_authorized"])

    def test_hard_responsibility_boundary_cannot_hand_visual_control_to_atlas(self):
        self.assertTrue(RESPONSIBILITY_BOUNDARY["vera_owns_visual_creation"])
        self.assertTrue(RESPONSIBILITY_BOUNDARY["vera_owns_art_direction"])
        self.assertTrue(RESPONSIBILITY_BOUNDARY["atlas_owns_final_pixel_placement"])
        self.assertTrue(RESPONSIBILITY_BOUNDARY["atlas_owns_slot_coordinates"])
        self.assertTrue(RESPONSIBILITY_BOUNDARY["atlas_owns_canvas_geometry"])
        self.assertTrue(RESPONSIBILITY_BOUNDARY["atlas_owns_manifest_mapping"])
        self.assertTrue(RESPONSIBILITY_BOUNDARY["atlas_owns_version_validation"])
        self.assertTrue(RESPONSIBILITY_BOUNDARY["atlas_owns_qa_acceptance_state"])
        self.assertFalse(RESPONSIBILITY_BOUNDARY["atlas_may_direct_visual_generation"])
        self.assertFalse(RESPONSIBILITY_BOUNDARY["atlas_may_condition_visual_generation"])
        self.assertFalse(RESPONSIBILITY_BOUNDARY["atlas_may_override_vera_art_direction"])
        self.assertFalse(RESPONSIBILITY_BOUNDARY["vera_may_override_atlas_geometry_or_manifest"])

    def test_creature_families_keep_art_requirements_but_not_atlas_conditioning(self):
        corrupt = plan_asset({"family":"guardian_corrupt","description":"old woodland guardian overtaken by roots","context":{"region":"Elyndor"},"seed":44})
        enemy = plan_asset({"family":"enemy_creature","description":"feral woodland prowler","context":{"region":"Elyndor"},"seed":45})
        boss = plan_asset({"family":"guardian_boss","description":"ancient grove warden","context":{"region":"Elyndor"},"seed":46})
        for plan in (corrupt, enemy, boss):
            self.assertIsNone(plan["atlas_visual_conditioning"])
            self.assertEqual(plan["visual_generation_owned_by"], "Vera")
        self.assertIn("cotton-like inner fiber", corrupt["generation_request"]["prompt"])
        self.assertIn("wild hostile Plushtopia species", enemy["generation_request"]["prompt"])
        self.assertIn("large imposing nonhuman Guardian boss", boss["generation_request"]["prompt"])

    def test_missing_required_context_fails_before_generation(self):
        with self.assertRaisesRegex(ValueError, "region"):
            plan_asset({"family":"guardian_friendly","description":"meadow guardian","context":{}})

    def test_human_enemy_is_planned_without_visual_generator_control(self):
        plan = plan_asset({"family":"enemy_human","description":"hostile relic hunter","context":{"region":"Elyndor","faction":"Ash Thread","role":"relic hunter","guardian_relationship":"captures Guardians"}})
        self.assertFalse(plan["generation_supported"])
        self.assertIsNone(plan["generation_request"])
        self.assertIsNone(plan["atlas_visual_conditioning"])
        self.assertEqual(plan["visual_generation_owned_by"], "Vera")

    def test_plan_identity_is_deterministic_and_changes_with_seed(self):
        intent={"family":"guardian_boss","description":"ancient woodland warden","context":{"region":"Elyndor"}}
        first=plan_asset(intent); second=plan_asset(intent)
        self.assertEqual(first["atlas_job_id"], second["atlas_job_id"])
        self.assertEqual(first["plan_digest"], second["plan_digest"])
        altered=plan_asset({**intent,"seed":first["seed"]+1})
        self.assertNotEqual(first["atlas_job_id"], altered["atlas_job_id"])


if __name__ == "__main__": unittest.main()
