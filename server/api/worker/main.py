import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import requests
from PIL import Image, ImageDraw

try:
    import cv2
except Exception:
    cv2 = None

try:
    import mediapipe as mp
except Exception:
    mp = None

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


API_BASE_URL = os.getenv("API_BASE_URL", "http://nailmind-api:8080").rstrip("/")
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "change-me-worker-token")
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "2"))
MODEL_DIR = Path(os.getenv("MODEL_DIR", "/models"))
YOLO_MODEL_PATH = Path(os.getenv("YOLO_MODEL_PATH", str(MODEL_DIR / "nail-seg.pt")))
LEGACY_BEST_PT_PATH = MODEL_DIR / "best.pt"
ENABLE_FALLBACK_RENDERER = os.getenv("ENABLE_FALLBACK_RENDERER", "true").lower() == "true"


@dataclass
class WorkerJob:
    id: str
    style_id: str
    style_name: str
    source_image_path: str
    result_image_key: str
    result_image_path: str
    selected_length: str
    selected_shape: str
    style_colors: List[str]


@dataclass
class NailRegion:
    finger: str
    polygon: List[Tuple[int, int]]
    box: Tuple[int, int, int, int]
    axis: Tuple[float, float]


@dataclass
class VisionResult:
    hand_box: Tuple[int, int, int, int]
    nail_regions: List[NailRegion]
    detected_traits: Dict[str, str]
    backend: str
    quality_score: float
    warnings: List[str]


class APIClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"X-Worker-Token": WORKER_TOKEN})

    def claim_job(self) -> Optional[WorkerJob]:
        response = self.session.post(f"{API_BASE_URL}/internal/try-on/jobs/claim", timeout=20)
        response.raise_for_status()
        payload = response.json()
        job_data = payload.get("job")
        if not job_data:
            return None
        return WorkerJob(
            id=job_data["id"],
            style_id=job_data["styleId"],
            style_name=job_data["styleName"],
            source_image_path=job_data["sourceImagePath"],
            result_image_key=job_data["resultImageKey"],
            result_image_path=job_data["resultImagePath"],
            selected_length=job_data["selectedLength"],
            selected_shape=job_data["selectedShape"],
            style_colors=job_data["styleColors"],
        )

    def update_progress(self, job_id: str, stage: str, progress: int) -> None:
        response = self.session.post(
            f"{API_BASE_URL}/internal/try-on/jobs/{job_id}/progress",
            json={"stage": stage, "progress": progress},
            timeout=20,
        )
        response.raise_for_status()

    def complete_job(self, job_id: str, result_image_key: str, detected_traits: Dict[str, str]) -> None:
        response = self.session.post(
            f"{API_BASE_URL}/internal/try-on/jobs/{job_id}/complete",
            json={"resultImageKey": result_image_key, "detectedTraits": detected_traits},
            timeout=20,
        )
        response.raise_for_status()

    def fail_job(self, job_id: str, code: str, message: str) -> None:
        response = self.session.post(
            f"{API_BASE_URL}/internal/try-on/jobs/{job_id}/fail",
            json={"errorCode": code, "errorMessage": message},
            timeout=20,
        )
        response.raise_for_status()


