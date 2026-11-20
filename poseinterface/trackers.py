"""Base class for point trackers.

Concrete trackers live in ``envs/<tool>/infer.py`` and run in their own
environment. This module must not import tool-specific dependencies
(e.g. ``torch``).
"""

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np


class PointTracker(ABC):
    """Track points through a clip, starting from its start labels."""

    @abstractmethod
    def track(
        self, video: np.ndarray, queries: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Track query points through a video.

        Parameters
        ----------
        video
            Clip frames, shape ``(T, H, W, 3)``, ``uint8``.
        queries
            Points to track, shape ``(N, 3)`` as ``(t, x, y)``.

        Returns
        -------
        tracks
            Point positions, shape ``(T, N, 2)`` as ``(x, y)``.
        visibility
            Point visibility, shape ``(T, N)``, ``bool``.
        """

    def run(
        self,
        startlabels_path: Path | str,
        video_path: Path | str,
        output_path: Path | str,
    ) -> Path:
        """Track a clip and write predictions as *PoseMark* clip labels."""
        raise NotImplementedError


def startlabels_to_queries(startlabels: dict) -> np.ndarray:
    """Convert *PoseMark* start labels to ``(N, 3)`` queries."""
    raise NotImplementedError


def tracks_to_cliplabels(
    tracks: np.ndarray, visibility: np.ndarray, startlabels: dict
) -> dict:
    """Convert tracker output to a *PoseMark* clip labels dict."""
    raise NotImplementedError
