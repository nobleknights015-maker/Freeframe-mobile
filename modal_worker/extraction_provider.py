"""Provider-neutral subject extraction contract.

Production code can swap in a real segmentation/background-removal backend without
coupling the rest of the Plushbound factory to one model or service.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from alpha_extraction_gate import validate_extracted_subject


@dataclass(frozen=True)
class ExtractionResult:
    png: bytes
    provider: str
    model: str


Extractor = Callable[[bytes], ExtractionResult]


class ExtractionError(RuntimeError):
    pass


def extract_and_validate(source_png: bytes, extractor: Extractor) -> tuple[bytes, dict]:
    if not source_png:
        raise ExtractionError("source PNG is empty")
    try:
        result = extractor(source_png)
    except Exception as exc:
        raise ExtractionError(f"subject extraction failed: {exc}") from exc
    if not isinstance(result, ExtractionResult):
        raise ExtractionError("extractor returned invalid result type")
    if not result.provider.strip() or not result.model.strip():
        raise ExtractionError("extractor must identify provider and model")
    inspection = validate_extracted_subject(result.png)
    if not inspection.accepted:
        raise ExtractionError("extracted subject rejected: " + "; ".join(inspection.reasons))
    return result.png, {
        "extraction_provider": result.provider,
        "extraction_model": result.model,
        "extraction_metrics": inspection.metrics,
    }
