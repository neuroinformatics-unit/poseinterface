"""Tests for the tool-agnostic PointTracker base (main env, no torch).

A dummy tracker that returns the query positions on every frame is enough
to exercise ``run`` end to end against ``tests/data``.
"""

import numpy as np

from poseinterface.trackers import PointTracker


class StaticTracker(PointTracker):
    def track(
        self, video: np.ndarray, queries: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError


def test_startlabels_to_queries(): ...


def test_tracks_to_cliplabels(): ...


def test_run_writes_valid_cliplabels(tmp_path): ...
