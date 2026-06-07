from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    import mediapipe as mp

    MEDIAPIPE_AVAILABLE = True
except Exception:
    MEDIAPIPE_AVAILABLE = False
    mp = None


class TryOnEngine:
    def __init__(self) -> None:
        self.mp_hands = mp.solutions.hands if MEDIAPIPE_AVAILABLE else None

    def detect_hand_landmarks(self, image: np.ndarray) -> list[dict]:
        if not MEDIAPIPE_AVAILABLE or self.mp_hands is None:
            return self._mock_landmarks(*image.shape[:2])

        with self.mp_hands.Hands(
            static_image_mode=True,
            max_num_hands=1,
            min_detection_confidence=0.5,
        ) as hands:
            result = hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            if not result.multi_hand_landmarks:
                return []

            height, width = image.shape[:2]
            points: list[dict] = []
            for landmark in result.multi_hand_landmarks[0].landmark:
                points.append({"x": landmark.x * width, "y": landmark.y * height, "z": landmark.z})
            return points

    def _mock_landmarks(self, height: int, width: int) -> list[dict]:
        points = [
            (0.32, 0.80),
            (0.28, 0.68),
            (0.25, 0.58),
            (0.22, 0.48),
            (0.18, 0.38),
            (0.40, 0.62),
            (0.40, 0.50),
            (0.39, 0.38),
            (0.39, 0.27),
            (0.50, 0.63),
            (0.50, 0.50),
            (0.50, 0.36),
            (0.50, 0.22),
            (0.60, 0.67),
            (0.60, 0.54),
            (0.61, 0.41),
            (0.62, 0.30),
            (0.69, 0.74),
            (0.71, 0.63),
            (0.72, 0.52),
            (0.74, 0.43),
        ]
        return [{"x": x * width, "y": y * height, "z": 0.0} for x, y in points]

    def estimate_nail_regions(self, landmarks: list[dict], image_shape: tuple[int, ...], selected_length: str) -> list[dict]:
        if len(landmarks) < 21:
            return []

        length_scale = {
            "natural_short": 1.0,
            "medium_short": 1.15,
            "elongated": 1.35,
            "long": 1.35,
        }.get(selected_length, 1.0)
        finger_bases = {4: 3, 8: 6, 12: 10, 16: 14, 20: 18}
        regions: list[dict] = []
        for tip_idx, base_idx in finger_bases.items():
            tip = landmarks[tip_idx]
            base = landmarks[base_idx]
            nail_length = max(abs(tip["y"] - base["y"]) * 2.0 * length_scale, 18.0)
            nail_width = max(nail_length * 0.72, 14.0)
            cx = (tip["x"] + base["x"]) / 2
            cy = (tip["y"] + base["y"]) / 2
            regions.append(
                {
                    "center": (cx, cy),
                    "width": nail_width,
                    "height": nail_length,
                    "angle": self._calc_angle(tip, base),
                }
            )
        return regions

    def _calc_angle(self, tip: dict, base: dict) -> float:
        return float(np.degrees(np.arctan2(tip["y"] - base["y"], tip["x"] - base["x"])))

    def apply_nail_overlay(self, hand_image: np.ndarray, style_image: np.ndarray, nail_region: dict, selected_shape: str) -> np.ndarray:
        height, width = hand_image.shape[:2]
        nail_h = int(max(nail_region["height"], 1))
        nail_w = int(max(nail_region["width"], 1))
        center_x, center_y = nail_region["center"]
        if nail_h <= 0 or nail_w <= 0:
            return hand_image

        style_resized = cv2.resize(style_image, (nail_w, nail_h))
        transform = cv2.getRotationMatrix2D((nail_w / 2, nail_h / 2), nail_region["angle"] - 90, 1.0)
        style_rotated = cv2.warpAffine(style_resized, transform, (nail_w, nail_h))

        mask = np.zeros((nail_h, nail_w), dtype=np.uint8)
        axes = {
            "squoval": (nail_w // 2, nail_h // 2),
            "oval": (max(nail_w // 2 - 1, 1), nail_h // 2),
            "almond": (max(nail_w // 2 - 2, 1), max(nail_h // 2 + 1, 1)),
        }.get(selected_shape, (nail_w // 2, nail_h // 2))
        cv2.ellipse(mask, (nail_w // 2, nail_h // 2), axes, 0, 0, 360, 255, -1)
        mask = cv2.GaussianBlur(mask, (5, 5), 3)

        x1 = int(center_x - nail_w / 2)
        y1 = int(center_y - nail_h / 2)
        x2 = x1 + nail_w
        y2 = y1 + nail_h
        x1_crop, y1_crop = max(0, x1), max(0, y1)
        x2_crop, y2_crop = min(width, x2), min(height, y2)
        if x2_crop <= x1_crop or y2_crop <= y1_crop:
            return hand_image

        mask_crop = mask[max(0, -y1) : nail_h - max(0, y2 - height), max(0, -x1) : nail_w - max(0, x2 - width)]
        style_crop = style_rotated[max(0, -y1) : nail_h - max(0, y2 - height), max(0, -x1) : nail_w - max(0, x2 - width)]
        roi = hand_image[y1_crop:y2_crop, x1_crop:x2_crop].astype(np.float32)
        if mask_crop.shape[:2] != style_crop.shape[:2] or roi.shape[:2] != style_crop.shape[:2]:
            return hand_image

        alpha_mask = cv2.cvtColor(mask_crop, cv2.COLOR_GRAY2BGR) / 255.0 * 0.88
        blended = style_crop.astype(np.float32) * alpha_mask + roi * (1.0 - alpha_mask)
        hand_image[y1_crop:y2_crop, x1_crop:x2_crop] = blended.astype(np.uint8)
        return hand_image

    def process_tryon(self, hand_image_bytes: bytes, style_image_bytes: bytes, selected_length: str, selected_shape: str) -> bytes:
        hand_image = cv2.imdecode(np.frombuffer(hand_image_bytes, np.uint8), cv2.IMREAD_COLOR)
        style_image = cv2.imdecode(np.frombuffer(style_image_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
        if hand_image is None or style_image is None:
            raise ValueError("unable to decode input images")
        if style_image.ndim == 2:
            style_image = cv2.cvtColor(style_image, cv2.COLOR_GRAY2BGR)
        elif style_image.shape[2] == 4:
            style_image = cv2.cvtColor(style_image, cv2.COLOR_BGRA2BGR)

        landmarks = self.detect_hand_landmarks(hand_image)
        if not landmarks:
            raise ValueError("unable to detect hand landmarks")

        result = hand_image.copy()
        for region in self.estimate_nail_regions(landmarks, result.shape, selected_length):
            result = self.apply_nail_overlay(result, style_image, region, selected_shape)

        ok, buffer = cv2.imencode(".png", result)
        if not ok:
            raise ValueError("unable to encode output image")
        return buffer.tobytes()


tryon_engine = TryOnEngine()
