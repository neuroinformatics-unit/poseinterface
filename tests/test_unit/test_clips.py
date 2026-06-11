import argparse
import json
import logging
from unittest.mock import patch

import pytest

from poseinterface.clips import (
    _extract_cliplabels,
    _uniform_start_frames,
    _validate_clip_request,
    extract_clips,
    extract_clips_uniform,
    extract_single_clip,
    main,
    parse_args,
    wrapper,
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
def test_extract_single_clip(
    mock_load_video, mock_save_video, get_mock_video, video_path
):
    """Test clip video and json are extracted from the input video."""
    # Set mock_video as return value from load_video
    mock_video = get_mock_video(n_frames=10)
    mock_load_video.return_value = mock_video

    # Extract clip
    start_frame = 3
    duration = 4
    clip_path, clip_json = extract_single_clip(
        video_path, start_frame, duration
    )

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
def test_extract_single_clip_no_labels(
    mock_load_video, mock_save_video, get_mock_video, tmp_path
):
    """extract_single_clip returns None clip_json when no video label exist."""
    mock_load_video.return_value = get_mock_video(n_frames=10)
    video_path = tmp_path / "sub-01_ses-01_cam-01.mp4"

    _, clip_json = extract_single_clip(video_path, 0, 5)

    assert clip_json is None


@patch("poseinterface.clips.sio.save_video")
@patch("poseinterface.clips.sio.load_video")
def test_extract_single_clip_clamped(
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
        clip_path, clip_json = extract_single_clip(
            video_path, start_frame, duration
        )

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
def test_extract_single_clip_invalid(
    video_path, start_frame, duration, expected_exception, expected_message
):
    """Test extract_single_clip with invalid start_frame or duration."""
    with pytest.raises(expected_exception, match=expected_message):
        extract_single_clip(video_path, start_frame, duration)


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
# _validate_clip_request
# ---------------------------------------------------------------------------


def test_validate_clip_request_valid():
    """No exception raised for valid inputs."""
    _validate_clip_request(0, 1)
    _validate_clip_request(10, 100)


@pytest.mark.parametrize(
    "start_frame, duration, match",
    [
        (-1, 5, "start_frame must be non-negative"),
        (0, 0, "duration must be positive"),
        (0, -1, "duration must be positive"),
    ],
)
def test_validate_clip_request_invalid(start_frame, duration, match):
    """Invalid inputs raise ValueError with a descriptive message."""
    with pytest.raises(ValueError, match=match):
        _validate_clip_request(start_frame, duration)


# ---------------------------------------------------------------------------
# extract_clips
# ---------------------------------------------------------------------------


@patch("poseinterface.clips.extract_single_clip")
def test_extract_clips(mock_extract_single_clip, video_path):
    """extract_clips calls extract_single_clip once per start frame."""
    start_frames = [0, 5, 10]
    duration = 3
    mock_extract_single_clip.return_value = (video_path, None)

    results = extract_clips(video_path, duration, start_frames)

    assert mock_extract_single_clip.call_count == len(start_frames)
    for sf in start_frames:
        mock_extract_single_clip.assert_any_call(video_path, sf, duration)
    assert len(results) == len(start_frames)


@patch("poseinterface.clips.extract_single_clip")
def test_extract_clips_returns_extract_single_clip_output(
    mock_extract_single_clip, video_path
):
    """Return a list of (clip_path, clip_json) from extract_single_clip."""
    sentinel = (video_path / "clip.mp4", None)
    mock_extract_single_clip.return_value = sentinel

    results = extract_clips(video_path, 3, [0, 5])

    assert results == [sentinel, sentinel]


# ---------------------------------------------------------------------------
# extract_clips_uniform
# ---------------------------------------------------------------------------


@patch("poseinterface.clips.extract_single_clip")
@patch("poseinterface.clips.sio.load_video")
def test_extract_clips_uniform(
    mock_load_video, mock_extract_single_clip, get_mock_video, video_path
):
    """extract_clips_uniform distributes clips evenly across the video."""
    mock_load_video.return_value = get_mock_video(n_frames=20)
    mock_extract_single_clip.return_value = (video_path, None)

    # n_frames=20, num_clips=3, step=20/3≈6.67 → [0, 7, 13]
    results = extract_clips_uniform(video_path, 4, 3)

    assert mock_extract_single_clip.call_count == 3
    for sf in [0, 7, 13]:
        mock_extract_single_clip.assert_any_call(video_path, sf, 4)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


def test_parse_args_uniform():
    """Uniform strategy args are parsed with correct types."""
    args = parse_args(
        [
            "--video_path",
            "foo.mp4",
            "--duration",
            "5",
            "--sampling",
            "uniform",
            "--num_clips",
            "3",
        ]
    )
    assert args.video_path == "foo.mp4"
    assert args.duration == 5
    assert args.sampling == "uniform"
    assert args.num_clips == 3
    assert args.start_frames is None


def test_parse_args_manual():
    """Manual strategy args are parsed with correct types."""
    args = parse_args(
        [
            "--video_path",
            "foo.mp4",
            "--duration",
            "5",
            "--sampling",
            "manual",
            "--start_frames",
            "0",
            "10",
            "20",
        ]
    )
    assert args.sampling == "manual"
    assert args.start_frames == [0, 10, 20]
    assert args.num_clips is None


@pytest.mark.parametrize(
    "argv",
    [
        ["--duration", "5", "--sampling", "uniform"],  # missing --video_path
        [
            "--video_path",
            "foo.mp4",
            "--sampling",
            "uniform",
        ],  # missing --duration
        ["--video_path", "foo.mp4", "--duration", "5"],  # missing --sampling
    ],
)
def test_parse_args_missing_required(argv):
    """Missing required arguments cause SystemExit."""
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_parse_args_invalid_sampling():
    """An unrecognised sampling choice causes SystemExit."""
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--video_path",
                "foo.mp4",
                "--duration",
                "5",
                "--sampling",
                "bad_strategy",
            ]
        )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


