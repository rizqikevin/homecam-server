"""Tests for backend.app.human_motion — pure landmark motion analysis."""

from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "/Users/mymac/Documents/project_kevin/homecam-server")

from backend.app.human_motion import (
    HumanMotionAnalyzer,
    Landmark,
    MotionResult,
    PersonObservation,
    Sensitivity,
)


def _make_standing_person(
    x_offset: float = 0.5,
    y_offset: float = 0.5,
    vis: float = 0.9,
) -> PersonObservation:
    """Standing person with body landmarks 11-32 in a plausible grid."""
    landmarks = []
    for i in range(11, 33):
        row = (i - 11) // 2
        col = (i - 11) % 2
        landmarks.append(Landmark(
            index=i,
            x=x_offset + col * 0.05,
            y=y_offset + row * 0.04,
            visibility=vis,
        ))
    return PersonObservation(landmarks=tuple(landmarks))


def _shift_landmarks(
    obs: PersonObservation,
    indices: set[int],
    dx: float,
    dy: float,
) -> PersonObservation:
    """Return new observation with selected landmark indices shifted."""
    shifted = []
    for lm in obs.landmarks:
        if lm.index in indices:
            shifted.append(Landmark(lm.index, lm.x + dx, lm.y + dy, lm.visibility))
        else:
            shifted.append(lm)
    return PersonObservation(landmarks=tuple(shifted))


class TestFirstFrameNoMotion(unittest.TestCase):
    def test_first_frame_no_motion(self):
        """Given: fresh analyzer, one person observed.
        When: process first frame.
        Then: no motion (no prior frame to compare)."""
        analyzer = HumanMotionAnalyzer()
        obs = [_make_standing_person()]
        result = analyzer.process(obs)
        self.assertFalse(result.any_human_moving)
        self.assertEqual(result.persons_moving, (False,))


class TestStationaryPersonNoMotion(unittest.TestCase):
    def test_stationary_person_no_motion(self):
        """Given: same landmarks in frame 1 and frame 2.
        When: process frame 2.
        Then: no motion detected."""
        analyzer = HumanMotionAnalyzer()
        obs = [_make_standing_person()]
        analyzer.process(obs)  # frame 1
        result = analyzer.process(obs)  # frame 2 — identical
        self.assertFalse(result.any_human_moving)
        self.assertEqual(result.persons_moving, (False,))


class TestSingleMovingLimbInsufficient(unittest.TestCase):
    def test_single_moving_limb_insufficient(self):
        """Given: only 1 landmark (left wrist, idx 15) moves significantly.
        When: process frame 2.
        Then: not enough (need >=2 moving landmarks)."""
        analyzer = HumanMotionAnalyzer()
        person = _make_standing_person()
        analyzer.process([person])

        moved = _shift_landmarks(person, {15}, dx=0.2, dy=0.2)
        result = analyzer.process([moved])
        self.assertFalse(result.any_human_moving)


class TestTwoLandmarksMovingTriggersMotion(unittest.TestCase):
    def test_two_landmarks_moving_triggers_motion(self):
        """Given: 2 landmarks (15=left wrist, 16=right wrist) move.
        When: displacement > medium threshold normalized by body size.
        Then: motion detected."""
        analyzer = HumanMotionAnalyzer()
        person = _make_standing_person()
        analyzer.process([person])

        moved_once = _shift_landmarks(person, {15, 16}, dx=0.15, dy=0.15)
        moved_twice = _shift_landmarks(person, {15, 16}, dx=0.30, dy=0.30)

        first_positive = analyzer.process([moved_once])
        result = analyzer.process([moved_twice])

        self.assertFalse(first_positive.any_human_moving)
        self.assertTrue(result.any_human_moving)
        self.assertEqual(result.persons_moving, (True,))


class TestNonhumanEmptyNoDetection(unittest.TestCase):
    def test_nonhuman_empty_no_detection(self):
        """Given: no person detected in frame.
        When: process empty observations.
        Then: no motion."""
        analyzer = HumanMotionAnalyzer()
        result = analyzer.process([])
        self.assertFalse(result.any_human_moving)
        self.assertEqual(result.persons_moving, ())

    def test_empty_after_person_disappears(self):
        """Given: person in frame 1, nobody in frame 2.
        When: process frame 2.
        Then: no motion."""
        analyzer = HumanMotionAnalyzer()
        analyzer.process([_make_standing_person()])
        result = analyzer.process([])
        self.assertFalse(result.any_human_moving)


