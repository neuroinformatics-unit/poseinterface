"""Tests for the tool-agnostic PointTracker base (main env, no torch).

A dummy tracker that returns the query positions on every frame is enough
to exercise ``run`` end to end against ``tests/data``.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from poseinterface.io import load_cliplabels
from poseinterface.trackers import PointTracker

CLIPS_DIR = (
    Path(__file__).parents[1]
    / "data/Train/SWC-plusmaze/sub-M708149_ses-20200317/Clips"
)
CLIP_STEM = "sub-M708149_ses-20200317_cam-topdown_start-1000_dur-5"
N_FRAMES, N_KEYPOINTS = 5, 8


class StaticTracker(PointTracker):
    """Return the query positions on every frame, all visible."""

    def track(self, video_path, startlabels_path):
        n_frames = len(self.load_video(video_path))
        queries = self.load_queries(startlabels_path)
        tracks = np.broadcast_to(
            queries[:, 1:], (n_frames, *queries[:, 1:].shape)
        )
        return tracks.copy(), np.ones(tracks.shape[:2], dtype=bool)


@pytest.fixture
def video_path():
    return CLIPS_DIR / f"{CLIP_STEM}.mp4"


@pytest.fixture
def cliplabels_path():
    return CLIPS_DIR / f"{CLIP_STEM}_cliplabels.json"


@pytest.fixture
def startlabels_path(tmp_path, cliplabels_path):
    """Start labels from the first frame of the clip labels.

    Keypoint 0 is unlabelled to check it stays unlabelled downstream.
    """
    clip = json.loads(cliplabels_path.read_text())
    annots = [a for a in clip["annotations"] if a["image_id"] == 0]
    annots[0]["keypoints"][2] = 0
    start = {
        "images": clip["images"][:1],
        "annotations": annots,
        "categories": clip["categories"],
    }
    path = tmp_path / f"{CLIP_STEM}_startlabels.json"
    path.write_text(json.dumps(start))
    return path


def test_load_video(video_path):
    video = PointTracker.load_video(video_path)
    assert video.shape == (N_FRAMES, 1028, 1300, 3)
    assert video.dtype == np.uint8


def test_load_queries(startlabels_path, cliplabels_path):
    queries = PointTracker.load_queries(startlabels_path)
    assert queries.shape == (N_KEYPOINTS, 3)
    np.testing.assert_array_equal(queries[:, 0], 0)
    assert np.isnan(queries[0, 1:]).all()
    expected = load_cliplabels(cliplabels_path)[0, 0, 1:]
    np.testing.assert_allclose(queries[1:, 1:], expected)


def test_write_cliplabels_roundtrip(
    tmp_path, startlabels_path, cliplabels_path
):
    truth = load_cliplabels(cliplabels_path)  # (T, 1, K, 2)
    tracks = truth.reshape(N_FRAMES, N_KEYPOINTS, 2)
    visibility = np.ones((N_FRAMES, N_KEYPOINTS), dtype=bool)
    visibility[2, 3] = False

    out = PointTracker.write_cliplabels(
        tracks, visibility, startlabels_path, tmp_path / "out"
    )

    assert out.name == f"{CLIP_STEM}_cliplabels.json"
    content = json.loads(out.read_text())
    assert [img["file_name"] for img in content["images"]] == [
        f"sub-M708149_ses-20200317_cam-topdown_frame-{1000 + t}"
        for t in range(N_FRAMES)
    ]
    flags = content["annotations"][2]["keypoints"][2::3]
    assert flags == [0, 2, 2, 1, 2, 2, 2, 2]
    back = load_cliplabels(out)
    assert np.isnan(back[:, 0, 0]).all()
    np.testing.assert_allclose(back[:, :, 1:], truth[:, :, 1:])


def test_write_cliplabels_predictions(tmp_path, startlabels_path):
    tracks = np.zeros((N_FRAMES, N_KEYPOINTS, 2))
    visibility = np.ones((N_FRAMES, N_KEYPOINTS), dtype=bool)
    visibility[2, 3] = False

    out = PointTracker.write_cliplabels(
        tracks, visibility, startlabels_path, tmp_path, format="predictions"
    )

    assert out.name == f"{CLIP_STEM}_clippredictions.json"
    content = json.loads(out.read_text())
    assert len(content) == N_FRAMES
    assert set(content[0]) == {"image_id", "category_id", "keypoints", "score"}
    assert [p["score"] for p in content] == pytest.approx([1, 1, 6 / 7, 1, 1])


def test_write_cliplabels_invalid_format(tmp_path, startlabels_path):
    with pytest.raises(ValueError, match="format must be"):
        PointTracker.write_cliplabels(
            np.zeros((1, N_KEYPOINTS, 2)),
            np.ones((1, N_KEYPOINTS)),
            startlabels_path,
            tmp_path,
            format="other",  # type: ignore[arg-type]
        )


def test_run_writes_valid_cliplabels(tmp_path, video_path, startlabels_path):
    out = StaticTracker().run(video_path, startlabels_path, tmp_path)
    tracked = load_cliplabels(out)
    start = load_cliplabels(startlabels_path)
    assert tracked.shape == (N_FRAMES, 1, N_KEYPOINTS, 2)
    np.testing.assert_allclose(tracked, np.broadcast_to(start, tracked.shape))
