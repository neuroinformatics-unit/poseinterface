import argparse
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from poseinterface.clips import (
    _extract_cliplabels,
    extract_clip,
    main,
    parse_args,
)


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


@pytest.fixture
def video_path(tmp_path, video_labels):
    """Video path with a corresponding cliplabels.json alongside it."""
    path = tmp_path / "sub-01_ses-01_cam-01.mp4"
    json_path = tmp_path / "sub-01_ses-01_cam-01_cliplabels.json"
    json_path.write_text(json.dumps(video_labels))
    return path


@pytest.fixture
def mock_video():
    """Mock Video object with 10 frames, matching video_labels fixture."""
    video = MagicMock()
    video.fps = 30
    video.shape = (10, 480, 640, 3)
    video.stem = "sub-01_ses-01_cam-01"
    return video


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
    mock_load_video, mock_save_video, mock_video, video_path
):
    """Test clip video and json are extracted from the input video."""
    # Set mock_video as return value from load_video
    mock_load_video.return_value = mock_video

    # Extract clip
    start_frame = 3
    duration = 4
    clip_path, clip_json = extract_clip(video_path, start_frame, duration)

    # Check save was called with correct range
    # Note: MagicMock caches the return value of __getitem__
    # for the same arguments. So mock_video[3:7] always returns the
    # same mock object and the assertion works.
    mock_save_video.assert_called_once_with(
        mock_video[start_frame : start_frame + duration],
        clip_path,
        fps=mock_video.fps,
    )

    # Check output files
    expected_stem = f"sub-01_ses-01_cam-01_start-{start_frame}_dur-{duration}"
    assert clip_path.name == f"{expected_stem}.mp4"
    assert clip_json.name == f"{expected_stem}_cliplabels.json"
    assert clip_json.exists()


@patch("poseinterface.clips.sio.save_video")
@patch("poseinterface.clips.sio.load_video")
def test_extract_clip_clamped(
    mock_load_video, mock_save_video, mock_video, video_path, caplog
):
    """Test clip video and json when duration is clamped."""
    # Set mock_video as return value from load_video
    mock_load_video.return_value = mock_video

    # Define clipping range
    start_frame = 9
    duration = 4  # exceeds total video length (10 frames)
    clamped_duration = mock_video.shape[0] - start_frame

    # Extract clip
    with caplog.at_level(logging.WARNING):
        clip_path, clip_json = extract_clip(video_path, start_frame, duration)

    # Check warning is thrown
    assert f"Clamping duration to {clamped_duration} frames" in caplog.text

    # Check save_video is called with clamped duration
    mock_save_video.assert_called_once_with(
        mock_video[start_frame : start_frame + clamped_duration],
        clip_path,
        fps=mock_video.fps,
    )

    # Check output files reference clamped duration
    expected_stem = (
        f"sub-01_ses-01_cam-01_start-{start_frame}_dur-{clamped_duration}"
    )
    assert clip_path.name == f"{expected_stem}.mp4"
    assert clip_json.name == f"{expected_stem}_cliplabels.json"
    assert clip_json.exists()


@pytest.mark.parametrize(
    "start_frame, duration, expected_exception, expected_message",
    [
        (-3, 10, ValueError, "start_frame must be non-negative"),
        (10, -3, ValueError, "duration must be positive"),
        (10, 0, ValueError, "duration must be positive"),
    ],
)
def test_extract_clip_invalid(
    video_path, start_frame, duration, expected_exception, expected_message
):
    """Test extract_clip with invalid start_frame or duration."""
    with pytest.raises(expected_exception, match=expected_message):
        extract_clip(video_path, start_frame, duration)


def test_parse_args():
    """Check arguments are parsed with correct types"""
    video_path = "foo.mp4"
    start_frame = 5
    duration = 10
    args = parse_args(
        [
            "--video_path",
            video_path,
            "--start_frame",
            str(start_frame),
            "--duration",
            str(duration),
        ]
    )
    assert args.video_path == video_path
    assert args.start_frame == int(start_frame)
    assert args.duration == int(duration)


def test_parse_args_missing_required():
    """Test parse_args raises on missing required arguments."""
    # Call argument parsing function without --start_frame
    # and --duration
    with pytest.raises(SystemExit):
        parse_args(["--video_path", "foo.mp4"])


@patch("poseinterface.clips.extract_clip")
def test_main(mock_extract_clip):
    """Test main calls extract_clip with parsed arguments."""
    args = argparse.Namespace(
        video_path="video.mp4", start_frame=5, duration=10
    )
    main(args)
    mock_extract_clip.assert_called_once_with(
        "video.mp4", args.start_frame, args.duration
    )
