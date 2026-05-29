import argparse
import json
import logging
from unittest.mock import patch

import pytest

from poseinterface.clips import (
    _extract_cliplabels,
    _uniform_start_frames,
    extract_clip,
    extract_clips,
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
    """Video path with a corresponding *_videolabels.json alongside it."""
    path = tmp_path / "sub-01_ses-01_cam-01.mp4"
    json_path = tmp_path / "sub-01_ses-01_cam-01_videolabels.json"
    json_path.write_text(json.dumps(video_labels))
    return path


def test_extract_cliplabels(tmp_path, video_path, video_labels):
    """Test clip json file is extracted from the *_videolabels.json file."""
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

    # Check image IDs in resulting "images" are local and 0-based
    assert [img["id"] for img in clip_labels["images"]] == list(
        range(duration)
    )
    # Check image IDs in "annotations" are local and 0-based
    assert set(
        annot["image_id"] for annot in clip_labels["annotations"]
    ) == set(range(duration))

    # Check annotation IDs in "annotations" start with 1
    assert [annot["id"] for annot in clip_labels["annotations"]] == list(
        range(1, len(clip_labels["annotations"]) + 1)
    )

    # Check categories are unchanged
    assert clip_labels["categories"] == video_labels["categories"]


@patch("poseinterface.clips.sio.save_video")
@patch("poseinterface.clips.sio.load_video")
def test_extract_clip(
    mock_load_video, mock_save_video, get_mock_video, video_path
):
    """Test clip video and json are extracted from the input video."""
    # Set mock_video as return value from load_video
    mock_video = get_mock_video(n_frames=10)
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
    mock_load_video, mock_save_video, get_mock_video, video_path, caplog
):
    """Test clip video and json when duration is clamped."""
    # Set mock_video as return value from load_video
    mock_video = get_mock_video(n_frames=10)
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


# ---------------------------------------------------------------------------
# _uniform_start_frames
# ---------------------------------------------------------------------------


def test_uniform_start_frames_single_clip():
    """Single clip always starts at frame 0."""
    assert _uniform_start_frames(1, 5, 20) == [0]


def test_uniform_start_frames_two_clips():
    """Two clips divide the video into two equal segments."""
    assert _uniform_start_frames(2, 5, 20) == [0, 10]


def test_uniform_start_frames_evenly_divisible():
    """Clips are evenly spaced when the step divides exactly."""
    assert _uniform_start_frames(5, 5, 25) == [0, 5, 10, 15, 20]


def test_uniform_start_frames_endpoints():
    """First start frame is 0; length equals num_clips."""
    result = _uniform_start_frames(7, 10, 100)
    assert len(result) == 7
    assert result[0] == 0


def test_uniform_start_frames_sorted():
    """Start frames are in ascending order."""
    result = _uniform_start_frames(5, 3, 30)
    assert result == sorted(result)


@pytest.mark.parametrize("num_clips", [0, -1])
def test_uniform_start_frames_invalid_num_clips(num_clips):
    """num_clips <= 0 raises ValueError."""
    with pytest.raises(ValueError, match="num_clips must be positive"):
        _uniform_start_frames(num_clips, 5, 20)


def test_uniform_start_frames_duration_exceeds_video():
    """duration longer than the video raises ValueError."""
    with pytest.raises(ValueError, match="exceeds video length"):
        _uniform_start_frames(3, 25, 20)


# ---------------------------------------------------------------------------
# extract_clips
# ---------------------------------------------------------------------------


@patch("poseinterface.clips.extract_clip")
def test_extract_clips_manual(mock_extract_clip, video_path):
    """Manual sampling calls extract_clip once per start frame."""
    start_frames = [0, 5, 10]
    duration = 3
    mock_extract_clip.return_value = (video_path, None)

    results = extract_clips(
        video_path, duration, "manual", start_frames=start_frames
    )

    assert mock_extract_clip.call_count == len(start_frames)
    for sf in start_frames:
        mock_extract_clip.assert_any_call(video_path, sf, duration)
    assert len(results) == len(start_frames)


@patch("poseinterface.clips.extract_clip")
@patch("poseinterface.clips.sio.load_video")
def test_extract_clips_uniform(
    mock_load_video, mock_extract_clip, get_mock_video, video_path
):
    """Uniform sampling distributes clips evenly across the video."""
    mock_load_video.return_value = get_mock_video(n_frames=20)
    mock_extract_clip.return_value = (video_path, None)

    # n_frames=20, num_clips=3, step=20/3≈6.67 → [0, 7, 13]
    results = extract_clips(video_path, 4, "uniform", num_clips=3)

    assert mock_extract_clip.call_count == 3
    for sf in [0, 7, 13]:
        mock_extract_clip.assert_any_call(video_path, sf, 4)
    assert len(results) == 3


@patch("poseinterface.clips.extract_clip")
def test_extract_clips_returns_extract_clip_output(
    mock_extract_clip, video_path
):
    """Return value is a list of (clip_path, clip_json) tuples."""
    sentinel = (video_path / "clip.mp4", None)
    mock_extract_clip.return_value = sentinel

    results = extract_clips(video_path, 3, "manual", start_frames=[0, 5])

    assert results == [sentinel, sentinel]


def test_extract_clips_missing_start_frames(video_path):
    """manual sampling without start_frames raises ValueError."""
    with pytest.raises(ValueError, match="start_frames"):
        extract_clips(video_path, 5, "manual")


@patch("poseinterface.clips.sio.load_video")
def test_extract_clips_missing_num_clips(
    mock_load_video, get_mock_video, video_path
):
    """uniform sampling without num_clips raises ValueError."""
    mock_load_video.return_value = get_mock_video(n_frames=20)
    with pytest.raises(ValueError, match="num_clips"):
        extract_clips(video_path, 5, "uniform")


def test_extract_clips_unknown_sampling(video_path):
    """Unrecognised sampling strategy raises ValueError."""
    with pytest.raises(ValueError, match="Unknown sampling"):
        extract_clips(video_path, 5, "bad_strategy")