class VisionPipeline:
    def __init__(self) -> None:
        self.mp_hands = None
        if mp is not None:
            self.mp_hands = mp.solutions.hands.Hands(
                static_image_mode=True,
                max_num_hands=2,
                min_detection_confidence=0.35,
            )

        self.yolo_model = None
        self.yolo_enabled = False
        model_path = resolve_model_path()
        if YOLO is not None and model_path is not None:
            try:
                patch_ultralytics_legacy_loss()
                self.yolo_model = YOLO(str(model_path))
                self.yolo_enabled = True
                print(f"[worker] loaded YOLO model from {model_path}", flush=True)
            except Exception as exc:
                print(f"[worker] failed to load YOLO model: {exc}", flush=True)

    def detect(self, image: Image.Image, selected_length: str, selected_shape: str) -> VisionResult:
        hand_box, landmarks = self.detect_hand(image)
        warnings: List[str] = []

        if self.yolo_enabled:
            nail_regions = self.detect_nails_yolo(image, hand_box, landmarks)
            if nail_regions:
                return VisionResult(
                    hand_box=hand_box,
                    nail_regions=nail_regions,
                    detected_traits={
                        "handType": "mediapipe_yolo",
                        "nailBed": selected_length,
                        "skinTone": "estimated_warm",
                        "shape": selected_shape,
                    },
                    backend="mediapipe+yolo",
                    quality_score=0.92,
                    warnings=warnings,
                )

        if landmarks:
            nail_regions, quality_score, warnings = self.detect_nails_landmarks(
                image_size=image.size,
                landmarks=landmarks,
                selected_length=selected_length,
                selected_shape=selected_shape,
            )
            if nail_regions:
                return VisionResult(
                    hand_box=hand_box,
                    nail_regions=nail_regions,
                    detected_traits={
                        "handType": "mediapipe_landmarks",
                        "nailBed": selected_length,
                        "skinTone": "estimated_warm",
                        "shape": selected_shape,
                    },
                    backend="mediapipe_landmarks",
                    quality_score=quality_score,
                    warnings=warnings,
                )

        if not ENABLE_FALLBACK_RENDERER:
            raise RuntimeError("no YOLO model available and fallback renderer is disabled")

        raise RuntimeError("unable to locate nail regions reliably, please retake with fingers spread on a plain background")

    def detect_hand(self, image: Image.Image) -> Tuple[Tuple[int, int, int, int], Optional[List[Tuple[int, int]]]]:
        width, height = image.size
        if self.mp_hands is not None:
            rgb = np.array(image.convert("RGB"))
            result = self.mp_hands.process(rgb)
            if result.multi_hand_landmarks:
                coords = []
                for landmark in result.multi_hand_landmarks[0].landmark:
                    coords.append((int(landmark.x * width), int(landmark.y * height)))
                xs = [point[0] for point in coords]
                ys = [point[1] for point in coords]
                hand_box = (
                    max(min(xs) - 20, 0),
                    max(min(ys) - 20, 0),
                    min(max(xs) + 20, width),
                    min(max(ys) + 20, height),
                )
                return hand_box, coords
        return detect_skin_box(image), None

    def detect_nails_yolo(
        self,
        image: Image.Image,
        hand_box: Tuple[int, int, int, int],
        landmarks: Optional[List[Tuple[int, int]]],
    ) -> List[NailRegion]:
        if self.yolo_model is None:
            return []
        if cv2 is None:
            return []

        rgb = np.array(image.convert("RGB"))
        results = self.yolo_model.predict(rgb, verbose=False, conf=0.25)
        if not results:
            return []
        result = results[0]
        masks = getattr(result, "masks", None)
        if masks is None or masks.xy is None:
            return []

        finger_names = assign_finger_names(masks.xy, landmarks)
        regions: List[NailRegion] = []
        ordered_masks = sort_masks_by_centroid(masks.xy)
        for idx, polygon in enumerate(ordered_masks[:5]):
            points = [(int(x), int(y)) for x, y in polygon.tolist()]
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            box = (min(xs), min(ys), max(xs), max(ys))
            axis = estimate_axis(points, landmarks, idx)
            regions.append(
                NailRegion(
                    finger=finger_names[min(idx, len(finger_names) - 1)],
                    polygon=points,
                    box=box,
                    axis=axis,
                )
            )
        return regions

    def detect_nails_fallback(self, hand_box: Tuple[int, int, int, int], selected_length: str) -> List[NailRegion]:
        min_x, min_y, max_x, max_y = hand_box
        width = max_x - min_x
        height = max_y - min_y
        base_y = min_y + int(height * 0.14)
        nail_width = max(18, width // 9)
        gap = max(6, width // 45)
        center_x = min_x + width // 2
        length_factor = {
            "natural_short": 1.0,
            "medium_short": 1.15,
            "long": 1.4,
            "自然短甲": 1.0,
            "中短": 1.15,
            "修长": 1.4,
        }.get(selected_length, 1.0)
        nail_height = max(24, int(height * 0.16 * length_factor))

        regions: List[NailRegion] = []
        finger_names = ["thumb", "index", "middle", "ring", "pinky"]
        for idx, offset in enumerate([-2, -1, 0, 1, 2]):
            x = center_x + offset * (nail_width + gap) - nail_width // 2
            y = base_y + abs(offset) * max(2, height // 45)
            polygon = [(x, y), (x + nail_width, y), (x + nail_width, y + nail_height), (x, y + nail_height)]
            regions.append(
                NailRegion(
                    finger=finger_names[idx],
                    polygon=polygon,
                    box=(x, y, x + nail_width, y + nail_height),
                    axis=(0.0, 1.0),
                )
            )
        return regions

    def detect_nails_landmarks(
        self,
        image_size: Tuple[int, int],
        landmarks: List[Tuple[int, int]],
        selected_length: str,
        selected_shape: str,
    ) -> Tuple[List[NailRegion], float, List[str]]:
        width, height = image_size
        finger_specs = [
            ("thumb", 4, 3, 2),
            ("index", 8, 7, 6),
            ("middle", 12, 11, 10),
            ("ring", 16, 15, 14),
            ("pinky", 20, 19, 18),
        ]
        length_factor = {
            "natural_short": 0.72,
            "medium_short": 0.88,
            "long": 1.08,
            "elongated": 1.08,
            "自然短甲": 0.72,
            "中短": 0.88,
            "修长": 1.08,
        }.get(selected_length, 0.8)
        shape_factor = {
            "squoval": 1.0,
            "方圆": 1.0,
            "oval": 0.92,
            "椭圆": 0.92,
            "almond": 0.82,
            "杏仁": 0.82,
        }.get(selected_shape, 1.0)
        regions: List[NailRegion] = []
        warnings: List[str] = []
        edge_hits = 0

        for finger_name, tip_idx, dip_idx, pip_idx in finger_specs:
            tip = np.array(landmarks[tip_idx], dtype=np.float64)
            dip = np.array(landmarks[dip_idx], dtype=np.float64)
            pip = np.array(landmarks[pip_idx], dtype=np.float64)
            finger_vec = tip - pip
            finger_len = float(np.linalg.norm(finger_vec))
            if finger_len < 18:
                warnings.append(f"{finger_name}_too_short")
                continue

            axis = normalize_vector(finger_vec)
            if axis[1] > 0.45 and finger_name != "thumb":
                warnings.append(f"{finger_name}_reversed")
                continue

            width_hint = float(np.linalg.norm(tip - dip)) * 1.15 * shape_factor
            nail_width = clamp(width_hint, 20.0, width * 0.18)
            nail_height = clamp(nail_width * (1.18 * length_factor), 18.0, height * 0.14)

            center = tip - axis * (nail_height * 0.48)
            axis_tuple = (float(axis[0]), float(axis[1]))
            polygon = oriented_box_polygon(center, nail_width, nail_height, axis_tuple)
            clipped_polygon = clamp_polygon(polygon, width, height)
            xs = [point[0] for point in clipped_polygon]
            ys = [point[1] for point in clipped_polygon]

            if min(xs) <= 2 or min(ys) <= 2 or max(xs) >= width - 2 or max(ys) >= height - 2:
                edge_hits += 1

            regions.append(
                NailRegion(
                    finger=finger_name,
                    polygon=clipped_polygon,
                    box=(min(xs), min(ys), max(xs), max(ys)),
                    axis=axis_tuple,
                )
            )

        quality = len(regions) / 5.0
        if edge_hits:
            quality -= 0.08 * edge_hits
            warnings.append("fingertips_near_edge")
        if len(regions) < 4:
            warnings.append("insufficient_fingers")
        quality = clamp(quality, 0.0, 1.0)
        return regions, quality, warnings


class TryOnRenderer:
    def render(
        self,
        image: Image.Image,
        vision: VisionResult,
        colors: Sequence[str],
        style_name: str,
        selected_shape: str,
    ) -> Image.Image:
        canvas = image.convert("RGBA")
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        base_color = parse_hex(colors[0] if colors else "#f0b4be")
        secondary_color = parse_hex(colors[1] if len(colors) > 1 else "#fff5f8")
        accent_color = parse_hex(colors[2] if len(colors) > 2 else "#8c5a6e")
        is_french = "法式" in style_name
        is_cat_eye = "猫眼" in style_name

        for idx, region in enumerate(vision.nail_regions):
            tilt = axis_to_tilt(region.axis)
            draw_nail(
                draw=draw,
                polygon=region.polygon,
                box=region.box,
                base_color=base_color,
                secondary_color=secondary_color,
                accent_color=accent_color,
                tilt=tilt,
                shape=selected_shape,
                french=is_french,
                cat_eye=is_cat_eye,
            )

        return Image.alpha_composite(canvas, overlay)


class TryOnWorker:
    def __init__(self) -> None:
        self.api = APIClient()
        self.vision = VisionPipeline()
        self.renderer = TryOnRenderer()

    def run_forever(self) -> None:
        while True:
            try:
                job = self.api.claim_job()
                if not job:
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue
                self.process_job(job)
            except Exception as exc:
                print(f"[worker] loop error: {exc}", flush=True)
                time.sleep(POLL_INTERVAL_SECONDS)

    def process_job(self, job: WorkerJob) -> None:
        try:
            self.api.update_progress(job.id, "loading_image", 20)
            image = Image.open(job.source_image_path).convert("RGBA")

            self.api.update_progress(job.id, "vision_pipeline", 45)
            vision = self.vision.detect(image, job.selected_length, job.selected_shape)
            if vision.quality_score < 0.72:
                warning_text = ", ".join(vision.warnings) if vision.warnings else "low_quality_detection"
                raise RuntimeError(
                    f"hand detected but nail fit is unreliable ({warning_text}); please retake with fingers spread and plain background"
                )

            self.api.update_progress(job.id, "rendering", 75)
            rendered = self.renderer.render(
                image=image,
                vision=vision,
                colors=job.style_colors,
                style_name=job.style_name,
                selected_shape=job.selected_shape,
            )

            os.makedirs(os.path.dirname(job.result_image_path), exist_ok=True)
            rendered.save(job.result_image_path, format="PNG")

            traits = dict(vision.detected_traits)
            traits["backend"] = vision.backend
            traits["qualityScore"] = f"{vision.quality_score:.2f}"
            if vision.warnings:
                traits["warnings"] = "|".join(vision.warnings)
            self.api.complete_job(job.id, job.result_image_key, traits)
        except Exception as exc:
            self.api.fail_job(job.id, "WORKER_PIPELINE_ERROR", str(exc))


def estimate_axis(points: Sequence[Tuple[int, int]], landmarks: Optional[List[Tuple[int, int]]], index: int) -> Tuple[float, float]:
    if landmarks and len(landmarks) >= 21:
        tip_indices = [4, 8, 12, 16, 20]
        pip_indices = [3, 6, 10, 14, 18]
        tip = landmarks[tip_indices[min(index, 4)]]
        pip = landmarks[pip_indices[min(index, 4)]]
        dx = tip[0] - pip[0]
        dy = tip[1] - pip[1]
        norm = math.sqrt(dx * dx + dy * dy) or 1.0
        return dx / norm, dy / norm
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    dx = 0.0
    dy = float(max(ys) - min(ys))
    norm = math.sqrt(dx * dx + dy * dy) or 1.0
    return dx / norm, dy / norm


def patch_ultralytics_legacy_loss() -> None:
    if YOLO is None:
        return
    try:
        import torch.nn as nn
        import ultralytics.utils.loss as loss_mod
    except Exception:
        return

    def make_stub(name: str):
        class Stub(nn.Module):
            def __init__(self, *args, **kwargs):
                super().__init__()

        Stub.__name__ = name
        Stub.__qualname__ = name
        return Stub

    for name in ("BCEDiceLoss", "MultiChannelDiceLoss"):
        if not hasattr(loss_mod, name):
            setattr(loss_mod, name, make_stub(name))


def resolve_model_path() -> Optional[Path]:
    candidates = [YOLO_MODEL_PATH, LEGACY_BEST_PT_PATH]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def sort_masks_by_centroid(polygons: Sequence[np.ndarray]) -> List[np.ndarray]:
    return sorted(
        list(polygons),
        key=lambda polygon: float(np.mean(polygon[:, 0])) if len(polygon) else 0.0,
    )


def assign_finger_names(
    polygons: Sequence[np.ndarray],
    landmarks: Optional[List[Tuple[int, int]]],
) -> List[str]:
    default_names = ["thumb", "index", "middle", "ring", "pinky"]
    ordered_masks = sort_masks_by_centroid(polygons)
    if not landmarks or len(landmarks) < 21:
        return default_names[: len(ordered_masks)] or default_names

    tip_indices = [4, 8, 12, 16, 20]
    tip_names = ["thumb", "index", "middle", "ring", "pinky"]
    tips = [(tip_names[i], landmarks[tip_indices[i]]) for i in range(len(tip_indices))]
    names: List[str] = []
    used_names: set[str] = set()
    for polygon in ordered_masks[:5]:
        centroid = np.array([float(np.mean(polygon[:, 0])), float(np.mean(polygon[:, 1]))], dtype=np.float64)
        ranked = sorted(
            tips,
            key=lambda item: (item[1][0] - centroid[0]) ** 2 + (item[1][1] - centroid[1]) ** 2,
        )
        chosen = next((name for name, _ in ranked if name not in used_names), ranked[0][0])
        used_names.add(chosen)
        names.append(chosen)
    return names or default_names


def detect_skin_box(image: Image.Image) -> Tuple[int, int, int, int]:
    rgb = np.array(image.convert("RGB"))
    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)
    mask = (r > 95) & (g > 40) & (b > 20) & ((np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b])) > 15) & (np.abs(r - g) > 15) & (r > g) & (r > b)
    ys, xs = np.where(mask)
    width, height = image.size
    if len(xs) < 100:
        return 0, 0, width, height
    min_x = max(int(xs.min()) - 12, 0)
    min_y = max(int(ys.min()) - 12, 0)
    max_x = min(int(xs.max()) + 12, width)
    max_y = min(int(ys.max()) + 12, height)
    return min_x, min_y, max_x, max_y


