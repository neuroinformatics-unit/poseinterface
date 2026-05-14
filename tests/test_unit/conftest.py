from unittest.mock import MagicMock

import pytest


@pytest.fixture
def get_mock_video():
    """Mock a Video object with n frames, matching video_labels fixture.

    The returned image size should not be square (that is, image width should
    not be equal to image height) to correctly check for inadvertent swaps
    between these two values.
    """

    def _get_mock_video(n_frames):
        # For the fixture to correctly check if image width and height
        # are mistakenly swapped in the code, the following values should
        # not be the same (i.e., the frame should not be square)
        img_height = 480
        img_width = 640

        video = MagicMock()
        video.fps = 30
        video.shape = (n_frames, img_height, img_width, 3)
        return video

    return _get_mock_video