class TestReorderedTwoPersons(unittest.TestCase):
    def test_reordered_two_persons(self):
        """Given: two persons at different positions, order swapped in frame 2.
        When: both move arms.
        Then: both detected as moving via torso-center matching."""
        analyzer = HumanMotionAnalyzer()
        p1 = _make_standing_person(x_offset=0.2, y_offset=0.3)
        p2 = _make_standing_person(x_offset=0.7, y_offset=0.3)
        analyzer.process([p1, p2])  # frame 1

        # Frame 2: swapped order + both move wrists
        p1_moved = _shift_landmarks(p1, {15, 16}, dx=0.15, dy=0.15)
        p2_moved = _shift_landmarks(p2, {15, 16}, dx=0.15, dy=0.15)
        first_positive = analyzer.process([p2_moved, p1_moved])  # swapped
        p1_moved_twice = _shift_landmarks(p1, {15, 16}, dx=0.30, dy=0.30)
        p2_moved_twice = _shift_landmarks(p2, {15, 16}, dx=0.30, dy=0.30)
        result = analyzer.process([p2_moved_twice, p1_moved_twice])

        self.assertFalse(first_positive.any_human_moving)
        self.assertTrue(result.any_human_moving)
        self.assertTrue(all(result.persons_moving))


class TestDisappearanceReacquire(unittest.TestCase):
    def test_disappearance_reacquire(self):
        """Given: person in frame 1, gone in frame 2, back in frame 3.
        When: process frame 3 (reacquired).
        Then: no motion on reacquired frame (no prior to compare)."""
        analyzer = HumanMotionAnalyzer()
        person = _make_standing_person()
        analyzer.process([person])   # frame 1
        analyzer.process([])          # frame 2 — disappeared
        moved = _shift_landmarks(person, {15, 16}, dx=0.2, dy=0.2)
        result = analyzer.process([moved])  # frame 3 — reacquired
        self.assertFalse(result.any_human_moving)


class TestLowVisibilityLandmarksIgnored(unittest.TestCase):
    def test_low_visibility_landmarks_ignored(self):
        """Given: person with only 2 landmarks moving, but both have low visibility.
        When: process frame 2.
        Then: no motion (low-vis landmarks excluded from counting)."""
        analyzer = HumanMotionAnalyzer()
        person = _make_standing_person()
        analyzer.process([person])

        # Set visibility of wrists (15, 16) to low in frame 2
        shifted = []
        for lm in person.landmarks:
            if lm.index in {15, 16}:
                shifted.append(Landmark(lm.index, lm.x + 0.2, lm.y + 0.2, 0.1))
            else:
                shifted.append(lm)
        moved = PersonObservation(landmarks=tuple(shifted))
        result = analyzer.process([moved])
        self.assertFalse(result.any_human_moving)


class TestSensitivityLevels(unittest.TestCase):
    def test_sensitivity_levels(self):
        """Given: same displacement for 3 landmarks.
        When: tested at low, medium, high sensitivity.
        Then: high detects, medium detects, low may not (displacement below threshold)."""
        person = _make_standing_person()
        moved_once = _shift_landmarks(person, {15, 16, 17}, dx=0.008, dy=0.008)
        moved_twice = _shift_landmarks(person, {15, 16, 17}, dx=0.016, dy=0.016)

        for sensitivity, expected in [
            (Sensitivity.HIGH, True),
            (Sensitivity.MEDIUM, False),
            (Sensitivity.LOW, False),
        ]:
            analyzer = HumanMotionAnalyzer()
            analyzer.process([person])
            analyzer.process([moved_once], sensitivity=sensitivity)
            result = analyzer.process([moved_twice], sensitivity=sensitivity)
            self.assertEqual(
                result.any_human_moving,
                expected,
                f"Failed for {sensitivity}: expected {expected}, got {result.any_human_moving}",
            )

    def test_small_movement_triggers_high_but_not_medium_or_low(self):
        person = _make_standing_person()
        moved_once = _shift_landmarks(person, {15, 16, 17}, dx=0.008, dy=0.008)
        moved_twice = _shift_landmarks(person, {15, 16, 17}, dx=0.016, dy=0.016)

        results = {}
        for sensitivity in Sensitivity:
            analyzer = HumanMotionAnalyzer()
            analyzer.process([person], sensitivity=sensitivity)
            analyzer.process([moved_once], sensitivity=sensitivity)
            results[sensitivity] = analyzer.process([moved_twice], sensitivity=sensitivity)

        self.assertTrue(results[Sensitivity.HIGH].any_human_moving)
        self.assertFalse(results[Sensitivity.MEDIUM].any_human_moving)
        self.assertFalse(results[Sensitivity.LOW].any_human_moving)


