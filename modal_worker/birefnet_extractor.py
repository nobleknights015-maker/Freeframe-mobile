"""Lazy BiRefNet adapter for the provider-neutral extraction contract.

Heavy ML dependencies are imported only when the backend is instantiated, keeping
normal CI/unit tests lightweight. The returned RGBA PNG always preserves the
source canvas; `extract_and_validate` remains responsible for the production gate.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError

from extraction_backend_policy import production_extraction_backend
from extraction_provider import ExtractionError, ExtractionResult


class BiRefNetExtractor:
    def __init__(self, *, model: Any | None = None, torch_module: Any | None = None):
        policy = production_extraction_backend()
        self.policy = policy
        self._torch = torch_module
        self._model = model
        if self._model is None:
            self._load_model()

    def _load_model(self) -> None:
        try:
            import torch
            from transformers import AutoModelForImageSegmentation
        except ImportError as exc:
            raise ExtractionError(
                "BiRefNet backend requires torch and transformers in the runtime image"
            ) from exc

        self._torch = torch
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self._model = AutoModelForImageSegmentation.from_pretrained(
            self.policy.model,
            trust_remote_code=True,
            torch_dtype=dtype,
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = self._model.to(device)
        self._model.eval()

    def _source_image(self, source_png: bytes) -> Image.Image:
        try:
            with Image.open(BytesIO(source_png)) as image:
                if image.format != "PNG":
                    raise ExtractionError("BiRefNet source must be PNG")
                return image.convert("RGB")
        except ExtractionError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ExtractionError(f"BiRefNet source is not a readable PNG: {exc}") from exc

    def _predict_mask(self, image: Image.Image) -> Image.Image:
        """Return an L-mode mask at source size using the official model's preprocessing.

        The official Hugging Face model exposes `preprocess_image` and returns the
        segmentation logits as the last prediction tensor. Keeping this method
        isolated makes the adapter easy to smoke-test against future upstream API
        changes without touching routing or packaging code.
        """
        torch = self._torch
        if torch is None or self._model is None:
            raise ExtractionError("BiRefNet backend is not initialized")

        try:
            inputs = self._model.preprocess_image(image)
            if hasattr(inputs, "to"):
                device = next(self._model.parameters()).device
                inputs = inputs.to(device)
            with torch.no_grad():
                predictions = self._model(inputs)
            logits = predictions[-1] if isinstance(predictions, (list, tuple)) else predictions
            if isinstance(logits, (list, tuple)):
                logits = logits[-1]
            mask = torch.sigmoid(logits).squeeze().detach().float().cpu().numpy()
        except Exception as exc:
            raise ExtractionError(f"BiRefNet inference failed: {exc}") from exc

        if getattr(mask, "ndim", 0) != 2:
            raise ExtractionError(f"BiRefNet returned unexpected mask shape: {getattr(mask, 'shape', None)}")
        mask_image = Image.fromarray((mask.clip(0.0, 1.0) * 255).astype("uint8"), mode="L")
        return mask_image.resize(image.size, Image.Resampling.LANCZOS)

    def __call__(self, source_png: bytes) -> ExtractionResult:
        source = self._source_image(source_png)
        mask = self._predict_mask(source)
        rgba = source.convert("RGBA")
        rgba.putalpha(mask)
        out = BytesIO()
        rgba.save(out, format="PNG", optimize=False)
        return ExtractionResult(
            png=out.getvalue(),
            provider=self.policy.provider,
            model=self.policy.model,
        )
