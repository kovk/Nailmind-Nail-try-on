from __future__ import annotations

from dataclasses import dataclass, field, replace
from io import BytesIO
from pathlib import Path
import time
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .config import get_settings
from .mask import NailMaskDetector, NailRegion
from .style import StyleExtractor
from .style_asset import FINGER_NAMES, load_style_asset_images


@dataclass
class EditResult:
    image_bytes: bytes
    metrics: dict[str, Any] = field(default_factory=dict)


class TryOnEditor:
    """Image editor boundary.

    Replace `_edit_with_model` when the GPU model is ready. The public API and
    backend integration should stay unchanged.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.mask_detector = NailMaskDetector(
            allow_heuristic=self.settings.allow_heuristic_mask,
            dilate=self.settings.mask_dilate,
            blur=self.settings.mask_blur,
        )
        self.style_extractor = StyleExtractor()
        self._pipeline = None
        self._flux2_pipeline = None
        self._flux2_inpaint_pipeline = None
        self._reference_adapter_loaded = False

    def edit(
        self,
        hand_image: bytes,
        style_image: bytes,
        prompt: str | None = None,
        style_nail_asset: bytes | None = None,
        style_asset_id: str | None = None,
    ) -> bytes:
        return self.edit_with_metrics(
            hand_image=hand_image,
            style_image=style_image,
            prompt=prompt,
            style_nail_asset=style_nail_asset,
            style_asset_id=style_asset_id,
        ).image_bytes

    def preload(self) -> None:
        self.mask_detector.preload_user_segmenter()
        backend = self.settings.editor_backend.strip().lower()
        if backend in {"flux2", "flux2_klein", "klein"}:
            self._get_flux2_pipeline()
        if backend in {"flux2_klein_inpaint", "klein_inpaint"}:
            self._get_flux2_inpaint_pipeline()
        if backend in {
            "local_inpaint",
            "local_edit",
            "hybrid_local",
            "reference_local_edit",
            "reference_inpaint",
            "ip_adapter_inpaint",
            "hybrid",
            "hybrid_overlay",
            "sdxl",
            "sdxl_inpaint",
        }:
            self._get_sdxl_pipeline()
        if backend in {"reference_local_edit", "reference_inpaint", "ip_adapter_inpaint"}:
            self._ensure_reference_adapter()

    def edit_with_metrics(
        self,
        hand_image: bytes,
        style_image: bytes,
        prompt: str | None = None,
        style_nail_asset: bytes | None = None,
        style_asset_id: str | None = None,
    ) -> EditResult:
        backend = self.settings.editor_backend.strip().lower()
        if self.settings.production_mode and backend in {"mock", "mask_only"}:
            raise RuntimeError("生产模式禁止使用 mock/mask_only 推理后端。")
        if self.settings.production_mode and self.settings.allow_heuristic_mask:
            raise RuntimeError("生产模式禁止启用启发式甲面区域，必须使用真实手部/甲面检测。")
        if self.settings.require_style_nail_asset and not style_nail_asset and not style_asset_id:
            raise RuntimeError("STYLE_ASSET_MISSING: 缺少预抠甲面素材，拒绝生成低质量试戴图。")
        style_references = self._load_style_references(
            style_image=style_image,
            style_nail_asset=style_nail_asset,
            style_asset_id=style_asset_id,
        )
        if self.settings.inference_mock or backend == "mock":
            return EditResult(self._normalize_output(hand_image), {"backend": "mock"})
        if backend == "mask_only":
            return EditResult(self._debug_mask_overlay(hand_image), {"backend": "mask_only"})
        if backend in {"flux2", "flux2_klein", "klein"}:
            return self._edit_with_flux2_klein(
                hand_image=hand_image,
                style_image=style_image,
                style_images=style_references,
                prompt=prompt,
                style_asset_id=style_asset_id,
            )
        if backend in {"flux2_klein_inpaint", "klein_inpaint"}:
            return self._edit_with_flux2_klein_inpaint(
                hand_image=hand_image,
                style_image=style_image,
                style_images=style_references,
                prompt=prompt,
                style_asset_id=style_asset_id,
            )
        if backend in {"overlay", "nail_overlay"}:
            return self._edit_with_overlay(hand_image=hand_image, style_images=style_references)
        if backend in {"local_inpaint", "local_edit", "hybrid_local"}:
            return self._edit_with_local_inpaint(
                hand_image=hand_image,
                style_image=style_image,
                style_images=style_references,
                prompt=prompt,
                style_asset_id=style_asset_id,
                reference_conditioned=False,
            )
        if backend in {"reference_local_edit", "reference_inpaint", "ip_adapter_inpaint"}:
            return self._edit_with_local_inpaint(
                hand_image=hand_image,
                style_image=style_image,
                style_images=style_references,
                prompt=prompt,
                style_asset_id=style_asset_id,
                reference_conditioned=True,
            )
        if backend in {"hybrid", "hybrid_overlay"}:
            image_bytes = self._edit_with_hybrid_overlay(
                hand_image=hand_image,
                style_image=style_image,
                style_images=style_references,
                prompt=prompt,
            )
            return EditResult(image_bytes, {"backend": "hybrid_overlay", "styleAssetId": style_asset_id})
        if backend in {"sdxl", "sdxl_inpaint"}:
            return EditResult(
                self._edit_with_sdxl(hand_image=hand_image, style_image=style_image, prompt=prompt),
                {"backend": "sdxl_inpaint"},
            )
        return EditResult(
            self._edit_with_model(hand_image=hand_image, style_image=style_image, prompt=prompt),
            {"backend": backend},
        )

    def _edit_with_model(self, hand_image: bytes, style_image: bytes, prompt: str | None) -> bytes:
        raise RuntimeError(
            f"Unsupported EDITOR_BACKEND={self.settings.editor_backend!r}. "
            "Use mock, mask_only, or sdxl_inpaint."
        )

    def _edit_with_flux2_klein(
        self,
        *,
        hand_image: bytes,
        style_image: bytes,
        style_images: list[Image.Image],
        prompt: str | None,
        style_asset_id: str | None,
    ) -> EditResult:
        import torch  # type: ignore

        original = self._load_original_image(hand_image)
        width, height = _fit_flux2_size(
            original.size,
            max_side=self.settings.flux2_max_image_side,
            min_side=self.settings.flux2_min_image_side,
        )
        hand_reference = original.resize((width, height), Image.Resampling.LANCZOS)
        style_reference = self._build_flux2_style_reference(style_images=style_images, style_image=style_image)
        pipeline = self._get_flux2_pipeline()
        final_prompt = self._build_flux2_prompt(prompt=prompt)
        generator = torch.Generator(device=self.settings.device).manual_seed(int(self.settings.flux2_seed))

        if self.settings.device.startswith("cuda"):
            torch.cuda.synchronize()
        started = time.perf_counter()
        result = pipeline(
            prompt=final_prompt,
            image=[hand_reference, style_reference],
            height=height,
            width=width,
            num_inference_steps=max(1, int(self.settings.flux2_steps)),
            guidance_scale=float(self.settings.flux2_guidance_scale),
            generator=generator,
        ).images[0].convert("RGB")
        if self.settings.device.startswith("cuda"):
            torch.cuda.synchronize()
        generation_ms = int((time.perf_counter() - started) * 1000)

        if self.settings.preserve_original_resolution and result.size != original.size:
            result = result.resize(original.size, Image.Resampling.LANCZOS)
        metrics = {
            "backend": "flux2_klein",
            "model": self._flux2_model_reference(),
            "generationMs": generation_ms,
            "steps": int(self.settings.flux2_steps),
            "seed": int(self.settings.flux2_seed),
            "workingImageSize": [width, height],
            "outputImageSize": [result.width, result.height],
            "styleAssetId": style_asset_id,
            "styleReferenceCount": len(style_images),
        }
        return EditResult(self._image_to_png_bytes(result), metrics)

    def _get_flux2_pipeline(self):
        if self._flux2_pipeline is not None:
            return self._flux2_pipeline
        try:
            import torch  # type: ignore
            from diffusers import Flux2KleinPipeline  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "FLUX.2 dependencies are missing. Install the current diffusers main build and transformers."
            ) from exc

        dtype_name = self.settings.torch_dtype.strip().lower()
        dtype = torch.bfloat16 if dtype_name in {"bfloat16", "bf16"} else torch.float16
        self._flux2_pipeline = Flux2KleinPipeline.from_pretrained(
            self._flux2_model_reference(),
            torch_dtype=dtype,
        )
        if self.settings.enable_cpu_offload:
            self._flux2_pipeline.enable_model_cpu_offload()
        else:
            self._flux2_pipeline.to(self.settings.device)
        return self._flux2_pipeline

    def _edit_with_flux2_klein_inpaint(
        self,
        *,
        hand_image: bytes,
        style_image: bytes,
        style_images: list[Image.Image],
        prompt: str | None,
        style_asset_id: str | None,
    ) -> EditResult:
        import torch  # type: ignore

        original = self._load_original_image(hand_image)
        overlay, original_mask, registration_metrics = self._overlay_on_work_image(
            hand=original.copy(),
            style_images=style_images,
        )
        detected_nails = int(registration_metrics.get("detectedNails") or 0)
        if detected_nails <= 0:
            raise RuntimeError("未检测到指甲区域，无法执行局部试戴。")
        width, height = _fit_flux2_size(
            original.size,
            max_side=self.settings.flux2_max_image_side,
            min_side=self.settings.flux2_min_image_side,
        )
        hand_reference = overlay.resize((width, height), Image.Resampling.LANCZOS)
        repair_mask = _build_boundary_ring_mask(
            original_mask,
            edge_width=max(1, int(self.settings.flux2_inpaint_edge_width)),
        )
        mask_reference = repair_mask.resize((width, height), Image.Resampling.LANCZOS)
        style_reference = self._build_flux2_style_reference(
            style_images=style_images,
            style_image=style_image,
        )
        pipeline = self._get_flux2_inpaint_pipeline()
        generator = torch.Generator(device=self.settings.device).manual_seed(int(self.settings.flux2_seed))

        if self.settings.device.startswith("cuda"):
            torch.cuda.synchronize()
        started = time.perf_counter()
        result = pipeline(
            prompt=self._build_flux2_refine_prompt(prompt=prompt),
            image=hand_reference,
            image_reference=style_reference,
            mask_image=mask_reference,
            height=height,
            width=width,
            padding_mask_crop=max(0, int(self.settings.flux2_inpaint_padding)),
            strength=float(self.settings.flux2_inpaint_strength),
            num_inference_steps=max(1, int(self.settings.flux2_steps)),
            guidance_scale=float(self.settings.flux2_guidance_scale),
            generator=generator,
        ).images[0].convert("RGB")
        if self.settings.device.startswith("cuda"):
            torch.cuda.synchronize()
        generation_ms = int((time.perf_counter() - started) * 1000)

        if result.size != original.size:
            result = result.resize(original.size, Image.Resampling.LANCZOS)
        # The model may alter unmasked pixels internally. Composite through the
        # exact nail mask so hand anatomy, skin, jewellery and background remain
        # byte-for-byte on the deterministic registration path.
        result = Image.composite(result, overlay.convert("RGB"), repair_mask)
        metrics = dict(registration_metrics)
        metrics.update({
            "backend": "flux2_klein_inpaint",
            "baseRegistrationBackend": "contour_uv",
            "model": self._flux2_model_reference(),
            "generationMs": generation_ms,
            "steps": int(self.settings.flux2_steps),
            "strength": float(self.settings.flux2_inpaint_strength),
            "inpaintMaskMode": "boundary_ring",
            "inpaintEdgeWidth": int(self.settings.flux2_inpaint_edge_width),
            "detectedNails": detected_nails,
            "workingImageSize": [width, height],
            "outputImageSize": [result.width, result.height],
            "styleAssetId": style_asset_id,
            "styleReferenceCount": len(style_images),
        })
        return EditResult(self._image_to_png_bytes(result), metrics)

    def _get_flux2_inpaint_pipeline(self):
        if self._flux2_inpaint_pipeline is not None:
            return self._flux2_inpaint_pipeline
        try:
            import torch  # type: ignore
            from diffusers import Flux2KleinInpaintPipeline  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "FLUX.2 Klein inpaint dependencies are missing. Install the current diffusers build."
            ) from exc

        dtype_name = self.settings.torch_dtype.strip().lower()
        dtype = torch.bfloat16 if dtype_name in {"bfloat16", "bf16"} else torch.float16
        self._flux2_inpaint_pipeline = Flux2KleinInpaintPipeline.from_pretrained(
            self._flux2_model_reference(),
            torch_dtype=dtype,
        )
        if self.settings.enable_cpu_offload:
            self._flux2_inpaint_pipeline.enable_model_cpu_offload()
        else:
            self._flux2_inpaint_pipeline.to(self.settings.device)
        return self._flux2_inpaint_pipeline

    def _flux2_model_reference(self) -> str:
        model_dir = self.settings.flux2_model_dir.strip()
        if model_dir:
            model_path = Path(model_dir)
            if model_path.is_dir() and (model_path / "model_index.json").is_file():
                return model_dir
        return self.settings.flux2_model_id

    def _build_flux2_style_reference(
        self,
        *,
        style_images: list[Image.Image],
        style_image: bytes,
    ) -> Image.Image:
        if style_images:
            reference = style_images[0].convert("RGBA")
            background = Image.new("RGBA", reference.size, (255, 255, 255, 255))
            background.alpha_composite(reference)
            return background.convert("RGB")
        return self._load_original_image(style_image)

    @staticmethod
    def _build_flux2_prompt(*, prompt: str | None) -> str:
        business_prompt = (prompt or "").strip()
        return (
            "Image 1 is the base hand photograph. Image 2 is the nail-art reference. "
            "Edit only the visible fingernails in image 1. Transfer the exact colors, patterns, "
            "gloss, french-tip layout, and decorations from image 2 to every visible fingernail. "
            "Keep the exact finger count, hand anatomy, pose, skin texture, skin tone, jewelry, "
            "lighting, background, camera angle, and framing of image 1 unchanged. "
            "Do not add or remove fingers. Do not change finger length or nail positions. "
            "The result must look like a realistic professional manicure photograph. "
            f"{business_prompt}"
        ).strip()

    @staticmethod
    def _build_flux2_refine_prompt(*, prompt: str | None) -> str:
        business_prompt = (prompt or "").strip()
        return (
            "Image 1 already contains geometrically registered nail art. Image 2 is the exact "
            "nail-art reference. Refine only the visible nail surfaces inside the supplied mask. "
            "Preserve the exact nail boundaries, length, angle, colors, patterns and decorations "
            "already present in image 1. Add only realistic nail curvature, subtle sidewall and "
            "cuticle shadows, natural glossy reflections, and seamless skin-to-nail edge blending. "
            "Do not redraw fingers, skin, jewellery, background or camera framing. Do not change "
            "finger count or hand anatomy. Do not simplify or invent nail art. "
            f"{business_prompt}"
        ).strip()

    def _edit_with_sdxl(self, hand_image: bytes, style_image: bytes, prompt: str | None) -> bytes:
        original = self._load_original_image(hand_image)
        hand = self._fit_for_model(original)
        style_words = self.style_extractor.describe(style_image)
        mask = self.mask_detector.build_mask_for_image(hand)
        final_prompt = self._build_prompt(style_words=style_words, prompt=prompt)
        pipeline = self._get_sdxl_pipeline()
        result = pipeline(
            prompt=final_prompt,
            negative_prompt=(
                "extra fingers, missing fingers, deformed hand, changed skin tone, "
                "changed background, text, watermark, low quality, blurry"
            ),
            image=hand,
            mask_image=mask,
            num_inference_steps=self.settings.inference_steps,
            guidance_scale=self.settings.guidance_scale,
            strength=self.settings.strength,
        ).images[0]
        result = self._restore_original_resolution(original=original, edited=result, mask=mask)
        return self._image_to_png_bytes(result)

    def _edit_with_local_inpaint(
        self,
        *,
        hand_image: bytes,
        style_image: bytes,
        style_images: list[Image.Image],
        prompt: str | None,
        style_asset_id: str | None,
        reference_conditioned: bool = False,
    ) -> EditResult:
        original = self._load_original_image(hand_image)
        overlay, mask, metrics = self._overlay_on_work_image(hand=original.copy(), style_images=style_images)
        style_words = self.style_extractor.describe(style_image)
        style_reference = (
            self._build_style_reference_image(style_images=style_images, style_image=style_image)
            if reference_conditioned
            else None
        )
        refined = self._local_inpaint_refine(
            original=original,
            overlay=overlay,
            mask=mask,
            prompt=self._build_local_refine_prompt(style_words=style_words, prompt=prompt),
            style_reference=style_reference,
        )
        metrics.update(
            {
                "backend": "reference_local_edit" if reference_conditioned else "local_inpaint",
                "baseRegistrationBackend": "overlay",
                "styleAssetId": style_asset_id,
                "styleReferenceCount": len(style_images),
                "outputImageSize": [refined.width, refined.height],
                "localEdit": True,
                "referenceConditioned": reference_conditioned,
                "referenceAdapterScale": self.settings.reference_adapter_scale if reference_conditioned else None,
                "localEditStrength": self.settings.local_edit_strength,
                "localEditSteps": self.settings.local_edit_steps,
            }
        )
        return EditResult(self._image_to_png_bytes(refined), metrics)

    def _edit_with_hybrid_overlay(
        self,
        hand_image: bytes,
        style_image: bytes,
        style_images: list[Image.Image],
        prompt: str | None,
    ) -> bytes:
        original = self._load_original_image(hand_image)
        hand = self._fit_for_model(original)
        overlay, mask, _metrics = self._overlay_on_work_image(hand=hand, style_images=style_images)
        style_words = self.style_extractor.describe(style_image)
        final_prompt = self._build_prompt(style_words=style_words, prompt=prompt)
        pipeline = self._get_sdxl_pipeline()
        result = pipeline(
            prompt=final_prompt,
            negative_prompt=(
                "extra fingers, missing fingers, deformed hand, changed skin tone, "
                "changed background, text, watermark, low quality, blurry, plastic skin"
            ),
            image=overlay,
            mask_image=mask,
            num_inference_steps=self.settings.inference_steps,
            guidance_scale=self.settings.guidance_scale,
            strength=min(self.settings.strength, 0.42),
        ).images[0]
        result = self._restore_original_resolution(original=original, edited=result, mask=mask)
        return self._image_to_png_bytes(result)

    def _edit_with_overlay(self, hand_image: bytes, style_images: list[Image.Image]) -> EditResult:
        original = self._load_original_image(hand_image)
        hand = self._fit_for_model(original)
        overlay, mask, metrics = self._overlay_on_work_image(hand=hand, style_images=style_images)
        result = self._restore_original_resolution(original=original, edited=overlay, mask=mask)
        metrics.update(
            {
                "backend": "overlay",
                "styleReferenceCount": len(style_images),
                "workImageSize": [hand.width, hand.height],
                "outputImageSize": [result.width, result.height],
            }
        )
        return EditResult(self._image_to_png_bytes(result), metrics)

    def _overlay_on_work_image(self, *, hand: Image.Image, style_images: list[Image.Image]) -> tuple[Image.Image, Image.Image, dict[str, Any]]:
        regions = self._select_target_regions(self.mask_detector.detect_regions(hand), hand)
        if not regions:
            raise RuntimeError("NO_HAND_DETECTED: 未检测到有效手部或指甲区域。")
        if len(regions) < self.settings.min_valid_nails:
            raise RuntimeError(
                f"NAIL_SEGMENTATION_FAILED: 仅检测到 {len(regions)} 片有效指甲，无法生成可靠试戴图。"
            )
        mask = self.mask_detector.build_mask_from_regions(hand.size, regions)
        result = hand.copy()
        applied = 0
        coverage_values: list[float] = []
        registration_modes: list[str] = []
        region_metrics: list[dict[str, Any]] = []
        for idx, region in enumerate(regions):
            style_index = region.finger_index if region.finger_index is not None else idx
            style = style_images[style_index % len(style_images)]
            next_result, applied_region, coverage, registration_mode, region_detail = self._apply_style_to_region(
                result,
                style,
                region,
                idx,
            )
            result = next_result
            region_detail = {
                "index": idx,
                "finger": (
                    FINGER_NAMES[style_index]
                    if style_index < len(FINGER_NAMES)
                    else f"finger_{style_index + 1}"
                ),
                "center": [round(float(region.center_x), 2), round(float(region.center_y), 2)],
                "size": [round(float(region.width), 2), round(float(region.height), 2)],
                "angle": round(float(region.angle), 2),
                "coverage": round(float(coverage), 4),
                "registration": registration_mode,
                "applied": bool(applied_region),
                **region_detail,
            }
            region_metrics.append(region_detail)
            if applied_region:
                applied += 1
                coverage_values.append(coverage)
                registration_modes.append(registration_mode)
        if applied < self.settings.min_valid_nails:
            raise RuntimeError(
                f"NAIL_REGISTRATION_FAILED: 仅成功配准 {applied} 片指甲，低于上线要求 {self.settings.min_valid_nails} 片。"
            )
        mask_area = _mask_area(mask)
        image_area = max(1, hand.width * hand.height)
        low_coverage_regions = [
            item
            for item in region_metrics
            if item.get("applied") and float(item.get("coverage") or 0) < 0.45
        ]
        metrics = {
            "detectedNails": len(regions),
            "registeredNails": applied,
            "nailMaskCoverage": round(mask_area / image_area, 5),
            "meanRegionCoverage": round(sum(coverage_values) / len(coverage_values), 4) if coverage_values else 0,
            "minRegionCoverage": round(min(coverage_values), 4) if coverage_values else 0,
            "maxRegionCoverage": round(max(coverage_values), 4) if coverage_values else 0,
            "lowCoverageCount": len(low_coverage_regions),
            "qualityGate": "needs_review" if low_coverage_regions else "passed",
            "qualityWarnings": [
                f"{item['finger']} 覆盖率 {item['coverage']} 偏低，可能存在分割或配准偏移。"
                for item in low_coverage_regions
            ],
            "regions": region_metrics,
            "registration": _summarize_modes(registration_modes, fallback=self.settings.registration_mode or "perspective"),
            "edgeRepair": bool(self.settings.enable_edge_repair),
        }
        return result, mask, metrics

    def _select_target_regions(self, regions: list[NailRegion], image: Image.Image) -> list[NailRegion]:
        """Keep the most plausible user fingernails for production rendering."""
        if not regions:
            return []
        image_size = image.size
        image_area = max(1, image_size[0] * image_size[1])
        valid: list[tuple[float, NailRegion]] = []
        for region in regions:
            area = _region_area(region)
            area_ratio = area / image_area
            aspect = region.height / max(region.width, 1.0)
            if area_ratio < 0.000025 or area_ratio > 0.025:
                continue
            if not 0.9 <= aspect <= 5.8:
                continue
            if region.width < 4 or region.height < 7:
                continue
            valid.append((area, region))
        if not valid:
            return []

        landmark_regions = self.mask_detector._detect_with_mediapipe(image)
        if landmark_regions:
            matched = self._match_regions_to_landmarks(
                candidates=[region for _, region in sorted(valid, key=lambda item: item[0], reverse=True)[:10]],
                landmarks=landmark_regions,
                image_size=image_size,
            )
            if len(matched) >= self.settings.min_valid_nails:
                return matched[:5]
            return []

        dominant = [region for _, region in sorted(valid, key=lambda item: item[0], reverse=True)[:5]]
        return sorted(dominant, key=lambda region: region.center_x)

    def _match_regions_to_landmarks(
        self,
        *,
        candidates: list[NailRegion],
        landmarks: list[NailRegion],
        image_size: tuple[int, int],
    ) -> list[NailRegion]:
        """Bind precise YOLO masks to MediaPipe fingertip priors.

        YOLO-seg gives the usable mask polygon, but it can occasionally classify
        palm wrinkles, rings or background edges as nails. MediaPipe is less
        precise, but it gives reliable fingertip locations. A candidate must be
        close to one fingertip prior before it is allowed into production output.
        """
        if not candidates or not landmarks:
            return []

        import math

        short_side = max(1.0, float(min(image_size)))
        used: set[int] = set()
        matched: list[NailRegion] = []
        for landmark_index, landmark in enumerate(landmarks[:5]):
            best_idx: int | None = None
            best_score: float | None = None
            max_distance = max(26.0, landmark.height * 1.15, landmark.width * 2.4, short_side * 0.052)
            for idx, candidate in enumerate(candidates):
                if idx in used:
                    continue
                distance = _region_center_distance(candidate, landmark)
                if distance > max_distance:
                    continue
                candidate_area = max(_region_area(candidate), 1.0)
                landmark_area = max(landmark.width * landmark.height, 1.0)
                area_ratio = candidate_area / landmark_area
                if area_ratio < 0.08 or area_ratio > 3.2:
                    continue
                aspect = candidate.height / max(candidate.width, 1.0)
                landmark_aspect = landmark.height / max(landmark.width, 1.0)
                aspect_penalty = abs(math.log(max(aspect, 0.1) / max(landmark_aspect, 0.1))) * 8.0
                area_penalty = abs(math.log(area_ratio)) * 10.0
                score = distance + area_penalty + aspect_penalty
                if best_score is None or score < best_score:
                    best_score = score
                    best_idx = idx
            if best_idx is not None:
                used.add(best_idx)
                finger_index = landmark.finger_index if landmark.finger_index is not None else landmark_index
                matched.append(
                    replace(
                        candidates[best_idx],
                        finger_index=finger_index,
                        angle=landmark.angle,
                    )
                )
        return matched

    def _apply_style_to_region(
        self,
        hand: Image.Image,
        style: Image.Image,
        region: NailRegion,
        index: int,
    ) -> tuple[Image.Image, bool, float, str, dict[str, Any]]:
        patch_size = int(max(region.width, region.height) * 2.4)
        if patch_size < 8:
            return hand, False, 0.0, "skipped", {"reason": "target_too_small"}

        texture = self._make_style_patch(style=style, size=patch_size, index=index)
        perspective_result = self._apply_perspective_style_to_region(hand, style, texture, region)
        if perspective_result is not None:
            return perspective_result

        nail_mask = Image.new("L", (patch_size, patch_size), 0)
        draw = ImageDraw.Draw(nail_mask)
        inset_x = (patch_size - region.width) / 2
        inset_y = (patch_size - region.height) / 2
        draw.rounded_rectangle(
            (inset_x, inset_y, patch_size - inset_x, patch_size - inset_y),
            radius=max(3, int(region.width * 0.42)),
            fill=255,
        )

        highlight = Image.new("RGBA", (patch_size, patch_size), (0, 0, 0, 0))
        highlight_draw = ImageDraw.Draw(highlight)
        highlight_draw.rounded_rectangle(
            (
                patch_size * 0.42,
                inset_y + region.height * 0.08,
                patch_size * 0.52,
                inset_y + region.height * 0.62,
            ),
            radius=max(2, int(region.width * 0.18)),
            fill=(255, 255, 255, int(255 * self.settings.overlay_highlight_alpha)),
        )
        texture = Image.alpha_composite(texture.convert("RGBA"), highlight)

        nail_mask = nail_mask.filter(ImageFilter.GaussianBlur(1.4))
        texture = texture.rotate(region.angle, resample=Image.Resampling.BICUBIC, expand=True)
        nail_mask = nail_mask.rotate(region.angle, resample=Image.Resampling.BICUBIC, expand=True)

        left = int(region.center_x - texture.width / 2)
        top = int(region.center_y - texture.height / 2)
        canvas = Image.new("RGBA", hand.size, (0, 0, 0, 0))
        canvas.paste(texture, (left, top), nail_mask.point(lambda value: int(value * self.settings.overlay_alpha)))
        return (
            Image.alpha_composite(hand.convert("RGBA"), canvas).convert("RGB"),
            True,
            0.75,
            "affine_fallback",
            {
                "targetBox": [left, top, left + texture.width, top + texture.height],
                "patchSize": patch_size,
            },
        )

    def _apply_perspective_style_to_region(
        self,
        hand: Image.Image,
        style: Image.Image,
        texture: Image.Image,
        region: NailRegion,
    ) -> tuple[Image.Image, bool, float, str, dict[str, Any]] | None:
        if not region.polygon or len(region.polygon) < 4:
            return None
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception:
            return None

        target = np.asarray(region.polygon, dtype=np.float32)
        rect = cv2.minAreaRect(target.astype(np.float32))
        target_quad = _quad_from_nail_polygon(target, angle_degrees=region.angle)
        if not _valid_quad(target_quad):
            target_quad = _ordered_box_points(cv2.boxPoints(rect))
        # Overscan the texture, then clip it with the precise segmentation mask.
        # Shrinking the quad leaves a visible ring of the original nail whenever
        # the source asset has transparent margins or the target nail is curved.
        quad_center = np.mean(target_quad, axis=0, keepdims=True)
        target_quad = quad_center + (target_quad - quad_center) * 1.06
        target_w = max(8, int(max(_point_distance(target_quad[0], target_quad[1]), _point_distance(target_quad[2], target_quad[3]))))
        target_h = max(12, int(max(_point_distance(target_quad[1], target_quad[2]), _point_distance(target_quad[3], target_quad[0]))))
        texture = self._make_region_texture(style=style, fallback=texture, width=target_w, height=target_h, index=0)

        source_quad = np.asarray(
            [
                [0, 0],
                [texture.width - 1, 0],
                [texture.width - 1, texture.height - 1],
                [0, texture.height - 1],
            ],
            dtype=np.float32,
        )
        texture_np = np.asarray(texture.convert("RGBA"), dtype=np.uint8)
        # A canonical style asset has its own nail silhouette. Reusing that
        # silhouette as runtime alpha exposes the user's original nail whenever
        # its shape differs from the target. Extend edge colours into the
        # transparent area and let the user's segmentation mask be the only
        # final silhouette.
        texture_np = _extend_texture_to_canvas(texture_np)
        contour_warp = _warp_texture_to_nail_contour(
            texture_np=texture_np,
            polygon=target,
            angle_degrees=region.angle,
            output_size=hand.size,
        )
        if contour_warp is not None:
            warped = contour_warp
            registration_mode = "contour_uv"
        else:
            warped, registration_mode = _warp_texture(
                texture_np=texture_np,
                source_quad=source_quad,
                target_quad=target_quad,
                output_size=hand.size,
                mode=self.settings.registration_mode,
            )

        polygon_mask = np.zeros((hand.height, hand.width), dtype=np.uint8)
        cv2.fillPoly(polygon_mask, [target.astype(np.int32)], 255)
        # The segmentation polygon is the final geometry boundary. Do not erode
        # it: even a one-pixel inset is conspicuous on a small fingernail.
        feather = max(0.28, min(0.72, min(target_w, target_h) * 0.018))
        polygon_mask = cv2.GaussianBlur(polygon_mask, (0, 0), sigmaX=feather)
        warped_alpha = warped[:, :, 3]
        missing_texture = ((polygon_mask > 12) & (warped_alpha < 12)).astype(np.uint8) * 255
        if bool(np.any(missing_texture)):
            # Curved segmentation masks can extend beyond the four TPS corner
            # controls. Continue the nearest registered colour into those small
            # corners before applying the exact target alpha, avoiding black
            # wedges without exposing the user's original nail.
            fill_radius = max(3, int(round(min(target_w, target_h) * 0.08)))
            for channel in range(3):
                warped[:, :, channel] = cv2.inpaint(
                    warped[:, :, channel],
                    missing_texture,
                    fill_radius,
                    cv2.INPAINT_TELEA,
                )
        alpha = polygon_mask.astype(np.float32) / 255.0
        alpha *= min(float(self.settings.overlay_alpha), 0.96)
        if alpha.max() <= 0.01:
            return None

        hand_np = np.asarray(hand.convert("RGB"), dtype=np.float32)
        color_np = warped[:, :, :3].astype(np.float32)
        color_np = _match_patch_lighting(color_np, hand_np, alpha)
        color_np = _preserve_style_detail(color_np, alpha)
        color_np = _apply_nail_surface_lighting(
            color_np=color_np,
            hand_np=hand_np,
            alpha=alpha,
            target_quad=target_quad,
        )
        blurred_alpha = cv2.GaussianBlur(alpha, (0, 0), sigmaX=max(0.25, feather * 0.7))
        alpha_3 = np.clip(blurred_alpha[:, :, None], 0.0, 1.0)
        # Preserve a small amount of the original nail luminance so the result
        # follows the user's lighting instead of looking pasted on.
        color_np = color_np * 0.97 + hand_np * 0.03
        blended = hand_np * (1.0 - alpha_3) + color_np * alpha_3

        original_highlight = np.max(hand_np, axis=2, keepdims=True)
        highlight_mask = np.clip((original_highlight - 205.0) / 50.0, 0.0, 1.0) * alpha_3
        blended = blended * (1.0 - highlight_mask * 0.22) + hand_np * (highlight_mask * 0.22)
        specular = _synthetic_specular_mask(hand.size, target_quad, alpha)
        if specular is not None:
            blended = blended * (1.0 - specular[:, :, None] * 0.07) + 255.0 * (specular[:, :, None] * 0.07)
        if self.settings.enable_edge_repair:
            blended = _repair_nail_edge(
                blended=blended,
                original=hand_np,
                alpha=alpha,
                strength=float(self.settings.edge_repair_strength),
            )
        region_area = max(_region_area(region), 1.0)
        coverage = float(np.sum(alpha > 0.08) / region_area)
        coverage = max(0.0, min(1.0, coverage))
        detail = {
            "targetQuad": [[round(float(x), 2), round(float(y), 2)] for x, y in target_quad],
            "targetSize": [target_w, target_h],
            "targetArea": round(float(region_area), 2),
            "alphaPixels": int(np.sum(alpha > 0.08)),
        }
        return Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8), mode="RGB"), True, coverage, registration_mode, detail

    def _local_inpaint_refine(
        self,
        *,
        original: Image.Image,
        overlay: Image.Image,
        mask: Image.Image,
        prompt: str,
        style_reference: Image.Image | None = None,
    ) -> Image.Image:
        bbox = mask.convert("L").point(lambda value: 255 if value > 8 else 0).getbbox()
        if not bbox:
            return overlay.convert("RGB")
        crop_box = _expand_box(bbox, original.size, int(self.settings.local_edit_crop_padding))
        image_crop = overlay.crop(crop_box).convert("RGB")
        mask_crop = mask.crop(crop_box).convert("L")
        model_image, model_mask = _fit_pair_for_inpaint(
            image_crop,
            mask_crop,
            max_side=max(256, int(self.settings.model_max_image_side)),
        )
        pipeline = self._get_sdxl_pipeline()
        call_kwargs: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": (
                "extra fingers, missing fingers, deformed hand, changed hand pose, changed background, "
                "changed skin tone, blurred nails, text, watermark, dirty edge, sticker edge"
            ),
            "image": model_image,
            "mask_image": model_mask,
            "num_inference_steps": max(1, int(self.settings.local_edit_steps)),
            "guidance_scale": float(self.settings.local_edit_guidance_scale),
            "strength": float(self.settings.local_edit_strength),
        }
        if style_reference is not None:
            self._ensure_reference_adapter()
            call_kwargs["ip_adapter_image"] = self._fit_reference_image(style_reference)
        result = pipeline(**call_kwargs).images[0]
        if result.size != image_crop.size:
            result = result.convert("RGB").resize(image_crop.size, Image.Resampling.LANCZOS)
        paste_mask = mask_crop.filter(ImageFilter.GaussianBlur(1.2))
        refined = overlay.convert("RGB").copy()
        refined.paste(result.convert("RGB"), crop_box[:2], paste_mask)
        # Keep non-mask pixels exactly from the overlay/original path.
        return Image.composite(refined, overlay.convert("RGB"), mask)

    def _make_region_texture(
        self,
        *,
        style: Image.Image,
        fallback: Image.Image,
        width: int,
        height: int,
        index: int,
    ) -> Image.Image:
        source = ImageOps.exif_transpose(style).convert("RGBA")
        alpha = source.getchannel("A")
        bbox = alpha.getbbox()
        if not bbox:
            source = fallback.convert("RGBA")
            alpha = source.getchannel("A")
            bbox = alpha.getbbox()
        if bbox:
            pad = max(2, int(min(source.size) * 0.015))
            bbox = (
                max(0, bbox[0] - pad),
                max(0, bbox[1] - pad),
                min(source.width, bbox[2] + pad),
                min(source.height, bbox[3] + pad),
            )
            source = source.crop(bbox)
        # Transparent nail assets are already canonicalized during style
        # preprocessing. Fit the full alpha content into the target aspect ratio
        # instead of center-cropping, otherwise french tips/rhinestones near the
        # edge can be cut off before warping.
        source = _fit_transparent_to_aspect(source, width / max(height, 1))
        texture = source.resize((width, height), Image.Resampling.LANCZOS).convert("RGBA")
        texture = texture.filter(ImageFilter.UnsharpMask(radius=0.9, percent=115, threshold=2))
        texture = ImageEnhance.Color(texture).enhance(1.06)
        texture = ImageEnhance.Contrast(texture).enhance(1.05)
        return texture

    @staticmethod
    def _make_style_patch(*, style: Image.Image, size: int, index: int) -> Image.Image:
        style = ImageOps.exif_transpose(style).convert("RGBA")
        alpha = style.getchannel("A")
        bbox = alpha.getbbox()
        if bbox:
            pad = max(6, int(min(style.size) * 0.02))
            bbox = (
                max(0, bbox[0] - pad),
                max(0, bbox[1] - pad),
                min(style.width, bbox[2] + pad),
                min(style.height, bbox[3] + pad),
            )
            style = style.crop(bbox)
        width, height = style.size
        crop_side = int(min(width, height) * 0.72)
        grid_offsets = ((0.5, 0.5), (0.35, 0.45), (0.65, 0.45), (0.42, 0.62), (0.58, 0.62))
        ox, oy = grid_offsets[index % len(grid_offsets)]
        cx = int(width * ox)
        cy = int(height * oy)
        left = max(0, min(width - crop_side, cx - crop_side // 2))
        top = max(0, min(height - crop_side, cy - crop_side // 2))
        patch = style.crop((left, top, left + crop_side, top + crop_side)).resize((size, size), Image.Resampling.LANCZOS)
        patch = ImageEnhance.Color(patch).enhance(1.08)
        patch = ImageEnhance.Contrast(patch).enhance(1.04)
        return patch.convert("RGBA")

    def _load_style_references(
        self,
        *,
        style_image: bytes,
        style_nail_asset: bytes | None,
        style_asset_id: str | None,
    ) -> list[Image.Image]:
        if style_asset_id:
            return load_style_asset_images(style_asset_id)
        if style_nail_asset:
            return [Image.open(BytesIO(style_nail_asset)).convert("RGBA")]
        return [self._load_original_image(style_image).convert("RGBA")]

    def _get_sdxl_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        try:
            import torch  # type: ignore
            from diffusers import AutoPipelineForInpainting  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "GPU dependencies are missing. Install inference/requirements-gpu.txt on AutoDL."
            ) from exc

        dtype = torch.float16 if self.settings.torch_dtype.lower() in {"float16", "fp16"} else torch.float32
        model_dir = self.settings.model_dir.strip()
        model_ref = model_dir if model_dir and Path(model_dir).exists() else self.settings.model_id
        self._pipeline = AutoPipelineForInpainting.from_pretrained(
            model_ref,
            torch_dtype=dtype,
            variant="fp16" if dtype == torch.float16 else None,
            use_safetensors=True,
        )
        if self.settings.enable_cpu_offload:
            self._pipeline.enable_model_cpu_offload()
        else:
            self._pipeline.to(self.settings.device)
        try:
            self._pipeline.enable_xformers_memory_efficient_attention()
        except Exception:
            pass
        return self._pipeline

    def _ensure_reference_adapter(self) -> None:
        if self._reference_adapter_loaded:
            return
        adapter_dir = self.settings.reference_adapter_dir.strip()
        if not adapter_dir:
            raise RuntimeError(
                "REFERENCE_ADAPTER_MISSING: reference_local_edit 需要配置 REFERENCE_ADAPTER_DIR，"
                "否则模型只能修边，不能真正参考款式图。"
            )
        pipeline = self._get_sdxl_pipeline()
        if not hasattr(pipeline, "load_ip_adapter"):
            raise RuntimeError(
                "REFERENCE_ADAPTER_UNSUPPORTED: 当前 diffusers pipeline 不支持 IP-Adapter。"
            )
        kwargs: dict[str, str] = {}
        if self.settings.reference_adapter_subfolder.strip():
            kwargs["subfolder"] = self.settings.reference_adapter_subfolder.strip()
        if self.settings.reference_adapter_weight_name.strip():
            kwargs["weight_name"] = self.settings.reference_adapter_weight_name.strip()
        try:
            pipeline.load_ip_adapter(adapter_dir, **kwargs)
            if hasattr(pipeline, "set_ip_adapter_scale"):
                pipeline.set_ip_adapter_scale(float(self.settings.reference_adapter_scale))
        except Exception as exc:
            raise RuntimeError(
                "REFERENCE_ADAPTER_LOAD_FAILED: 无法加载参考图适配器，请检查 "
                "REFERENCE_ADAPTER_DIR / REFERENCE_ADAPTER_SUBFOLDER / REFERENCE_ADAPTER_WEIGHT_NAME。"
            ) from exc
        self._reference_adapter_loaded = True

    def _build_style_reference_image(self, *, style_images: list[Image.Image], style_image: bytes) -> Image.Image:
        if style_images:
            tiles = [
                ImageOps.contain(image.convert("RGBA"), (160, 240), Image.Resampling.LANCZOS)
                for image in style_images[:5]
            ]
            canvas = Image.new("RGBA", (max(1, len(tiles)) * 180 + 20, 280), (255, 255, 255, 255))
            for idx, tile in enumerate(tiles):
                x = 10 + idx * 180 + (160 - tile.width) // 2
                y = 20 + (240 - tile.height) // 2
                canvas.alpha_composite(tile, (x, y))
            return canvas.convert("RGB")
        return ImageOps.contain(
            self._load_original_image(style_image),
            (int(self.settings.reference_image_size), int(self.settings.reference_image_size)),
            Image.Resampling.LANCZOS,
        ).convert("RGB")

    def _fit_reference_image(self, image: Image.Image) -> Image.Image:
        size = max(128, int(self.settings.reference_image_size))
        return ImageOps.contain(image.convert("RGB"), (size, size), Image.Resampling.LANCZOS)

    def _normalize_output(self, image_bytes: bytes) -> bytes:
        image = self._load_original_image(image_bytes)
        return self._image_to_png_bytes(image)

    def _debug_mask_overlay(self, hand_image: bytes) -> bytes:
        hand = self._load_original_image(hand_image)
        mask = self.mask_detector.build_mask_for_image(hand)
        overlay = Image.new("RGB", hand.size, (230, 75, 130))
        result = Image.composite(overlay, hand, mask.point(lambda value: int(value * 0.42)))
        return self._image_to_png_bytes(result)

    @staticmethod
    def _load_original_image(image_bytes: bytes) -> Image.Image:
        image = Image.open(BytesIO(image_bytes))
        return ImageOps.exif_transpose(image).convert("RGB")

    def _fit_for_model(self, image: Image.Image) -> Image.Image:
        image = image.copy()
        image.thumbnail((self.settings.model_max_image_side, self.settings.model_max_image_side))
        return image

    def _restore_original_resolution(self, *, original: Image.Image, edited: Image.Image, mask: Image.Image) -> Image.Image:
        if not self.settings.preserve_original_resolution or edited.size == original.size:
            return edited.convert("RGB")
        edited_up = edited.convert("RGB").resize(original.size, Image.Resampling.LANCZOS)
        mask_up = mask.resize(original.size, Image.Resampling.LANCZOS)
        if self.settings.mask_blur:
            mask_up = mask_up.filter(ImageFilter.GaussianBlur(max(1, self.settings.mask_blur // 2)))
        return Image.composite(edited_up, original.convert("RGB"), mask_up)

    @staticmethod
    def _build_prompt(*, style_words: str, prompt: str | None) -> str:
        business_prompt = prompt or ""
        return (
            "photorealistic nail art edit, only modify visible fingernails, "
            f"apply nail style colors and decorations: {style_words}. "
            "preserve exact hand pose, finger count, skin texture, lighting, camera angle and background. "
            f"{business_prompt}"
        ).strip()

    @staticmethod
    def _build_local_refine_prompt(*, style_words: str, prompt: str | None) -> str:
        # Keep this under CLIP's short text limit. Backend business prompts are
        # ignored here because this model only repairs the already registered
        # nail overlay edges.
        compact_style = (style_words or "nail art")[:120]
        return (
            "realistic nail edge repair inside mask only, preserve fingers skin hand background, "
            f"natural glossy manicure, style {compact_style}"
        ).strip()

    @staticmethod
    def _image_to_png_bytes(image: Image.Image) -> bytes:
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()


def _order_quad_points(points):
    import numpy as np  # type: ignore

    pts = np.asarray(points, dtype=np.float32)
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).reshape(-1)
    ordered[0] = pts[np.argmin(sums)]
    ordered[2] = pts[np.argmax(sums)]
    ordered[1] = pts[np.argmin(diffs)]
    ordered[3] = pts[np.argmax(diffs)]
    return ordered


def _fit_flux2_size(
    size: tuple[int, int],
    *,
    max_side: int,
    min_side: int = 256,
) -> tuple[int, int]:
    width, height = size
    limit = max(256, int(max_side))
    target_min = min(limit, max(256, int(min_side)))
    scale = min(limit / max(width, height), max(1.0, target_min / max(width, height)))
    fitted_width = max(256, int(round(width * scale / 16.0)) * 16)
    fitted_height = max(256, int(round(height * scale / 16.0)) * 16)
    return fitted_width, fitted_height


def _quad_from_nail_polygon(polygon, angle_degrees: float | None = None):
    """Build a stable target quad from the actual nail mask, not its min box.

    `minAreaRect` is fast but unstable for curved or side-view nails: a tiny mask
    protrusion can rotate the whole texture. This PCA/envelope quad follows the
    detected polygon's long axis and uses local widths near both nail ends.
    """
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    points = np.asarray(polygon, dtype=np.float32)
    if points.shape[0] < 4:
        rect = cv2.minAreaRect(points)
        return _order_quad_points(cv2.boxPoints(rect).astype(np.float32))

    center = np.mean(points, axis=0)
    centered = points - center
    if angle_degrees is not None:
        radians = np.deg2rad(float(angle_degrees))
        axis = np.asarray([np.sin(radians), np.cos(radians)], dtype=np.float32)
    else:
        try:
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
            axis = vh[0].astype(np.float32)
        except Exception:
            rect = cv2.minAreaRect(points)
            return _order_quad_points(cv2.boxPoints(rect).astype(np.float32))
    if float(np.linalg.norm(axis)) < 1e-4:
        rect = cv2.minAreaRect(points)
        return _order_quad_points(cv2.boxPoints(rect).astype(np.float32))
    axis = axis / np.linalg.norm(axis)
    # Prefer a visually top-to-bottom direction for consistent style texture.
    if axis[1] < 0:
        axis = -axis
    normal = np.asarray([-axis[1], axis[0]], dtype=np.float32)
    if normal[0] < 0:
        normal = -normal
    v = centered @ axis
    u = centered @ normal
    v_min = float(np.min(v))
    v_max = float(np.max(v))
    if v_max - v_min < 8:
        rect = cv2.minAreaRect(points)
        return _order_quad_points(cv2.boxPoints(rect).astype(np.float32))

    top_v = v_min
    bottom_v = v_max
    # Registration needs an oriented envelope that fully covers the target.
    # The precise curved silhouette is applied later by the segmentation mask;
    # tapering this quad would leave uncovered wedges near the nail shoulders.
    left_u = float(np.min(u))
    right_u = float(np.max(u))
    top_center = center + axis * top_v
    bottom_center = center + axis * bottom_v
    quad = np.asarray(
        [
            top_center + normal * left_u,
            top_center + normal * right_u,
            bottom_center + normal * right_u,
            bottom_center + normal * left_u,
        ],
        dtype=np.float32,
    )
    return quad


def _summarize_modes(modes: list[str], *, fallback: str) -> str:
    if not modes:
        return fallback
    unique_modes = sorted(set(modes))
    if len(unique_modes) == 1:
        return unique_modes[0]
    return "+".join(unique_modes)


def _expand_box(box: tuple[int, int, int, int], image_size: tuple[int, int], padding: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    width, height = image_size
    padding = max(0, int(padding))
    return (
        max(0, left - padding),
        max(0, top - padding),
        min(width, right + padding),
        min(height, bottom + padding),
    )


def _fit_pair_for_inpaint(image: Image.Image, mask: Image.Image, *, max_side: int) -> tuple[Image.Image, Image.Image]:
    """Resize a local crop for diffusion without changing the final output size."""
    width, height = image.size
    max_side = max(128, int(max_side))
    scale = min(1.0, max_side / max(width, height, 1))
    target_w = max(64, int(width * scale))
    target_h = max(64, int(height * scale))
    target_w = max(64, (target_w // 8) * 8)
    target_h = max(64, (target_h // 8) * 8)
    if (target_w, target_h) == image.size:
        return image.convert("RGB"), mask.convert("L")
    return (
        image.convert("RGB").resize((target_w, target_h), Image.Resampling.LANCZOS),
        mask.convert("L").resize((target_w, target_h), Image.Resampling.LANCZOS),
    )


def _warp_texture(texture_np, source_quad, target_quad, output_size: tuple[int, int], mode: str):
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    requested_mode = (mode or "perspective").strip().lower()
    if requested_mode in {"tps", "thin_plate_spline", "thin-plate-spline"}:
        tps_result = _warp_texture_tps(texture_np, source_quad, target_quad, output_size)
        if tps_result is not None:
            return tps_result, "tps"
        mesh_result = _warp_texture_curved_mesh(texture_np, target_quad, output_size)
        if mesh_result is not None:
            return mesh_result, "tps_mesh"
    matrix = cv2.getPerspectiveTransform(np.asarray(source_quad, dtype=np.float32), np.asarray(target_quad, dtype=np.float32))
    warped = cv2.warpPerspective(
        texture_np,
        matrix,
        output_size,
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    if requested_mode in {"tps", "thin_plate_spline", "thin-plate-spline"}:
        return warped, "perspective_fallback"
    return warped, "perspective"


def _warp_texture_to_nail_contour(texture_np, polygon, angle_degrees: float | None, output_size: tuple[int, int]):
    """Stretch a canonical texture across every cross-section of a nail mask.

    A four-corner warp cannot represent a curved cuticle, convex sidewalls and a
    rounded tip at the same time. This dense UV map measures the left and right
    mask boundary along the finger axis, then maps the complete source texture
    into each target cross-section. The target polygon remains the final alpha.
    """
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    points = np.asarray(polygon, dtype=np.float32)
    if points.ndim != 2 or points.shape[0] < 4:
        return None
    canvas_w, canvas_h = output_size
    x, y, w, h = cv2.boundingRect(points.astype(np.int32))
    if w < 8 or h < 10:
        return None
    pad = 2
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(canvas_w, x + w + pad)
    y1 = min(canvas_h, y + h + pad)
    roi_w = x1 - x0
    roi_h = y1 - y0
    if roi_w < 8 or roi_h < 10:
        return None

    center = np.mean(points, axis=0)
    if angle_degrees is not None:
        radians = np.deg2rad(float(angle_degrees))
        axis = np.asarray([np.sin(radians), np.cos(radians)], dtype=np.float32)
    else:
        centered = points - center
        try:
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
            axis = vh[0].astype(np.float32)
        except Exception:
            return None
    norm = float(np.linalg.norm(axis))
    if norm < 1e-4:
        return None
    axis /= norm
    if axis[1] < 0:
        axis = -axis
    normal = np.asarray([-axis[1], axis[0]], dtype=np.float32)
    if normal[0] < 0:
        normal = -normal

    local_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
    local_polygon = np.rint(points - np.asarray([x0, y0], dtype=np.float32)).astype(np.int32)
    cv2.fillPoly(local_mask, [local_polygon], 255)
    ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dx = xs - center[0]
    dy = ys - center[1]
    projected_v = dx * axis[0] + dy * axis[1]
    projected_u = dx * normal[0] + dy * normal[1]
    inside = local_mask > 0
    if int(np.sum(inside)) < 24:
        return None

    v_inside = projected_v[inside]
    v_min = float(np.min(v_inside))
    v_max = float(np.max(v_inside))
    span_v = v_max - v_min
    if span_v < 8.0:
        return None
    bins = max(16, min(512, int(round(span_v)) + 1))
    v_normalized = np.clip((projected_v - v_min) / span_v, 0.0, 1.0)
    bin_index = np.clip(np.rint(v_normalized * (bins - 1)).astype(np.int32), 0, bins - 1)

    left = np.full(bins, np.inf, dtype=np.float32)
    right = np.full(bins, -np.inf, dtype=np.float32)
    np.minimum.at(left, bin_index[inside], projected_u[inside])
    np.maximum.at(right, bin_index[inside], projected_u[inside])
    valid_bins = np.isfinite(left) & np.isfinite(right) & ((right - left) >= 1.0)
    valid_indices = np.flatnonzero(valid_bins)
    if valid_indices.size < 2:
        return None
    all_indices = np.arange(bins, dtype=np.float32)
    left = np.interp(all_indices, valid_indices.astype(np.float32), left[valid_bins]).astype(np.float32)
    right = np.interp(all_indices, valid_indices.astype(np.float32), right[valid_bins]).astype(np.float32)

    row_position = v_normalized * (bins - 1)
    row_low = np.floor(row_position).astype(np.int32)
    row_high = np.minimum(row_low + 1, bins - 1)
    row_mix = row_position - row_low
    left_at_v = left[row_low] * (1.0 - row_mix) + left[row_high] * row_mix
    right_at_v = right[row_low] * (1.0 - row_mix) + right[row_high] * row_mix
    width_at_v = np.maximum(right_at_v - left_at_v, 1.0)
    u_normalized = (projected_u - left_at_v) / width_at_v

    source_h, source_w = texture_np.shape[:2]
    map_x = (np.clip(u_normalized, 0.0, 1.0) * (source_w - 1)).astype(np.float32)
    map_y = (v_normalized * (source_h - 1)).astype(np.float32)
    map_x = np.where(inside, map_x, -1).astype(np.float32)
    map_y = np.where(inside, map_y, -1).astype(np.float32)
    warped_roi = cv2.remap(
        texture_np,
        map_x,
        map_y,
        interpolation=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    warped_roi[:, :, 3] = local_mask
    output = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
    output[y0:y1, x0:x1] = warped_roi
    return output


def _extend_texture_to_canvas(texture_np):
    """Bleed opaque style pixels across transparent canvas before registration.

    Runtime geometry comes from the user's nail mask. Filling transparent source
    pixels prevents the source asset's narrower silhouette from revealing the
    original nail after it is warped onto a wider or rounder target.
    """
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    rgba = np.asarray(texture_np, dtype=np.uint8).copy()
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        return rgba
    opaque = rgba[:, :, 3] > 12
    if not bool(np.any(opaque)):
        return rgba
    missing = (~opaque).astype(np.uint8)
    # OpenCV inpainting propagates nearby colour/texture into transparent
    # margins. The result is clipped later by the precise user nail mask.
    radius = max(3, int(round(min(rgba.shape[:2]) * 0.08)))
    for channel in range(3):
        rgba[:, :, channel] = cv2.inpaint(
            rgba[:, :, channel],
            missing,
            radius,
            cv2.INPAINT_TELEA,
        )
    rgba[:, :, 3] = 255
    return rgba


def _warp_texture_tps(texture_np, source_quad, target_quad, output_size: tuple[int, int]):
    """Warp with OpenCV TPS when opencv-contrib is available.

    The TPS implementation works on a full-size transparent canvas. This keeps
    coordinates in the same space as the target hand image and avoids a second
    resampling pass after the non-linear deformation.
    """
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    if not hasattr(cv2, "createThinPlateSplineShapeTransformer"):
        return None
    target_quad = np.asarray(target_quad, dtype=np.float32)
    x, y, w, h = cv2.boundingRect(target_quad.astype(np.int32))
    if w < 8 or h < 12:
        return None
    canvas_w, canvas_h = output_size
    x = max(0, min(canvas_w - 1, x))
    y = max(0, min(canvas_h - 1, y))
    w = max(1, min(canvas_w - x, w))
    h = max(1, min(canvas_h - y, h))
    resized = cv2.resize(texture_np, (w, h), interpolation=cv2.INTER_LANCZOS4)
    source_canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
    source_canvas[y : y + h, x : x + w] = resized
    source_quad_full = np.asarray(
        [
            [x, y],
            [x + w - 1, y],
            [x + w - 1, y + h - 1],
            [x, y + h - 1],
        ],
        dtype=np.float32,
    )
    source_points = _quad_control_points(source_quad_full)
    target_points = _quad_control_points(target_quad)
    try:
        matches = [cv2.DMatch(i, i, 0) for i in range(len(source_points))]
        transformer = cv2.createThinPlateSplineShapeTransformer()
        # OpenCV TPS maps the image toward the second point set when the shapes
        # are estimated as target, source in this order.
        transformer.estimateTransformation(
            target_points.reshape(1, -1, 2),
            source_points.reshape(1, -1, 2),
            matches,
        )
        warped = transformer.warpImage(source_canvas, flags=cv2.INTER_LANCZOS4)
        if warped is None or warped.shape[:2] != source_canvas.shape[:2]:
            return None
        if float(np.max(warped[:, :, 3])) <= 1.0:
            return None
        return warped
    except Exception:
        return None


def _warp_texture_curved_mesh(texture_np, target_quad, output_size: tuple[int, int]):
    """Dependency-free curved nail warp.

    This is not a mathematical TPS solver, but it provides the same production
    role for nail try-on: per-pixel non-linear mapping along the nail centerline,
    with a small width bulge so the texture follows curved nail plates better
    than a planar perspective transform.
    """
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    target_quad = np.asarray(target_quad, dtype=np.float32)
    canvas_w, canvas_h = output_size
    x, y, w, h = cv2.boundingRect(target_quad.astype(np.int32))
    if w < 8 or h < 12:
        return None
    pad = max(3, int(min(w, h) * 0.18))
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(canvas_w, x + w + pad)
    y1 = min(canvas_h, y + h + pad)
    roi_w = x1 - x0
    roi_h = y1 - y0
    if roi_w < 8 or roi_h < 12:
        return None

    top_center = (target_quad[0] + target_quad[1]) * 0.5
    bottom_center = (target_quad[2] + target_quad[3]) * 0.5
    axis = bottom_center - top_center
    axis_len = float(np.linalg.norm(axis))
    if axis_len < 8:
        return None
    unit = axis / axis_len
    normal = np.asarray([-unit[1], unit[0]], dtype=np.float32)
    top_width = max(1.0, _point_distance(target_quad[0], target_quad[1]))
    bottom_width = max(1.0, _point_distance(target_quad[3], target_quad[2]))

    ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    points_x = xs - top_center[0]
    points_y = ys - top_center[1]
    v = (points_x * unit[0] + points_y * unit[1]) / axis_len
    width_at_v = top_width * (1.0 - v) + bottom_width * v
    # Nails are convex: a mild center bulge prevents straight-sided sticker
    # distortion when the target mask is photographed at an angle.
    width_at_v *= 1.0 + 0.10 * np.sin(np.clip(v, 0.0, 1.0) * np.pi)
    lateral = (points_x * normal[0] + points_y * normal[1]) / np.maximum(width_at_v, 1.0)
    u = lateral + 0.5

    source_h, source_w = texture_np.shape[:2]
    map_x = (u * (source_w - 1)).astype(np.float32)
    map_y = (v * (source_h - 1)).astype(np.float32)
    valid = (u >= 0.0) & (u <= 1.0) & (v >= 0.0) & (v <= 1.0)
    map_x = np.where(valid, map_x, -1).astype(np.float32)
    map_y = np.where(valid, map_y, -1).astype(np.float32)
    warped_roi = cv2.remap(
        texture_np,
        map_x,
        map_y,
        interpolation=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    output = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
    output[y0:y1, x0:x1] = warped_roi
    return output


def _quad_control_points(quad):
    import numpy as np  # type: ignore

    quad = np.asarray(quad, dtype=np.float32)
    top_mid = (quad[0] + quad[1]) * 0.5
    right_mid = (quad[1] + quad[2]) * 0.5
    bottom_mid = (quad[2] + quad[3]) * 0.5
    left_mid = (quad[3] + quad[0]) * 0.5
    center = np.mean(quad, axis=0)
    return np.asarray([quad[0], quad[1], quad[2], quad[3], top_mid, right_mid, bottom_mid, left_mid, center], dtype=np.float32)


def _point_distance(a, b) -> float:
    import numpy as np  # type: ignore

    point_a = np.asarray(a, dtype=np.float32)
    point_b = np.asarray(b, dtype=np.float32)
    return float(np.linalg.norm(point_a - point_b))


def _valid_quad(quad) -> bool:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    pts = np.asarray(quad, dtype=np.float32)
    if pts.shape != (4, 2):
        return False
    edges = [_point_distance(pts[idx], pts[(idx + 1) % 4]) for idx in range(4)]
    if min(edges) < 4.0:
        return False
    area = abs(float(cv2.contourArea(pts)))
    return area >= 24.0


def _ordered_box_points(points):
    import numpy as np  # type: ignore

    pts = np.asarray(points, dtype=np.float32)
    if pts.shape != (4, 2):
        return pts
    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).reshape(-1)
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(sums)]
    ordered[2] = pts[np.argmax(sums)]
    ordered[1] = pts[np.argmin(diffs)]
    ordered[3] = pts[np.argmax(diffs)]
    return ordered


def _mask_area(mask: Image.Image) -> float:
    histogram = mask.convert("L").histogram()
    return float(sum(value * count for value, count in enumerate(histogram)) / 255.0)


def _build_boundary_ring_mask(mask: Image.Image, *, edge_width: int) -> Image.Image:
    """Return an inner edge ring without exposing skin/background to generation."""
    edge_width = max(1, int(edge_width))
    filter_size = edge_width * 2 + 1
    source = mask.convert("L")
    eroded = source.filter(ImageFilter.MinFilter(filter_size))
    ring = ImageChops.subtract(source, eroded)
    return ring.filter(ImageFilter.GaussianBlur(radius=max(0.6, edge_width * 0.12)))


def _region_area(region: NailRegion) -> float:
    if region.polygon:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore

            return abs(float(cv2.contourArea(np.asarray(region.polygon, dtype=np.float32))))
        except Exception:
            pass
    return float(region.width * region.height)


def _region_center_distance(a: NailRegion, b: NailRegion) -> float:
    import math

    return float(math.hypot(a.center_x - b.center_x, a.center_y - b.center_y))


def _center_crop_to_aspect(image: Image.Image, aspect: float) -> Image.Image:
    aspect = max(0.08, min(8.0, aspect))
    width, height = image.size
    current = width / max(height, 1)
    if abs(current - aspect) < 0.03:
        return image
    if current > aspect:
        new_width = max(1, int(height * aspect))
        left = max(0, (width - new_width) // 2)
        return image.crop((left, 0, left + new_width, height))
    new_height = max(1, int(width / aspect))
    top = max(0, (height - new_height) // 2)
    return image.crop((0, top, width, top + new_height))


def _fit_transparent_to_aspect(image: Image.Image, aspect: float) -> Image.Image:
    """Pad RGBA content to the requested aspect ratio without losing details."""
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return _center_crop_to_aspect(image, aspect)

    content = image.crop(bbox)
    content_w, content_h = content.size
    if content_w <= 0 or content_h <= 0:
        return _center_crop_to_aspect(image, aspect)

    aspect = max(0.08, min(8.0, aspect))
    current = content_w / max(content_h, 1)
    if abs(current - aspect) < 0.03:
        return content

    if current > aspect:
        canvas_w = content_w
        canvas_h = max(content_h, int(round(content_w / aspect)))
    else:
        canvas_h = content_h
        canvas_w = max(content_w, int(round(content_h * aspect)))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    left = (canvas_w - content_w) // 2
    top = (canvas_h - content_h) // 2
    canvas.alpha_composite(content, (left, top))
    return canvas


def _match_patch_lighting(color_np, hand_np, alpha):
    import numpy as np  # type: ignore

    visible = alpha > 0.12
    if not np.any(visible):
        return color_np
    hand_region = hand_np[visible]
    color_region = color_np[visible]
    hand_mean = np.mean(hand_region, axis=0)
    color_mean = np.mean(color_region, axis=0)
    hand_std = np.std(hand_region, axis=0)
    color_std = np.std(color_region, axis=0)
    scale = np.clip(hand_std / np.maximum(color_std, 1.0), 0.72, 1.32)
    # Keep the style color dominant. The hand region is used for illumination,
    # not for washing the nail art back into the original bare nail color.
    matched = (color_np - color_mean) * scale + (color_mean * 0.72 + hand_mean * 0.28)
    return np.clip(matched, 0, 255)


def _preserve_style_detail(color_np, alpha):
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return color_np

    visible = alpha > 0.08
    if not np.any(visible):
        return color_np
    blurred = cv2.GaussianBlur(color_np, (0, 0), sigmaX=0.75)
    detail = color_np - blurred
    sharpened = color_np + detail * 0.32
    return np.clip(sharpened, 0, 255)


def _repair_nail_edge(blended, original, alpha, strength: float):
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return blended

    strength = float(np.clip(strength, 0.0, 0.45))
    if strength <= 0:
        return blended
    nail_mask = (alpha > 0.035).astype(np.uint8)
    if int(nail_mask.sum()) <= 0:
        return blended
    kernel = np.ones((3, 3), dtype=np.uint8)
    outer = cv2.dilate(nail_mask, kernel, iterations=1)
    inner = cv2.erode(nail_mask, kernel, iterations=1)
    boundary = np.clip(outer - inner, 0, 1).astype(np.float32)
    boundary = cv2.GaussianBlur(boundary, (0, 0), sigmaX=1.2)
    boundary = np.clip(boundary * strength, 0.0, 0.45)[:, :, None]
    smoothed = cv2.bilateralFilter(np.clip(blended, 0, 255).astype(np.uint8), d=5, sigmaColor=28, sigmaSpace=4).astype(np.float32)
    softened = blended * (1.0 - boundary) + smoothed * boundary

    # A very narrow outside ring should borrow original skin/nail color so the
    # edge dissolves into the user's finger instead of forming a visible sticker
    # outline. Keep the ratio conservative to avoid washing out the style.
    outside = np.clip(outer - nail_mask, 0, 1).astype(np.float32)
    outside = cv2.GaussianBlur(outside, (0, 0), sigmaX=0.9)
    outside = np.clip(outside * strength * 0.42, 0.0, 0.18)[:, :, None]
    return softened * (1.0 - outside) + original * outside


def _apply_nail_surface_lighting(color_np, hand_np, alpha, target_quad):
    """Add restrained nail curvature while preserving the photographed light.

    Distance to the target boundary approximates plate curvature: the center is
    gently lifted, sidewalls and cuticle are shaded, and low-frequency lighting
    from the original nail remains visible. Values are deliberately subtle so
    detailed nail art is not washed out.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return color_np

    mask = (alpha > 0.05).astype(np.uint8)
    if int(mask.sum()) < 24:
        return color_np
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    positive = distance[mask > 0]
    distance_scale = max(1.0, float(np.percentile(positive, 95)))
    depth = np.clip(distance / distance_scale, 0.0, 1.0)

    quad = np.asarray(target_quad, dtype=np.float32)
    top_center = (quad[0] + quad[1]) * 0.5
    bottom_center = (quad[2] + quad[3]) * 0.5
    axis_vector = bottom_center - top_center
    axis_length = max(float(np.linalg.norm(axis_vector)), 1.0)
    axis = axis_vector / axis_length
    normal = np.asarray([axis[1], -axis[0]], dtype=np.float32)
    average_width = max(
        2.0,
        (_point_distance(quad[0], quad[1]) + _point_distance(quad[3], quad[2])) * 0.5,
    )

    height, width = mask.shape
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    rel_x = xs - top_center[0]
    rel_y = ys - top_center[1]
    longitudinal = (rel_x * axis[0] + rel_y * axis[1]) / axis_length
    lateral = (rel_x * normal[0] + rel_y * normal[1]) / (average_width * 0.5)

    edge_shadow = np.power(np.clip(1.0 - depth, 0.0, 1.0), 1.7) * 0.055
    side_shadow = np.power(np.clip(np.abs(lateral), 0.0, 1.0), 1.8) * 0.035
    cuticle_shadow = np.exp(-np.square((longitudinal - 0.94) / 0.085)) * 0.032
    center_lift = np.exp(-np.square(lateral / 0.42)) * 0.022

    original_luminance = (
        hand_np[:, :, 0] * 0.2126
        + hand_np[:, :, 1] * 0.7152
        + hand_np[:, :, 2] * 0.0722
    )
    local_sigma = max(1.0, average_width * 0.16)
    local_light = cv2.GaussianBlur(original_luminance, (0, 0), sigmaX=local_sigma)
    mean_light = max(1.0, float(np.mean(local_light[mask > 0])))
    photographed_light = np.clip(local_light / mean_light, 0.90, 1.10)

    shading = 1.0 - edge_shadow - side_shadow - cuticle_shadow + center_lift
    shading *= 0.72 + photographed_light * 0.28
    shading = np.where(mask > 0, np.clip(shading, 0.86, 1.07), 1.0)
    return np.clip(color_np * shading[:, :, None], 0.0, 255.0)


def _synthetic_specular_mask(size: tuple[int, int], target_quad, alpha):
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None

    width, height = size
    quad = np.asarray(target_quad, dtype=np.float32)
    center_top = (quad[0] + quad[1]) * 0.5
    center_bottom = (quad[2] + quad[3]) * 0.5
    vector = center_bottom - center_top
    length = float(np.linalg.norm(vector))
    if length < 8:
        return None
    unit = vector / length
    normal = np.asarray([-unit[1], unit[0]], dtype=np.float32)
    line_center_top = center_top + normal * 0.12 * max(_point_distance(quad[0], quad[1]), 1.0)
    line_center_bottom = center_top + vector * 0.58 + normal * 0.12 * max(_point_distance(quad[2], quad[3]), 1.0)
    thickness = max(1, int(min(_point_distance(quad[0], quad[1]), _point_distance(quad[2], quad[3])) * 0.08))
    mask = np.zeros((height, width), dtype=np.float32)
    cv2.line(mask, tuple(line_center_top.astype(int)), tuple(line_center_bottom.astype(int)), 1.0, thickness, cv2.LINE_AA)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(0.8, thickness * 0.7))
    mask *= np.clip(alpha, 0.0, 1.0)
    return np.clip(mask, 0.0, 0.6)
