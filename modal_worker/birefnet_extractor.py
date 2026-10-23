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

    def _preprocess(self, image: Image.Image):
        """Apply BiRefNet's documented ImageNet normalization at policy resolution."""
        torch = self._torch
        if torch is None:
            raise ExtractionError("BiRefNet backend is not initialized")
        size = int(self.policy.inference_size)
        resized = image.resize((size, size), Image.Resampling.LANCZOS)
        # Avoid a torchvision runtime dependency: PIL bytes -> CHW float tensor.
        channels = len(resized.getbands())
        raw = torch.tensor(bytearray(resized.tobytes()), dtype=torch.uint8)
        tensor = raw.reshape(size, size, channels).permute(2, 0, 1).float().div(255.0)
        mean = torch.tensor([0.485, 0.456, 0.406], dtype=tensor.dtype).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225], dtype=tensor.dtype).view(3, 1, 1)
        return tensor.sub(mean).div(std).unsqueeze(0)

    def _predict_mask(self, image: Image.Image) -> Image.Image:
        torch = self._torch
        if torch is None or self._model is None:
            raise ExtractionError("BiRefNet backend is not initialized")

        try:
            inputs = self._preprocess(image)
            device = next(self._model.parameters()).device
            dtype = next(self._model.parameters()).dtype
            inputs = inputs.to(device=device, dtype=dtype)
            with torch.inference_mode():
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
