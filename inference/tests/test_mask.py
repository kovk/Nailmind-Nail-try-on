import unittest

from app.mask import NailMaskDetector, NailRegion


class NailMaskDetectorTestCase(unittest.TestCase):
    def test_landmarks_only_fill_the_missing_finger(self) -> None:
        segmented = [
            NailRegion(center_x=x, center_y=20, width=10, height=18, angle=0, source="yolo_polygon")
            for x in (30, 50, 70, 90)
        ]
        landmarks = [
            NailRegion(center_x=x, center_y=20, width=10, height=18, angle=0, source="mediapipe_fallback")
            for x in (10, 30, 50, 70, 90)
        ]

        completed = NailMaskDetector._complete_with_landmarks(segmented, landmarks)

        self.assertEqual(len(completed), 5)
        self.assertEqual([region.center_x for region in completed], [10, 30, 50, 70, 90])
        self.assertEqual(sum(region.source == "mediapipe_fallback" for region in completed), 1)

    def test_landmark_outside_frame_is_not_used_to_force_five_nails(self) -> None:
        segmented = [
            NailRegion(center_x=x, center_y=30, width=10, height=18, angle=0, source="yolo_polygon")
            for x in (30, 50, 70, 90)
        ]
        landmarks = [
            *[
                NailRegion(center_x=x, center_y=30, width=10, height=18, angle=0, source="mediapipe_fallback")
                for x in (30, 50, 70, 90)
            ],
            NailRegion(center_x=119, center_y=70, width=14, height=24, angle=0, source="mediapipe_fallback"),
        ]

        completed = NailMaskDetector._complete_with_landmarks(
            segmented,
            landmarks,
            image_size=(120, 100),
        )

        self.assertEqual(len(completed), 4)
        self.assertTrue(all(region.source == "yolo_polygon" for region in completed))


if __name__ == "__main__":
    unittest.main()