def draw_nail(
    draw: ImageDraw.ImageDraw,
    polygon: Sequence[Tuple[int, int]],
    box: Tuple[int, int, int, int],
    base_color: Tuple[int, int, int, int],
    secondary_color: Tuple[int, int, int, int],
    accent_color: Tuple[int, int, int, int],
    tilt: float,
    shape: str,
    french: bool,
    cat_eye: bool,
) -> None:
    min_x, min_y, max_x, max_y = box
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    a = max((max_x - min_x) / 2, 1)
    b = max((max_y - min_y) / 2, 1)
    exponent = {"squoval": 3.8, "方圆": 3.8, "almond": 1.6, "杏仁": 1.6}.get(shape, 2.2)
    rad = math.radians(tilt)
    cos_v = math.cos(rad)
    sin_v = math.sin(rad)
    polygon_path = polygon if polygon else [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]

    for y in range(min_y, max_y):
        for x in range(min_x, max_x):
            if not point_in_polygon(x, y, polygon_path):
                continue
            dx = x - cx
            dy = y - cy
            rx = dx * cos_v + dy * sin_v
            ry = -dx * sin_v + dy * cos_v
            v = (abs(rx) / a) ** exponent + (abs(ry) / b) ** exponent
            if v > 1:
                continue

            color_rgba = blend(base_color, accent_color, 0.18 * (1 - abs(rx) / a))
            if french and ry < -b * 0.28:
                color_rgba = blend(secondary_color, base_color, 0.35)
            if cat_eye:
                line = abs(rx * 0.45 + ry * 0.55) / max(a, b)
                if line < 0.18:
                    color_rgba = blend(color_rgba, secondary_color, 0.55 * (1 - line / 0.18))

            alpha = int(188 + 52 * (1 - v))
            if ry > b * 0.58:
                alpha = int(alpha * 0.78)
            draw.point((x, y), fill=(color_rgba[0], color_rgba[1], color_rgba[2], alpha))


