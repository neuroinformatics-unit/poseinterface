from unittest.mock import MagicMock

import pytest


@pytest.fixture
def get_mock_video():
    """Mock a Video object with n frames, matching video_labels fixture."""

    def _get_mock_video(n_frames):
        video = MagicMock()
        video.fps = 30
        video.shape = (n_frames, 480, 640, 3)
        video.stem = "sub-01_ses-01_cam-01"
        return video

    return _get_mock_video
