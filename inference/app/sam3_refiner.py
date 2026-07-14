from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from PIL import Image

from .mask import NailRegion


@dataclass(frozen=True)
class Sam3Refinement:
    regions: list[NailRegion]
    candidate_count: int
    refined_count: int


@lru_cache(maxsize=1)
def _load_sam3_processor(checkpoint_path: str, device: str):
    from sam3.model.sam3_image_processor import Sam3Processor  # type: ignore
    from sam3.model_builder import build_sam3_image_model  # type: ignore

    model = build_sam3_image_model(
        checkpoint_path=checkpoint_path,
        load_from_HF=False,
        device=device,
        eval_mode=True,
    )
    return Sam3Processor(model)


class Sam3NailRefiner:
    """Segment visible nail plates from a style image using a text prompt."""

    def __init__(
        self,
        *,
        checkpoint_path: str,
        device: str,
        prompt: str,
        min_score: float,
    ) -> None:
        self.checkpoint_path = checkpoint_path
        self.device = device
        self.prompt = prompt
        self.min_score = min_score

    def segment(self, image: Image.Image) -> Sam3Refinement:
        import torch

        processor = _load_sam3_processor(self.checkpoint_path, self.device)
        autocast_device = "cuda" if self.device.startswith("cuda") else "cpu"
        autocast_enabled = autocast_device == "cuda"
        with torch.inference_mode(), torch.autocast(
            autocast_device,
            dtype=torch.bfloat16,
            enabled=autocast_enabled,
        ):
            state = processor.set_image(image.convert("RGB"))
            result = processor.set_text_prompt(prompt=self.prompt, state=state)

        sam_regions = self._candidate_regions(result, image.size)
        refined = _deduplicate_regions(sam_regions, image.size)

        return Sam3Refinement(
            regions=refined,
            candidate_count=len(sam_regions),
            refined_count=len(refined),
        )

    def _candidate_regions(
        self,
        result: dict[str, Any],
        image_size: tuple[int, int],
    ) -> list[NailRegion]:
        import numpy as np

        masks = result["masks"].detach().float().cpu().numpy()
        scores = result["scores"].detach().float().cpu().numpy().reshape(-1)
        while masks.ndim > 3 and masks.shape[1] == 1:
            masks = masks[:, 0]

        candidates: list[NailRegion] = []
        for index, score_value in enumerate(scores):
            score = float(score_value)
            if score < self.min_score or index >= len(masks):
                continue
            mask = masks[index] > 0.0
            expected_shape = (image_size[1], image_size[0])
            if mask.shape != expected_shape:
                mask = np.asarray(
                    Image.fromarray(mask.astype(np.uint8), mode="L").resize(
                        image_size,
                        Image.Resampling.NEAREST,
                    )
                ) > 0
            region = region_from_binary_mask(mask, confidence=score, source="sam3_text_fingernail")
            if region is None:
                continue
            area_ratio = _region_area(region) / max(image_size[0] * image_size[1], 1)
            if area_ratio < 0.00002 or area_ratio > 0.04:
                continue
            candidates.append(region)
        return candidates


def region_from_binary_mask(mask, *, confidence: float, source: str) -> NailRegion | None:
    import cv2
    import numpy as np

    binary = np.asarray(mask, dtype=np.uint8)
    if binary.ndim != 2 or not binary.any():
        return None
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    if area < 12:
        return None
    epsilon = max(0.5, 0.0025 * cv2.arcLength(contour, True))
    polygon_np = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2).astype(np.float32)
    if polygon_np.shape[0] < 4:
        return None
    (cx, cy), (rw, rh), angle = cv2.minAreaRect(polygon_np)
    if rw <= 1 or rh <= 1:
        return None
    width = min(float(rw), float(rh))
    height = max(float(rw), float(rh))
    if rw > rh:
        angle += 90
    return NailRegion(
        center_x=float(cx),
        center_y=float(cy),
        width=width,
        height=height,
        angle=float(angle),
        polygon=tuple((float(x), float(y)) for x, y in polygon_np),
        confidence=float(confidence),
        source=source,
    )


def _region_area(region: NailRegion) -> float:
    if region.polygon:
        import cv2
        import numpy as np

        return abs(float(cv2.contourArea(np.asarray(region.polygon, dtype=np.float32))))
    return float(region.width * region.height)


def _region_iou(first: NailRegion, second: NailRegion, image_size: tuple[int, int]) -> float:
    import cv2
    import numpy as np

    width, height = image_size
    mask_a = np.zeros((height, width), dtype=np.uint8)
    mask_b = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask_a, [np.asarray(first.polygon, dtype=np.int32)], 1)
    cv2.fillPoly(mask_b, [np.asarray(second.polygon, dtype=np.int32)], 1)
    intersection = int(np.count_nonzero(mask_a & mask_b))
    union = int(np.count_nonzero(mask_a | mask_b))
    return intersection / union if union else 0.0


def _deduplicate_regions(regions: list[NailRegion], image_size: tuple[int, int]) -> list[NailRegion]:
    selected: list[NailRegion] = []
    for region in sorted(regions, key=lambda item: item.confidence, reverse=True):
        if any(_region_iou(region, existing, image_size) > 0.65 for existing in selected):
            continue
        selected.append(region)
    return selected