def parse_hex(value: str) -> Tuple[int, int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return 240, 180, 190, 255
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), 255


def blend(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int], t: float) -> Tuple[int, int, int, int]:
    return (
        int(a[0] * (1 - t) + b[0] * t),
        int(a[1] * (1 - t) + b[1] * t),
        int(a[2] * (1 - t) + b[2] * t),
        255,
    )


def normalize_vector(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-6:
        return np.array([0.0, -1.0], dtype=np.float64)
    return vec / norm


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def oriented_box_polygon(
    center: np.ndarray,
    width: float,
    height: float,
    axis: Tuple[float, float],
) -> List[Tuple[int, int]]:
    axis_vec = normalize_vector(np.array(axis, dtype=np.float64))
    perp = np.array([-axis_vec[1], axis_vec[0]], dtype=np.float64)
    half_w = width / 2.0
    half_h = height / 2.0
    corners = [
        center - perp * half_w - axis_vec * half_h,
        center + perp * half_w - axis_vec * half_h,
        center + perp * half_w + axis_vec * half_h,
        center - perp * half_w + axis_vec * half_h,
    ]
    return [(int(round(point[0])), int(round(point[1]))) for point in corners]


def clamp_polygon(points: Sequence[Tuple[int, int]], width: int, height: int) -> List[Tuple[int, int]]:
    return [
        (max(0, min(int(x), width - 1)), max(0, min(int(y), height - 1)))
        for x, y in points
    ]


def axis_to_tilt(axis: Tuple[float, float]) -> float:
    return math.degrees(math.atan2(axis[0], -axis[1]))


def point_in_polygon(x: int, y: int, polygon: Sequence[Tuple[int, int]]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-6) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


if __name__ == "__main__":
    print(
        f"[worker] starting with API_BASE_URL={API_BASE_URL}, YOLO_MODEL_PATH={YOLO_MODEL_PATH}, "
        f"ENABLE_FALLBACK_RENDERER={ENABLE_FALLBACK_RENDERER}",
        flush=True,
    )
    worker = TryOnWorker()
    worker.run_forever()
