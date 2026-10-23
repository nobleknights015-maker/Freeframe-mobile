"""Provider-neutral subject extraction contract.

Production code can swap in a real segmentation/background-removal backend without
coupling the rest of the Plushbound factory to one model or service. The contract
also protects downstream MV packaging from silent resize/corruption by requiring
extraction to preserve the source canvas and recording deterministic hashes.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import Callable

from PIL import Image, UnidentifiedImageError

# Support both package imports in Modal (/root/modal_worker) and the historical
# direct-module import style used by the lightweight unit-test harness.
try:
    from .alpha_extraction_gate import inspect_extracted_png
except ImportError:  # pragma: no cover - direct-module compatibility for CI/tests
    from alpha_extraction_gate import inspect_extracted_png


@dataclass(frozen=True)
class ExtractionResult:
    png: bytes
    provider: str
    model: str


Extractor = Callable[[bytes], ExtractionResult]


class ExtractionError(RuntimeError):
    pass


def _png_dimensions(payload: bytes, *, label: str) -> tuple[int, int]:
    try:
        with Image.open(BytesIO(payload)) as image:
            if image.format != "PNG":
                raise ExtractionError(f"{label} must be PNG")
            return image.size
    except ExtractionError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ExtractionError(f"{label} is not a readable PNG: {exc}") from exc


def extract_and_validate(source_png: bytes, extractor: Extractor) -> tuple[bytes, dict]:
    if not source_png:
        raise ExtractionError("source PNG is empty")

    source_dimensions = _png_dimensions(source_png, label="source")
    try:
        result = extractor(source_png)
    except Exception as exc:
        raise ExtractionError(f"subject extraction failed: {exc}") from exc
    if not isinstance(result, ExtractionResult):
        raise ExtractionError("extractor returned invalid result type")
    if not result.png:
        raise ExtractionError("extractor returned empty PNG")
    if not result.provider.strip() or not result.model.strip():
        raise ExtractionError("extractor must identify provider and model")

    output_dimensions = _png_dimensions(result.png, label="extracted output")
    if output_dimensions != source_dimensions:
        raise ExtractionError(
            "extracted output dimensions changed: "
            f"source={source_dimensions[0]}x{source_dimensions[1]} "
            f"output={output_dimensions[0]}x{output_dimensions[1]}"
        )

    inspection = inspect_extracted_png(result.png)
    if not inspection["accepted"]:
        raise ExtractionError("extracted subject rejected: " + "; ".join(inspection["errors"]))
    metrics = {key: value for key, value in inspection.items() if key not in {"accepted", "errors"}}
    return result.png, {
        "extraction_provider": result.provider,
        "extraction_model": result.model,
        "source_sha256": sha256(source_png).hexdigest(),
        "output_sha256": sha256(result.png).hexdigest(),
        "source_width": source_dimensions[0],
        "source_height": source_dimensions[1],
        "output_width": output_dimensions[0],
        "output_height": output_dimensions[1],
        "extraction_metrics": metrics,
    }