@patch("poseinterface.clips.extract_clips_uniform")
def test_main_uniform(mock_extract_single_clips_uniform):
    """main dispatches uniform sampling to extract_clips_uniform."""
    args = argparse.Namespace(
        video_path="foo.mp4",
        duration=5,
        sampling="uniform",
        num_clips=3,
        start_frames=None,
    )
    main(args)
    mock_extract_single_clips_uniform.assert_called_once_with("foo.mp4", 5, 3)


@patch("poseinterface.clips.extract_clips")
def test_main_manual(mock_extract_single_clips):
    """main dispatches manual sampling to extract_clips."""
    args = argparse.Namespace(
        video_path="foo.mp4",
        duration=5,
        sampling="manual",
        num_clips=None,
        start_frames=[0, 10, 20],
    )
    main(args)
    mock_extract_single_clips.assert_called_once_with(
        "foo.mp4", 5, [0, 10, 20]
    )


def test_main_uniform_missing_num_clips():
    """uniform sampling without --num_clips exits with an error message."""
    args = argparse.Namespace(
        video_path="foo.mp4",
        duration=5,
        sampling="uniform",
        num_clips=None,
        start_frames=None,
    )
    with pytest.raises(SystemExit, match="num_clips"):
        main(args)


@patch(
    "poseinterface.clips.extract_clips", side_effect=ValueError("bad frame")
)
def test_main_propagates_value_error(mock_extract_single_clips):
    """ValueError raised by extract_clips is caught/re-raised as SystemExit."""
    args = argparse.Namespace(
        video_path="foo.mp4",
        duration=5,
        sampling="manual",
        num_clips=None,
        start_frames=[0, 10],
    )
    with pytest.raises(SystemExit, match="bad frame"):
        main(args)


def test_main_manual_missing_start_frames():
    """manual sampling without --start_frames exits with an error message."""
    args = argparse.Namespace(
        video_path="foo.mp4",
        duration=5,
        sampling="manual",
        num_clips=None,
        start_frames=None,
    )
    with pytest.raises(SystemExit, match="start_frames"):
        main(args)


@patch("poseinterface.clips.main")
def test_wrapper(mock_main, monkeypatch):
    """wrapper parses sys.argv and calls main with the result."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "extract-clips",
            "--video_path",
            "foo.mp4",
            "--duration",
            "5",
            "--sampling",
            "uniform",
            "--num_clips",
            "3",
        ],
    )
    wrapper()
    mock_main.assert_called_once()
    args = mock_main.call_args[0][0]
    assert args.video_path == "foo.mp4"
    assert args.duration == 5
    assert args.sampling == "uniform"
    assert args.num_clips == 3
