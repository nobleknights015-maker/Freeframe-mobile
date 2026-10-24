"""Atlas conditioning policy derived from bounded creature visual evidence.

This module separates body-plan conditioning from art-style conditioning. The current
project-owned creature crops remain valuable visual-bible evidence, but bounded A/B
runs showed that healthy/boss/enemy crops can leak toy anatomy, ordinary-animal
features, accessories, or limb-count errors into new species. They are therefore not
approved as body-construction references for healthy creature masters.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

CONDITIONING_POLICY_VERSION = "atlas-creature-conditioning-v1"
EVIDENCE_RUN = 40050547258
EVIDENCE_ARTIFACT_DIGEST = "sha256:ea9ae4894359a2dcff49a8a302f7c88eea8bbaca7401c170d6ad4727e7db814b"


@dataclass(frozen=True)
class CreatureConditioningContract:
    family: str
    pose_guide: str
    project_creature_reference: str
    style_anchor: str
    production_state: str
    rationale: str

    def metadata(self) -> dict:
        return {**asdict(self), "policy_version": CONDITIONING_POLICY_VERSION}


CONTRACTS = {
    "guardian_friendly": CreatureConditioningContract(
        family="guardian_friendly",
        pose_guide="required",
        project_creature_reference="evidence_only_not_body_conditioning",
        style_anchor="clean_noncreature_plushbound_anchor_required",
        production_state="visual_gate_blocked",
        rationale="pose-only A/B improved structural obedience and removed creature-crop leakage, but lost Plushbound style identity",
    ),
    "guardian_corrupt": CreatureConditioningContract(
        family="guardian_corrupt",
        pose_guide="required",
        project_creature_reference="approved_bounded_lineage_style_candidate",
        style_anchor="project_corrupt_reference_current_candidate",
        production_state="bounded_candidate_only",
        rationale="corrupt Guardian was the only v3 style-conditioned case to pass visual review; approval remains bounded to this family",
    ),
    "guardian_boss": CreatureConditioningContract(
        family="guardian_boss",
        pose_guide="required",
        project_creature_reference="evidence_only_not_body_conditioning",
        style_anchor="clean_noncreature_plushbound_anchor_required",
        production_state="visual_gate_blocked",
        rationale="removing boss crop restored six-leg obedience, proving the crop competed with the exterior body-plan guide",
    ),
    "enemy_creature": CreatureConditioningContract(
        family="enemy_creature",
        pose_guide="required",
        project_creature_reference="evidence_only_not_body_conditioning",
        style_anchor="clean_noncreature_plushbound_anchor_required",
        production_state="visual_gate_blocked",
        rationale="removing enemy crop removed collar/patchwork-toy leakage and improved multi-leg structure, but pose-only output lacked Plushbound art identity",
    ),
}


def get_conditioning_contract(family: str) -> CreatureConditioningContract:
    try:
        return CONTRACTS[family]
    except KeyError as exc:
        raise ValueError(f"unknown creature conditioning family: {family}") from exc


def conditioning_snapshot() -> dict:
    return {
        "policy_version": CONDITIONING_POLICY_VERSION,
        "evidence_run": EVIDENCE_RUN,
        "evidence_artifact_digest": EVIDENCE_ARTIFACT_DIGEST,
        "contracts": {name: contract.metadata() for name, contract in CONTRACTS.items()},
        "automatic_full_production_authorized": False,
    }
