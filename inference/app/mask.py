from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import lru_cache
from io import BytesIO
import math

from PIL import Image, ImageDraw, ImageFilter, ImageOps


@lru_cache(maxsize=2)
def _load_yolo_model(model_path: str):
    from ultralytics import YOLO  # type: ignore

    return YOLO(model_path)


@dataclass(frozen=True)
class NailRegion:
    center_x: float
    center_y: float
    width: float
    height: float
    angle: float
    polygon: tuple[tuple[float, float], ...] = field(default_factory=tuple)
    confidence: float = 0.0
    source: str = "unknown"
    finger_index: int | None = None


@dataclass(frozen=True)
class SegmentedNailDetection:
    regions: list[NailRegion]
    mode: str
    yolo_candidate_count: int = 0
    sam3_candidate_count: int = 0
    refined_count: int = 0
    warning: str | None = None


def _region_fully_visible(region: NailRegion, image_size: tuple[int, int]) -> bool:
    """Reject landmark ellipses that extend beyond the photographed frame."""
    width, height = image_size
    radius = max(float(region.width), float(region.height)) * 0.55
    margin = max(2.0, min(width, height) * 0.002)
    return (
        region.center_x - radius >= margin
        and region.center_y - radius >= margin
        and region.center_x + radius <= width - margin
        and region.center_y + radius <= height - margin
    )


