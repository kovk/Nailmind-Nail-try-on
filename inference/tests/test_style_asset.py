from __future__ import annotations

import unittest

import numpy as np

from inference.app.sam3_refiner import region_from_binary_mask
from inference.app.style_asset import _tps_flatten


class TpsStyleAssetTests(unittest.TestCase):
    def test_tps_preserves_source_pixels_and_transparency(self) -> None:
        height, width = 180, 120
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        source_mask = np.zeros((height, width), dtype=np.uint8)
        target_mask = np.zeros((height, width), dtype=np.uint8)

        import cv2

        cv2.ellipse(source_mask, (60, 92), (31, 72), 11, 0, 360, 255, -1)
        rgba[source_mask > 0] = (17, 93, 211, 255)
        cv2.ellipse(target_mask, (60, 90), (35, 78), 0, 0, 360, 255, -1)

        result = _tps_flatten(rgba, source_mask, target_mask)
        self.assertIsNotNone(result)
        warped, alpha, controls = result
        self.assertEqual(warped.shape, rgba.shape)
        self.assertEqual(len(controls["source"]), 10)
        self.assertGreater(int(np.count_nonzero(alpha)), 5000)
        visible = warped[alpha > 100, :3]
        self.assertGreater(len(visible), 1000)
        self.assertLess(float(np.abs(visible.astype(np.int16) - np.array([17, 93, 211])).mean()), 2.0)
        self.assertEqual(int(alpha[target_mask == 0].max(initial=0)), 0)

    def test_sam3_binary_mask_becomes_polygon_region(self) -> None:
        import cv2

        mask = np.zeros((220, 160), dtype=np.uint8)
        cv2.ellipse(mask, (82, 112), (27, 76), 13, 0, 360, 1, -1)
        region = region_from_binary_mask(mask, confidence=0.93, source="sam3_text_fingernail")
        self.assertIsNotNone(region)
        assert region is not None
        self.assertGreaterEqual(len(region.polygon), 8)
        self.assertAlmostEqual(region.confidence, 0.93)
        self.assertEqual(region.source, "sam3_text_fingernail")
        self.assertGreater(region.height, region.width)



if __name__ == "__main__":
    unittest.main()
