import unittest
from mini_jarvis_controller import MINI_JARVIS_VERSION,plan_asset
class MiniJarvisControllerTests(unittest.TestCase):
 def test_friendly_guardian_plan_uses_shared_contract(self):
  plan=plan_asset({"family":"guardian_friendly","description":"small meadow guardian with leaflike ears","context":{"region":"Elyndor"}}); self.assertEqual(plan["controller_version"],MINI_JARVIS_VERSION); self.assertTrue(plan["generation_supported"]); self.assertEqual(plan["generation_request"]["creature_family"],"guardian_friendly"); self.assertIn("creature first and textile second",plan["generation_request"]["prompt"]); self.assertFalse(plan["automatic_full_production_authorized"]); self.assertFalse(plan["chat_model_attached"])
 def test_corrupt_guardian_and_enemy_do_not_share_wrong_family(self):
  c=plan_asset({"family":"guardian_corrupt","description":"old woodland guardian overtaken by roots","context":{"region":"Elyndor"},"seed":44}); e=plan_asset({"family":"enemy_creature","description":"feral woodland prowler","context":{"region":"Elyndor"},"seed":45}); self.assertEqual(c["generation_request"]["creature_family"],"guardian_corrupt"); self.assertEqual(e["generation_request"]["creature_family"],"enemy_creature"); self.assertIn("torn seams",c["generation_request"]["prompt"]); self.assertIn("wild hostile Plushtopia creature",e["generation_request"]["prompt"])
 def test_missing_required_context_fails_before_generation(self):
  with self.assertRaisesRegex(ValueError,"region"): plan_asset({"family":"guardian_friendly","description":"meadow guardian","context":{}})
 def test_human_enemy_is_planned_but_not_forced_through_creature_renderer(self):
  plan=plan_asset({"family":"enemy_human","description":"hostile relic hunter","context":{"region":"Elyndor","faction":"Ash Thread","role":"relic hunter","guardian_relationship":"captures Guardians"}}); self.assertFalse(plan["generation_supported"]); self.assertIsNone(plan["generation_request"]); self.assertEqual(plan["production_state"],"planned")
 def test_seed_is_deterministic(self):
  intent={"family":"guardian_boss","description":"ancient woodland warden","context":{"region":"Elyndor"}}; self.assertEqual(plan_asset(intent)["seed"],plan_asset(intent)["seed"])
if __name__=="__main__": unittest.main()
