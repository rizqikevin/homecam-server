"""Real MediaPipe PoseLandmarker inference smoke tests on actual image fixtures.

Fixtures provenance:
- pose.jpg: Google MediaPipe Python Pose Landmarker notebook image source
  Source: https://cdn.pixabay.com/photo/2019/03/12/20/39/girl-4051811_960_720.jpg
- cat_and_dog.jpg: Google MediaPipe object detector fixture
  Source: https://storage.googleapis.com/mediapipe-tasks/object_detector/cat_and_dog.jpg
Model: pose_landmarker_lite.task (SHA256: 59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import cv2

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.app.human_motion import HumanMotionAnalyzer, Sensitivity
from backend.app.pose_detector import PoseDetector


class TestRealImageMotionSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        cls.pose_img_path = cls.fixtures_dir / "pose.jpg"
        cls.nonhuman_img_path = cls.fixtures_dir / "cat_and_dog.jpg"
        cls.model_path = WORKSPACE_ROOT / "backend" / "models" / "pose_landmarker_lite.task"

        if not cls.pose_img_path.exists():
            raise FileNotFoundError(f"Fixture missing: {cls.pose_img_path}")
        if not cls.nonhuman_img_path.exists():
            raise FileNotFoundError(f"Fixture missing: {cls.nonhuman_img_path}")
        if not cls.model_path.exists():
            raise FileNotFoundError(f"Model missing: {cls.model_path}")

    def test_real_nonhuman_image_detects_no_persons_and_no_motion(self):
        cat_dog_img = cv2.imread(str(self.nonhuman_img_path))
        self.assertIsNotNone(cat_dog_img)

        detector = PoseDetector(self.model_path)
        analyzer = HumanMotionAnalyzer()
        try:
            observations = detector.detect(cat_dog_img, timestamp_ms=100)
            self.assertEqual(len(observations), 0)

            result = analyzer.process(observations)
            self.assertFalse(result.any_human_moving)
            self.assertEqual(result.persons_moving, ())
        finally:
            detector.close()

    def test_real_human_pose_image_inference_and_motion_tracking(self):
        pose_img = cv2.imread(str(self.pose_img_path))
        self.assertIsNotNone(pose_img)

        detector = PoseDetector(self.model_path)
        analyzer = HumanMotionAnalyzer()

        try:
            obs1 = detector.detect(pose_img, timestamp_ms=200)
            self.assertEqual(len(obs1), 1)
            self.assertEqual(len(obs1[0].landmarks), 33)
            self.assertGreater(obs1[0].landmarks[0].visibility, 0.5)

            result1 = analyzer.process(obs1)
            self.assertFalse(result1.any_human_moving)

            obs2 = detector.detect(pose_img, timestamp_ms=400)
            self.assertEqual(len(obs2), 1)

            result2 = analyzer.process(obs2)
            self.assertFalse(result2.any_human_moving)
            self.assertEqual(result2.persons_moving, (False,))

            h, w = pose_img.shape[:2]
            translate_50 = cv2.getRotationMatrix2D((w / 2, h / 2), 0, 1.0)
            translate_50[0, 2] += 50
            translate_100 = cv2.getRotationMatrix2D((w / 2, h / 2), 0, 1.0)
            translate_100[0, 2] += 100
            shifted_50 = cv2.warpAffine(pose_img, translate_50, (w, h))
            shifted_100 = cv2.warpAffine(pose_img, translate_100, (w, h))

            obs3 = detector.detect(shifted_50, timestamp_ms=600)
            result3 = analyzer.process(obs3)
            self.assertFalse(result3.any_human_moving)

            obs4 = detector.detect(shifted_100, timestamp_ms=800)
            self.assertEqual(len(obs4), 1)
            self.assertEqual(len(obs4[0].landmarks), 33)
            result4 = analyzer.process(obs4)
            self.assertTrue(result4.any_human_moving)
            self.assertEqual(result4.persons_moving, (True,))
        finally:
            detector.close()

    def test_compression_perturbation_at_high_sensitivity_is_not_motion(self):
        pose_img = cv2.imread(str(self.pose_img_path))
        self.assertIsNotNone(pose_img)
        encoded = cv2.imencode(".jpg", pose_img, [cv2.IMWRITE_JPEG_QUALITY, 95])[1]
        perturbed_img = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        self.assertIsNotNone(perturbed_img)

        detector = PoseDetector(self.model_path)
        analyzer = HumanMotionAnalyzer()
        try:
            obs1 = detector.detect(pose_img, timestamp_ms=1000)
            obs2 = detector.detect(perturbed_img, timestamp_ms=1200)
            obs3 = detector.detect(pose_img, timestamp_ms=1400)

            result1 = analyzer.process(obs1, sensitivity=Sensitivity.HIGH)
            result2 = analyzer.process(obs2, sensitivity=Sensitivity.HIGH)
            result3 = analyzer.process(obs3, sensitivity=Sensitivity.HIGH)

            self.assertFalse(result1.any_human_moving)
            self.assertFalse(result2.any_human_moving)
            self.assertFalse(result3.any_human_moving)
        finally:
            detector.close()


if __name__ == "__main__":
    unittest.main()
