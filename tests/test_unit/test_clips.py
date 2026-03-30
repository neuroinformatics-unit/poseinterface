import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from poseinterface.clips import _extract_cliplabels, extract_clip


@pytest.fixture
def video_labels():
    n_images = 10
    n_annot = 5  # per image
    return {
        "images": [{"id": i} for i in range(n_images)],
        "annotations": [
            {"image_id": i, "id": j}
            for i in range(n_images)
            for j in range(n_annot)
        ],
        "categories": [{"id": 1, "name": "mouse"}],
    }


def test_extract_cliplabels(tmp_path, video_labels):
    """Test clip json file is extracted from the video cliplabels.json file."""
    # Set up fake video path and corresponding cliplabels.json
    video_path = tmp_path / "sub-01_ses-01_cam-01.mp4"
    json_path = tmp_path / "sub-01_ses-01_cam-01_cliplabels.json"
    json_path.write_text(json.dumps(video_labels))

    # Set up a "Clips" destination directory
    clips_dir = tmp_path / "Clips"
    clips_dir.mkdir()

    # Extract labels from frame 3 to frame 6, both included
    start_frame = 3
    duration = 4
    clip_json = _extract_cliplabels(
        video_path, clips_dir, start_frame=start_frame, duration=duration
    )

    # Load results
    clip_labels = json.loads(clip_json.read_text())

    # Check image IDs in results
    selected_img_ids = list(range(start_frame, start_frame + duration))
    assert [img["id"] for img in clip_labels["images"]] == selected_img_ids

    # Check annotations are unchanged for the selected image_id
    expected_annotations = [
        ann
        for ann in video_labels["annotations"]
        if ann["image_id"] in selected_img_ids
    ]
    assert clip_labels["annotations"] == expected_annotations

    # Check categories are unchanged
    assert clip_labels["categories"] == video_labels["categories"]


@patch("poseinterface.clips.sio.save_video")
@patch("poseinterface.clips.sio.load_video")
def test_extract_clip(
    mock_load_video,
    mock_save_video,
    video_labels,
    tmp_path,
):
    """Test clip video and json are extracted from the input video."""
    # Create test input video and video cliplabels.json
    video_path = tmp_path / "sub-01_ses-01_cam-01.mp4"
    json_path = tmp_path / "sub-01_ses-01_cam-01_cliplabels.json"
    json_path.write_text(json.dumps(video_labels))

    # Mock loaded Video object and relevant attributes
    # (10 frames, matching video_labels)
    mock_video = MagicMock()
    mock_video.fps = 30
    mock_video.shape = (10, 480, 640, 3)
    mock_video.stem = "sub-01_ses-01_cam-01"

    # Make mock Video object return value for load_video
    mock_load_video.return_value = mock_video

    # Compute clip
    start_frame = 3
    duration = 4
    clip_path, clip_json = extract_clip(video_path, start_frame, duration)

    # Check save video was called
    # Note: MagicMock caches the return value of __getitem__
    # for the same arguments. So mock_video[3:7] always returns the
    # same mock object and the assertion works
    mock_save_video.assert_called_once_with(
        mock_video[start_frame : start_frame + duration],
        clip_path,
        fps=mock_video.fps,
    )

    # Check mp4 and json files exist and have expected names
    expected_stem = f"sub-01_ses-01_cam-01_start-{start_frame}_dur-{duration}"
    assert clip_path.name == f"{expected_stem}.mp4"
    assert clip_json.name == f"{expected_stem}_cliplabels.json"
    assert clip_json.exists()


@patch("poseinterface.clips.sio.save_video")
@patch("poseinterface.clips.sio.load_video")
def test_extract_clip_clamped(
    mock_load_video, mock_save_video, video_labels, caplog, tmp_path
):
    """Test clip video and json when duration is clamped."""
    # Create test input video and video cliplabels.json
    video_path = tmp_path / "sub-01_ses-01_cam-01.mp4"
    json_path = tmp_path / "sub-01_ses-01_cam-01_cliplabels.json"
    json_path.write_text(json.dumps(video_labels))

    # Mock loaded Video object and relevant attributes
    # (10 frames, matching video_labels)
    mock_video = MagicMock()
    mock_video.fps = 30
    mock_video.shape = (10, 480, 640, 3)
    mock_video.stem = "sub-01_ses-01_cam-01"

    # Make mock Video object return value for load_video
    mock_load_video.return_value = mock_video

    # Compute clip
    start_frame = 9
    duration = 4  # exceeds total video length (10 frames)
    clamped_duration = mock_video.shape[0] - start_frame

    with caplog.at_level(logging.WARNING):
        clip_path, clip_json = extract_clip(video_path, start_frame, duration)

    # Check warning
    assert f"Clamping duration to {clamped_duration} frames" in caplog.text

    # Check save video is called with clamped duration
    mock_save_video.assert_called_once_with(
        mock_video[start_frame : start_frame + clamped_duration],
        clip_path,
        fps=mock_video.fps,
    )

    # Check mp4 and json files exist and have expected names
    expected_stem = (
        f"sub-01_ses-01_cam-01_start-{start_frame}_dur-{clamped_duration}"
    )
    assert clip_path.name == f"{expected_stem}.mp4"
    assert clip_json.name == f"{expected_stem}_cliplabels.json"
    assert clip_json.exists()
