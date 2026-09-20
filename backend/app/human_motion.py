"""
Pure human-motion analysis from pose landmarks.

No external dependencies — works on dataclasses only.
MediaPipe adapter feeds PersonObservation; this module decides motion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

# -- Value objects ----------------------------------------------------------

BODY_LANDMARK_RANGE = range(11, 33)  # shoulders(11) through feet(32)
TORSO_INDICES = (11, 12, 23, 24)     # left/right shoulder + left/right hip
MIN_VISIBILITY = 0.5
MIN_MOVING_LANDMARKS = 2
NOISE_DEADBAND = 0.025


class Sensitivity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


SENSITIVITY_THRESHOLDS: dict[Sensitivity, float] = {
    Sensitivity.LOW: 0.05,
    Sensitivity.MEDIUM: 0.035,
    Sensitivity.HIGH: 0.025,
}


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Landmark:
    index: int
    x: float
    y: float
    visibility: float


@dataclass(frozen=True)
class PersonObservation:
    """One detected person's body landmarks in a single frame."""
    landmarks: tuple[Landmark, ...]


@dataclass(frozen=True)
class MotionResult:
    """Output of a single analysis frame."""
    any_human_moving: bool
    persons_moving: tuple[bool, ...]


# -- Pure helpers -----------------------------------------------------------

def _torso_center(landmarks: Sequence[Landmark]) -> Point | None:
    """Mean of visible torso landmarks (shoulders + hips)."""
    by_idx = {lm.index: lm for lm in landmarks}
    visible = [by_idx[i] for i in TORSO_INDICES
               if i in by_idx and by_idx[i].visibility >= MIN_VISIBILITY]
    if len(visible) < 2:
        return None
    return Point(
        x=sum(lm.x for lm in visible) / len(visible),
        y=sum(lm.y for lm in visible) / len(visible),
    )


def _body_size(landmarks: Sequence[Landmark]) -> float:
    """Approximate body size as max extent of visible body landmarks."""
    visible = [lm for lm in landmarks
               if lm.index in BODY_LANDMARK_RANGE and lm.visibility >= MIN_VISIBILITY]
    if len(visible) < 2:
        return 1.0  # fallback avoids division by zero
    xs = [lm.x for lm in visible]
    ys = [lm.y for lm in visible]
    return max(max(xs) - min(xs), max(ys) - min(ys), 0.01)


def _unique_nearest(distances: Sequence[float]) -> int | None:
    if not distances:
        return None
    nearest = min(distances)
    if sum(math.isclose(distance, nearest, abs_tol=1e-6) for distance in distances) != 1:
        return None
    return distances.index(nearest)


def _match_persons(
    prev: list[PersonObservation],
    curr: list[PersonObservation],
) -> list[tuple[int, int]]:
    """Return only mutually-nearest, body-size-bounded person matches."""
    prev_centers = [_torso_center(person.landmarks) for person in prev]
    curr_centers = [_torso_center(person.landmarks) for person in curr]
    distances: list[list[float | None]] = []

    for pc in prev_centers:
        row: list[float | None] = []
        for cc in curr_centers:
            row.append(None if pc is None or cc is None else math.hypot(pc.x - cc.x, pc.y - cc.y))
        distances.append(row)

    curr_nearest = [
        _unique_nearest([distance if distance is not None else math.inf for distance in row])
        for row in distances
    ]
    prev_nearest = [
        _unique_nearest([
            distances[pi][ci] if distances[pi][ci] is not None else math.inf
            for pi in range(len(prev))
        ])
        for ci in range(len(curr))
    ]

    pairs: list[tuple[int, int]] = []
    for pi, ci in enumerate(curr_nearest):
        if ci is None or prev_nearest[ci] != pi:
            continue
        distance = distances[pi][ci]
        if distance is None:
            continue
        bound = max(_body_size(prev[pi].landmarks), _body_size(curr[ci].landmarks))
        if distance <= bound:
            pairs.append((pi, ci))
    return pairs


def _motion_vector(
    prev: PersonObservation,
    curr: PersonObservation,
    threshold: float,
) -> Point | None:
    """Mean vector of sufficiently displaced corresponding body landmarks."""
    prev_by_idx = {lm.index: lm for lm in prev.landmarks}
    body_sz = _body_size(curr.landmarks)
    vectors: list[Point] = []

    for lm in curr.landmarks:
        prev_lm = prev_by_idx.get(lm.index)
        if lm.index not in BODY_LANDMARK_RANGE or prev_lm is None:
            continue
        if lm.visibility < MIN_VISIBILITY or prev_lm.visibility < MIN_VISIBILITY:
            continue
        dx, dy = lm.x - prev_lm.x, lm.y - prev_lm.y
        if math.hypot(dx, dy) / body_sz > threshold:
            vectors.append(Point(dx, dy))

    if len(vectors) < MIN_MOVING_LANDMARKS:
        return None
    return Point(
        sum(vector.x for vector in vectors) / len(vectors),
        sum(vector.y for vector in vectors) / len(vectors),
    )


# -- Analyzer ---------------------------------------------------------------

class HumanMotionAnalyzer:
    """Stateful frame-by-frame human motion detector.

    Feed PersonObservation lists per frame. Returns MotionResult.
    Pure Python — no native deps.
    """

    def __init__(self) -> None:
        self._prev_observations: list[PersonObservation] = []
        self._motion_streaks: dict[int, int] = {}

    def reset(self) -> None:
        self._prev_observations = []
        self._motion_streaks = {}

    def process(
        self,
        observations: Sequence[PersonObservation],
        sensitivity: Sensitivity = Sensitivity.MEDIUM,
    ) -> MotionResult:
        curr = list(observations)
        threshold = SENSITIVITY_THRESHOLDS[sensitivity]

        if not self._prev_observations or not curr:
            self.reset()
            self._prev_observations = curr
            return MotionResult(False, tuple(False for _ in curr))

        pairs = _match_persons(self._prev_observations, curr)
        moving: list[bool] = [False] * len(curr)
        next_streaks: dict[int, int] = {}

        for pi, ci in pairs:
            positive = _motion_vector(self._prev_observations[pi], curr[ci], threshold) is not None
            streak = self._motion_streaks.get(pi, 0) + 1 if positive else 0
            next_streaks[ci] = streak
            moving[ci] = streak >= 2

        self._prev_observations = curr
        self._motion_streaks = next_streaks
        persons_moving = tuple(moving)
        return MotionResult(any(persons_moving), persons_moving)
