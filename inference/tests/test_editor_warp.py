from __future__ import annotations

import unittest

import numpy as np

from PIL import Image, ImageDraw

from inference.app.editor import (
    _apply_nail_surface_lighting,
    _build_boundary_ring_mask,
    _warp_texture_to_nail_contour,
)


class ContourWarpTests(unittest.TestCase):
    def test_texture_is_stretched_to_full_curved_nail_mask(self) -> None:
        import cv2

        texture = np.zeros((96, 48, 4), dtype=np.uint8)
        texture[:, :24] = (220, 40, 60, 255)
        texture[:, 24:] = (30, 90, 220, 255)

        mask = np.zeros((180, 140), dtype=np.uint8)
        cv2.ellipse(mask, (70, 88), (36, 72), 0, 0, 360, 255, -1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        polygon = contours[0].reshape(-1, 2).astype(np.float32)

        warped = _warp_texture_to_nail_contour(texture, polygon, 0.0, (140, 180))

        self.assertIsNotNone(warped)
        assert warped is not None
        inside = mask > 0
        self.assertGreater(float(np.mean(warped[:, :, 3][inside] > 0)), 0.99)
        self.assertEqual(int(warped[:, :, 3][~inside].max(initial=0)), 0)
        self.assertGreater(int(warped[88, 48, 0]), int(warped[88, 48, 2]))
        self.assertGreater(int(warped[88, 92, 2]), int(warped[88, 92, 0]))

    def test_surface_lighting_shapes_flat_colour_without_overwriting_it(self) -> None:
        import cv2

        alpha = np.zeros((160, 120), dtype=np.float32)
        cv2.ellipse(alpha, (60, 78), (30, 62), 0, 0, 360, 0.94, -1)
        color = np.full((160, 120, 3), (180, 100, 130), dtype=np.float32)
        hand = np.full((160, 120, 3), 145, dtype=np.float32)
        quad = np.asarray([[30, 16], [90, 16], [90, 140], [30, 140]], dtype=np.float32)

        shaded = _apply_nail_surface_lighting(color, hand, alpha, quad)

        self.assertGreater(float(shaded[78, 60].mean()), float(shaded[78, 32].mean()))
        self.assertGreater(float(shaded[78, 60, 0]), float(shaded[78, 60, 1]))
        self.assertLess(float(np.abs(shaded - color).max()), 30.0)

    def test_boundary_ring_excludes_nail_interior(self) -> None:
        mask = Image.new("L", (120, 160), 0)
        ImageDraw.Draw(mask).ellipse((30, 15, 90, 145), fill=255)

        ring = _build_boundary_ring_mask(mask, edge_width=6)

        self.assertEqual(ring.getpixel((60, 80)), 0)
        self.assertGreater(ring.getpixel((60, 15)), 0)
        self.assertGreater(ring.getpixel((30, 80)), 0)
        self.assertEqual(ring.getpixel((15, 80)), 0)


if __name__ == "__main__":
    unittest.main()
