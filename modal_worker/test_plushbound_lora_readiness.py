import unittest

from plushbound_lora_readiness import (
    INFERENCE_TARGET,
    LORA_READINESS_VERSION,
    MIN_LONG_EDGE,
    REQUIRED_TRIGGER,
    TRAINING_TARGET,
    TrainingImage,
    evaluate_training_manifest,
)


def sample(
    index: int,
    category: str = "character",
    rights: str = "project_owned",
    *,
    width: int = 1024,
    height: int = 1024,
    caption: str | None = None,
) -> TrainingImage:
    return TrainingImage(
        asset_id=f"asset-{index:02d}",
        category=category,
        caption=caption or f"{REQUIRED_TRIGGER}, original Plushbound subject {index}",
        rights=rights,
        sha256=f"{index + 1:064x}",
        width=width,
        height=height,
    )


class PlushboundLoRAReadinessTests(unittest.TestCase):
    def test_balanced_owned_dataset_is_ready_but_never_auto_authorized(self):
        items = []
        for i in range(5):
            items.append(sample(i, "character"))
            items.append(sample(i + 5, "guardian"))
            items.append(sample(i + 10, "environment", "user_owned"))
        result = evaluate_training_manifest(items)
        self.assertTrue(result["ready"])
        self.assertFalse(result["training_authorized"])
        self.assertEqual(result["version"], LORA_READINESS_VERSION)
        self.assertEqual(LORA_READINESS_VERSION, "plushbound-lora-readiness-v2")
        self.assertEqual(result["training_target"], TRAINING_TARGET)
        self.assertEqual(result["inference_target"], INFERENCE_TARGET)
        self.assertEqual(result["minimum_long_edge"], MIN_LONG_EDGE)

    def test_third_party_rights_fail_closed(self):
        items = [sample(i, ("character", "guardian", "environment")[i % 3]) for i in range(15)]
        items[0] = sample(0, "character", "third_party")
        result = evaluate_training_manifest(items)
        self.assertFalse(result["ready"])
        self.assertTrue(any("user-owned or project-owned" in reason for reason in result["reasons"]))

    def test_too_small_dataset_fails(self):
        result = evaluate_training_manifest([sample(i, ("character", "guardian", "environment")[i % 3]) for i in range(6)])
        self.assertFalse(result["ready"])
        self.assertTrue(any("15-40" in reason for reason in result["reasons"]))

    def test_duplicate_hash_and_missing_trigger_fail(self):
        items = [sample(i, ("character", "guardian", "environment")[i % 3]) for i in range(15)]
        items[1] = TrainingImage(
            asset_id=items[1].asset_id,
            category=items[1].category,
            caption="original subject without trigger",
            rights=items[1].rights,
            sha256=items[0].sha256,
            width=1024,
            height=1024,
        )
        result = evaluate_training_manifest(items)
        self.assertFalse(result["ready"])
        self.assertTrue(any("duplicate image hashes" in reason for reason in result["reasons"]))
        self.assertTrue(any("trigger" in reason for reason in result["reasons"]))

    def test_low_resolution_image_fails_closed(self):
        items = [sample(i, ("character", "guardian", "environment")[i % 3]) for i in range(15)]
        items[4] = sample(4, "guardian", width=768, height=768)
        result = evaluate_training_manifest(items)
        self.assertFalse(result["ready"])
        self.assertTrue(any("1024px" in reason for reason in result["reasons"]))

    def test_style_words_in_caption_fail_closed(self):
        items = [sample(i, ("character", "guardian", "environment")[i % 3]) for i in range(15)]
        items[7] = sample(
            7,
            "guardian",
            caption=f"{REQUIRED_TRIGGER}, fox companion in JRPG style on a forest path",
        )
        result = evaluate_training_manifest(items)
        self.assertFalse(result["ready"])
        self.assertTrue(any("describe content rather than naming the visual style" in reason for reason in result["reasons"]))

    def test_portrait_or_landscape_can_pass_if_long_edge_is_large_enough(self):
        items = [sample(i, ("character", "guardian", "environment")[i % 3]) for i in range(15)]
        items[0] = sample(0, "character", width=768, height=1024)
        items[1] = sample(1, "guardian", width=1280, height=720)
        result = evaluate_training_manifest(items)
        self.assertTrue(result["ready"])


if __name__ == "__main__":
    unittest.main()