class NailMaskDetector:
    """Estimate visible nail regions from hand landmarks.

    MediaPipe is optional so the service can still start in slim environments.
    On GPU hosts install `requirements-gpu.txt` to enable landmark detection.
    """

    _finger_landmark_groups = (
        (4, 3, 2),  # thumb
        (8, 7, 6),  # index
        (12, 11, 10),  # middle
        (16, 15, 14),  # ring
        (20, 19, 18),  # pinky
    )

    def __init__(self, *, allow_heuristic: bool, dilate: int, blur: int) -> None:
        self.allow_heuristic = allow_heuristic
        self.dilate = max(0, dilate)
        self.blur = max(0, blur)

    def build_mask(self, image_bytes: bytes) -> Image.Image:
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
        return self.build_mask_for_image(image)

    def build_mask_for_image(self, image: Image.Image) -> Image.Image:
        regions = self.detect_regions(image)
        if not regions:
            raise RuntimeError("未检测到可用手部关键点，无法生成指甲编辑区域。")
        return self.build_mask_from_regions(image.size, regions)

    def detect_regions(self, image: Image.Image) -> list[NailRegion]:
        from .config import get_settings

        settings = get_settings()
        segmenter = settings.user_nail_segmenter.strip().lower()
        if segmenter in {"sam3", "sam3_text"}:
            try:
                regions = self._detect_with_sam3_text(image)
            except Exception:
                if not settings.user_nail_allow_yolo_fallback:
                    raise
                regions = self._detect_with_yolo(image)
        else:
            regions = self._detect_with_yolo(image)
        if 0 < len(regions) < 5:
            regions = self._complete_with_landmarks(
                regions,
                self._detect_with_mediapipe(image),
                image_size=image.size,
            )
        if not regions:
            regions = self._detect_with_mediapipe(image)
        if not regions:
            regions = self._detect_with_opencv(image)
        if not regions and self.allow_heuristic:
            regions = self._heuristic_regions(image)
        return regions

    def preload_user_segmenter(self) -> None:
        from pathlib import Path

        from .config import get_settings

        settings = get_settings()
        if settings.user_nail_segmenter.strip().lower() not in {"sam3", "sam3_text"}:
            return
        checkpoint = Path(settings.sam3_checkpoint_path)
        if not checkpoint.is_file():
            raise RuntimeError(f"SAM3_CHECKPOINT_MISSING: {checkpoint}")
        from .sam3_refiner import _load_sam3_processor

        _load_sam3_processor(str(checkpoint), settings.device)

    @staticmethod
    def _detect_with_sam3_text(image: Image.Image) -> list[NailRegion]:
        from pathlib import Path

        from .config import get_settings
        from .sam3_refiner import Sam3NailRefiner

        settings = get_settings()
        checkpoint = Path(settings.sam3_checkpoint_path)
        if not checkpoint.is_file():
            raise RuntimeError(f"SAM3_CHECKPOINT_MISSING: {checkpoint}")
        refinement = Sam3NailRefiner(
            checkpoint_path=str(checkpoint),
            device=settings.device,
            prompt=settings.sam3_prompt,
            min_score=settings.sam3_min_score,
        ).segment(image)
        return refinement.regions

    @staticmethod
    def _complete_with_landmarks(
        segmented: list[NailRegion],
        landmarks: list[NailRegion],
        expected_count: int = 5,
        image_size: tuple[int, int] | None = None,
    ) -> list[NailRegion]:
        """Use landmarks only for fingers missed by the segmentation model."""
        if not segmented or len(segmented) >= expected_count or len(landmarks) < expected_count:
            return segmented

        typical_height = sorted(region.height for region in segmented)[len(segmented) // 2]
        min_separation = max(6.0, typical_height * 0.8)
        ranked: list[tuple[float, NailRegion]] = []
        for candidate in landmarks[:expected_count]:
            if image_size and not _region_fully_visible(candidate, image_size):
                continue
            nearest = min(
                math.hypot(candidate.center_x - region.center_x, candidate.center_y - region.center_y)
                for region in segmented
            )
            if nearest >= min_separation:
                ranked.append((nearest, candidate))

        missing_count = expected_count - len(segmented)
        additions = [candidate for _, candidate in sorted(ranked, key=lambda item: item[0], reverse=True)[:missing_count]]
        return sorted([*segmented, *additions], key=lambda region: (region.center_x, region.center_y))

    def detect_segmented_regions(self, image: Image.Image) -> list[NailRegion]:
        """Return only real segmentation polygons from the configured model.

        Style-asset preprocessing must never use landmark ellipses or skin-color
        heuristics: those approximations include surrounding finger pixels and
        permanently contaminate the reusable transparent texture.
        """
        return self.detect_style_regions(image).regions

    def detect_style_regions(self, image: Image.Image) -> SegmentedNailDetection:
        from pathlib import Path

        from .config import get_settings

        settings = get_settings()
        segmenter = settings.style_asset_segmenter.strip().lower()
        if segmenter == "yolo":
            yolo_regions = [region for region in self._detect_with_yolo(image) if len(region.polygon) >= 4]
            return SegmentedNailDetection(
                regions=yolo_regions,
                mode="yolo_polygon" if yolo_regions else "yolo_no_candidates",
                yolo_candidate_count=len(yolo_regions),
            )

        checkpoint = Path(settings.sam3_checkpoint_path)
        if not checkpoint.exists():
            if settings.sam3_allow_yolo_fallback:
                return SegmentedNailDetection(
                    [],
                    "yolo_fallback",
                    warning=f"SAM3 checkpoint missing: {checkpoint}",
                )
            raise RuntimeError(f"SAM3_CHECKPOINT_MISSING: {checkpoint}")

        try:
            from .sam3_refiner import Sam3NailRefiner

            refinement = Sam3NailRefiner(
                checkpoint_path=str(checkpoint),
                device=settings.device,
                prompt=settings.sam3_prompt,
                min_score=settings.sam3_min_score,
            ).segment(image)
        except Exception as exc:
            if settings.sam3_allow_yolo_fallback:
                return SegmentedNailDetection(
                    [],
                    "yolo_fallback",
                    warning=f"SAM3 segmentation failed: {exc}",
                )
            raise RuntimeError(f"SAM3_SEGMENTATION_FAILED: {exc}") from exc

        return SegmentedNailDetection(
            regions=refinement.regions,
            mode="sam3_text_fingernail",
            sam3_candidate_count=refinement.candidate_count,
            refined_count=refinement.refined_count,
        )

    def build_mask_from_regions(self, size: tuple[int, int], regions: list[NailRegion]) -> Image.Image:
        if not regions:
            raise RuntimeError("未检测到可用手部关键点，无法生成指甲编辑区域。")
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        for region in regions:
            if region.polygon:
                draw.polygon(region.polygon, fill=255)
            else:
                self._draw_rotated_ellipse(mask, draw, region)
        if self.dilate:
            mask = mask.filter(ImageFilter.MaxFilter(self.dilate * 2 + 1))
        if self.blur:
            mask = mask.filter(ImageFilter.GaussianBlur(self.blur))
        return mask

    def _detect_with_yolo(self, image: Image.Image) -> list[NailRegion]:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore

            from .config import get_settings
        except Exception:
            return []

        settings = get_settings()
        model_path = settings.nailseg_model_path.strip()
        if not model_path:
            return []
        try:
            from pathlib import Path

            path = Path(model_path)
            if not path.exists():
                return []
            model = _load_yolo_model(str(path))
            result = model.predict(
                source=np.array(image.convert("RGB")),
                imgsz=settings.max_image_side,
                conf=0.18,
                retina_masks=True,
                verbose=False,
                device=settings.device if settings.device else None,
            )[0]
        except Exception:
            return []

        masks = getattr(result, "masks", None)
        if masks is None or getattr(masks, "xy", None) is None:
            return []

        width, height = image.size
        min_area = max(18.0, width * height * 0.000035)
        max_area = width * height * 0.03
        regions: list[NailRegion] = []
        for polygon_array in masks.xy:
            polygon_np = np.asarray(polygon_array, dtype=np.float32)
            if polygon_np.shape[0] < 4:
                continue
            area = abs(float(cv2.contourArea(polygon_np)))
            if area < min_area or area > max_area:
                continue
            rect = cv2.minAreaRect(polygon_np)
            (cx, cy), (rw, rh), angle = rect
            if rw <= 1 or rh <= 1:
                continue
            nail_width = min(float(rw), float(rh))
            nail_height = max(float(rw), float(rh))
            if nail_height / max(nail_width, 1.0) > 5.5:
                continue
            if nail_width < 4 or nail_height < 7:
                continue
            if rw > rh:
                angle += 90
            polygon = tuple((float(x), float(y)) for x, y in polygon_np)
            regions.append(
                NailRegion(
                    center_x=float(cx),
                    center_y=float(cy),
                    width=nail_width,
                    height=nail_height,
                    angle=float(angle),
                    polygon=polygon,
                    confidence=1.0,
                    source="yolo_polygon",
                )
            )
        return sorted(regions, key=lambda region: (region.center_x, region.center_y))[:10]

    def _detect_with_mediapipe(self, image: Image.Image) -> list[NailRegion]:
        try:
            import mediapipe as mp  # type: ignore
            import numpy as np  # type: ignore
        except Exception:
            return []

        mp_hands = mp.solutions.hands
        with mp_hands.Hands(static_image_mode=True, max_num_hands=2, min_detection_confidence=0.45) as hands:
            result = hands.process(np.array(image))
        if not result.multi_hand_landmarks:
            return []

        width, height = image.size
        regions: list[NailRegion] = []
        for hand in result.multi_hand_landmarks:
            points = [(lm.x * width, lm.y * height) for lm in hand.landmark]
            for finger_index, (tip_idx, dip_idx, pip_idx) in enumerate(self._finger_landmark_groups):
                tip_x, tip_y = points[tip_idx]
                dip_x, dip_y = points[dip_idx]
                pip_x, pip_y = points[pip_idx]
                vector_x = tip_x - dip_x
                vector_y = tip_y - dip_y
                length = max((vector_x**2 + vector_y**2) ** 0.5, 12.0)
                knuckle_width = max(((dip_x - pip_x) ** 2 + (dip_y - pip_y) ** 2) ** 0.5 * 0.42, 11.0)
                center_x = tip_x - vector_x * 0.25
                center_y = tip_y - vector_y * 0.25
                angle = self._angle_degrees(vector_x, vector_y)
                regions.append(
                    NailRegion(
                        center_x=center_x,
                        center_y=center_y,
                        width=knuckle_width,
                        height=length * 0.72,
                        angle=angle,
                        confidence=0.45,
                        source="mediapipe_fallback",
                        finger_index=finger_index,
                    )
                )
        return regions

    def _detect_with_opencv(self, image: Image.Image) -> list[NailRegion]:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception:
            return []

        rgb = np.array(image)
        height, width = rgb.shape[:2]
        if min(width, height) < 160:
            return []

        ycrcb = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
        lower = np.array([0, 132, 72], dtype=np.uint8)
        upper = np.array([255, 178, 132], dtype=np.uint8)
        skin = cv2.inRange(ycrcb, lower, upper)
        kernel = np.ones((5, 5), np.uint8)
        skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, kernel, iterations=1)
        skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(skin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < width * height * 0.035:
            return []

        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            return []
        centroid = np.array([moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]], dtype=np.float32)
        hull = cv2.convexHull(contour).reshape(-1, 2).astype(np.float32)
        vectors = hull - centroid
        distances = np.linalg.norm(vectors, axis=1)
        if len(distances) < 5:
            return []

        max_distance = float(distances.max())
        # Fingertips are usually convex-hull peaks far from the palm center.
        peak_points: list[tuple[float, float, float, float]] = []
        for point, vector, distance in zip(hull, vectors, distances, strict=False):
            x, y = float(point[0]), float(point[1])
            if distance < max_distance * 0.52:
                continue
            if x < width * 0.04 or x > width * 0.96 or y < height * 0.03 or y > height * 0.97:
                continue
            angle = float(np.arctan2(vector[1], vector[0]))
            peak_points.append((angle, float(distance), x, y))
        if not peak_points:
            return []

        peak_points.sort(key=lambda item: item[0])
        clusters: list[list[tuple[float, float, float, float]]] = []
        for peak in peak_points:
            if not clusters or abs(peak[0] - clusters[-1][-1][0]) > 0.22:
                clusters.append([peak])
            else:
                clusters[-1].append(peak)
        if len(clusters) > 1 and abs((clusters[0][0][0] + 6.28318530718) - clusters[-1][-1][0]) < 0.22:
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()

        candidates = [max(cluster, key=lambda item: item[1]) for cluster in clusters]
        candidates = sorted(candidates, key=lambda item: item[1], reverse=True)[:5]
        if len(candidates) < 3:
            return []

        short_side = min(width, height)
        regions: list[NailRegion] = []
        for _, distance, tip_x, tip_y in candidates:
            direction = np.array([tip_x, tip_y], dtype=np.float32) - centroid
            norm = float(np.linalg.norm(direction))
            if norm < 1:
                continue
            direction = direction / norm
            nail_height = max(short_side * 0.072, min(distance * 0.19, short_side * 0.13))
            nail_width = max(nail_height * 0.48, short_side * 0.028)
            center = np.array([tip_x, tip_y], dtype=np.float32) - direction * nail_height * 0.42
            angle = self._angle_degrees(float(direction[0]), float(direction[1]))
            regions.append(
                NailRegion(
                    center_x=float(center[0]),
                    center_y=float(center[1]),
                    width=float(nail_width),
                    height=float(nail_height),
                    angle=angle,
                )
            )
        return sorted(regions, key=lambda region: region.center_x)

    def _heuristic_regions(self, image: Image.Image) -> list[NailRegion]:
        width, height = image.size
        y = height * 0.38
        spacing = width * 0.115
        start = width * 0.27
        return [
            NailRegion(center_x=start + idx * spacing, center_y=y, width=width * 0.045, height=height * 0.09, angle=0)
            for idx in range(5)
        ]

    @staticmethod
    def _angle_degrees(vector_x: float, vector_y: float) -> float:
        import math

        return math.degrees(math.atan2(vector_y, vector_x)) + 90

    @staticmethod
    def _draw_rotated_ellipse(mask: Image.Image, draw: ImageDraw.ImageDraw, region: NailRegion) -> None:
        patch_size = int(max(region.width, region.height) * 2.4)
        patch = Image.new("L", (patch_size, patch_size), 0)
        patch_draw = ImageDraw.Draw(patch)
        cx = patch_size / 2
        cy = patch_size / 2
        patch_draw.ellipse(
            (
                cx - region.width / 2,
                cy - region.height / 2,
                cx + region.width / 2,
                cy + region.height / 2,
            ),
            fill=255,
        )
        patch = patch.rotate(region.angle, resample=Image.Resampling.BICUBIC, expand=True)
        left = int(region.center_x - patch.width / 2)
        top = int(region.center_y - patch.height / 2)
        mask.paste(patch, (left, top), patch)