class TestDegenrateTorso(unittest.TestCase):
    def test_clipping_degenerate_torso(self):
        """Given: person with only head/face landmarks visible (torso clipped).
        When: process two frames.
        Then: no crash, treated as new person each frame (no torso match)."""
        analyzer = HumanMotionAnalyzer()
        # Only landmarks 11, 12 with low vis (rest absent)
        lms = (
            Landmark(11, 0.5, 0.5, 0.3),
            Landmark(12, 0.55, 0.5, 0.3),
        )
        obs = PersonObservation(landmarks=lms)
        result1 = analyzer.process([obs])
        self.assertFalse(result1.any_human_moving)

        result2 = analyzer.process([obs])
        # Torso center None for both -> no match -> treated as new
        self.assertFalse(result2.any_human_moving)


class TestAssociationAndTemporalConfirmation(unittest.TestCase):
    def test_ambiguous_close_crossing_is_rebaselined_not_motion(self):
        analyzer = HumanMotionAnalyzer()
        left = _make_standing_person(x_offset=0.40, y_offset=0.3)
        right = _make_standing_person(x_offset=0.50, y_offset=0.3)
        analyzer.process([left, right])

        crossed_left = _make_standing_person(x_offset=0.45, y_offset=0.3)
        crossed_right = _make_standing_person(x_offset=0.45, y_offset=0.3)
        result = analyzer.process([crossed_left, crossed_right])

        self.assertFalse(result.any_human_moving)
        self.assertEqual(result.persons_moving, (False, False))

    def test_one_noisy_positive_sample_does_not_trigger_motion(self):
        analyzer = HumanMotionAnalyzer()
        person = _make_standing_person()
        analyzer.process([person], sensitivity=Sensitivity.HIGH)

        noisy = _shift_landmarks(person, {15, 16}, dx=0.03, dy=0.03)
        noisy_result = analyzer.process([noisy], sensitivity=Sensitivity.HIGH)
        stationary_result = analyzer.process([noisy], sensitivity=Sensitivity.HIGH)

        self.assertFalse(noisy_result.any_human_moving)
        self.assertFalse(stationary_result.any_human_moving)

    def test_different_people_cannot_share_confirmation_streak(self):
        analyzer = HumanMotionAnalyzer()
        first = _make_standing_person(x_offset=0.1)
        second = _make_standing_person(x_offset=0.8)
        analyzer.process([first, second])

        first_moved = _shift_landmarks(first, {15, 16}, dx=0.15, dy=0.15)
        result1 = analyzer.process([first_moved, second])
        second_moved = _shift_landmarks(second, {15, 16}, dx=0.15, dy=0.15)
        result2 = analyzer.process([first_moved, second_moved])

        self.assertFalse(result1.any_human_moving)
        self.assertFalse(result2.any_human_moving)

    def test_waving_in_opposite_directions_confirms_human_motion(self):
        analyzer = HumanMotionAnalyzer()
        person = _make_standing_person()
        analyzer.process([person])

        arms_forward = _shift_landmarks(person, {15, 16}, dx=0.20, dy=0.0)
        arms_back = _shift_landmarks(arms_forward, {15, 16}, dx=-0.20, dy=0.0)

        first_positive = analyzer.process([arms_forward])
        confirmed = analyzer.process([arms_back])

        self.assertFalse(first_positive.any_human_moving)
        self.assertTrue(confirmed.any_human_moving)
        self.assertEqual(confirmed.persons_moving, (True,))


if __name__ == "__main__":
    unittest.main()
