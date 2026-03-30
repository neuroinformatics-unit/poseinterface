import json
from contextlib import nullcontext as does_not_raise
from unittest.mock import MagicMock, Mock, patch

import pytest
from pytest_lazy_fixtures import lf

from poseinterface.io import (
    _EMPTY_LABELS_ERROR_MSG,
    POSEINTERFACE_FRAME_REGEXP,
    REENCODING_PARAMS,
    _check_ffmpeg,
    _extract_frame_number,
    _generate_poseinterface_filenames,
    _get_codec_pixelformat,
    _needs_reencoding,
    _pad_integers_to_same_width,
    _reencode_video,
    _update_image_ids,
    annotations_to_poseinterface,
    video_to_poseinterface,
)


@patch("poseinterface.io.coco.convert_labels")
@patch("poseinterface.io.sio.load_file")
def test_annotations_to_coco(
    mock_load_file,
    mock_convert_labels,
    tmp_path,
    test_ids,
):
    """Test that the relevant subfunctions are called."""
    # Mock return value of load_file
    mock_labels = mock_load_file.return_value
    mock_labels.labeled_frames = [1]  # non-empty

    # Mock return value of convert_labels
    mock_convert_labels.return_value = {"images": [], "annotations": []}

    # Run function to test
    input_csv = tmp_path / "input.csv"
    output_path = tmp_path / "output.json"
    result = annotations_to_poseinterface(
        input_csv,
        output_path,
        **test_ids,
    )

    # Check subfunctions are all called
    mock_load_file.assert_called_once_with(input_csv)
    mock_convert_labels.assert_called_once_with(
        mock_labels,
        image_filenames=None,
        visibility_encoding="ternary",
    )

    # Check output file path is as expected
    assert result == output_path
    assert output_path.exists()


@patch("poseinterface.io.sio.load_file")
@patch("poseinterface.io.is_dlc_file")
@pytest.mark.parametrize(
    "input_file, error_message",
    [
        ("foo.csv", "default"),
        (lf("dlc_single_index_in_project_root"), "dlc"),
        (lf("dlc_multi_index_in_project_root"), "dlc"),
    ],
)
def test_annotations_to_coco_invalid(
    mock_load_file,
    mock_is_dlc_file,
    input_file,
    error_message,
    tmp_path,
):
    # Mock return value of load_file to have empty
    # labeled frames
    mock_labels = mock_load_file.return_value
    mock_labels.labeled_frames = []  # empty

    # Check error is raised
    with pytest.raises(
        ValueError, match=_EMPTY_LABELS_ERROR_MSG[error_message]
    ):
        annotations_to_poseinterface(
            input_file,
            tmp_path / "output.json",
        )

    # Check is_dlc_file was called
    mock_is_dlc_file.assert_called_once_with(input_file)


@patch("poseinterface.io.sio.load_file")
def test_annotations_to_coco_not_single_video(
    mock_load_file,
    tmp_path,
):
    """Test that error is raised when labels object contains >1 videos."""
    # Mock return value of load_file
    mock_labels = mock_load_file.return_value
    mock_labels.labeled_frames = [1]  # there are labelled frames
    mock_labels.videos = [1, 2]  # from multiple videos

    # Check error is raised
    with pytest.raises(
        ValueError,
        match=(r"The annotations refer to multiple videos.*Please check .*"),
    ):
        annotations_to_poseinterface(
            tmp_path / "input.csv",
            tmp_path / "output.json",
        )


def test_update_image_ids():
    """Test that image ids are updated based on frame number."""
    # Define a COCO data dict with minimal info
    input_data = {
        "images": [
            {"id": 234, "file_name": "frame-00011.png"},
            {"id": 100, "file_name": "frame-00012.png"},
        ],
        "annotations": [
            {"id": 1, "image_id": 100},
            {"id": 2, "image_id": 234},
        ],
    }

    # New image IDs are derived from filename
    expected_old_to_new_image_ids = {
        img["id"]: _extract_frame_number(
            img["file_name"],
            POSEINTERFACE_FRAME_REGEXP,
        )
        for img in input_data["images"]
    }

    # Update image IDs
    data = _update_image_ids(input_data)

    # Check image IDs in list of images
    list_ids = [img["id"] for img in data["images"]]
    expected_list_ids = [
        expected_old_to_new_image_ids[img["id"]]
        for img in input_data["images"]
    ]
    assert expected_list_ids == list_ids

    # Check image IDs in list of annotations
    list_image_ids = [annot["image_id"] for annot in data["annotations"]]
    expected_list_image_ids = [
        expected_old_to_new_image_ids[annot["image_id"]]
        for annot in input_data["annotations"]
    ]
    assert expected_list_image_ids == list_image_ids


def test_update_image_ids_duplicate_ids():
    """Test that duplicate frame numbers raise ValueError."""
    data = {
        "images": [
            {"id": 1, "file_name": "frame-0005.png"},
            {"id": 2, "file_name": "frame-0005.png"},  # duplicate!
        ],
        "annotations": [],
    }

    with pytest.raises(ValueError, match="Extracted image IDs are not unique"):
        _update_image_ids(data)


@pytest.mark.parametrize(
    "filename, frame_regexp, expected_image_id",
    [
        ("img0000.png", r"img(\d*)", 0),
        ("img0234.png", r"img(0\d*)", 234),
        (
            "sub-M708149_ses-20200317_view-topdown_frame-00000.png",
            POSEINTERFACE_FRAME_REGEXP,
            0,
        ),
        ("frame-234", POSEINTERFACE_FRAME_REGEXP, 234),
        ("frame-0234", POSEINTERFACE_FRAME_REGEXP, 234),
        ("frame-0234abcd", POSEINTERFACE_FRAME_REGEXP, 234),
    ],
)
def test_extract_frame_number(filename, frame_regexp, expected_image_id):
    """Test that image id is correctly extracted from filename."""
    image_id = _extract_frame_number(filename, frame_regexp)
    assert isinstance(image_id, int)
    assert image_id == expected_image_id


@pytest.mark.parametrize(
    "filename, frame_regexp",
    [
        ("sub-M708149_ses-20200317_view-topdown_frame.png", r"frame-(0\d*)"),
        # no frame number after "frame-"
        ("frame-234", r"frame-(0\d*)"),
        # no leading zero
        ("sub-M708149_ses-20200317_view-topdown_.png", r"frame-(0\d*)"),
        # no "frame-" prefix
        ("frame-0234", r"img(0\d*)"),
        # regexp does not produce a match
    ],
)
def test_extract_frame_number_invalid(filename, frame_regexp):
    """Test that ValueError is raised when frame number cannot be extracted."""
    with pytest.raises(
        ValueError,
        match=(
            r"No frame number could be extracted from filename.*regexp pattern"
        ),
    ):
        _extract_frame_number(filename, frame_regexp)


@pytest.mark.parametrize(
    "input_file, include_file_extension, expected_json",
    [
        (lf("sleap_h5_file"), False, lf("sleap_h5_file_cliplabels_json")),
        (
            lf("dlc_multi_index_in_video_folder"),
            True,
            lf("dlc_multi_index_framelabels_json"),
        ),
    ],
)
def test_generate_poseinterface_filenames(
    input_file, include_file_extension, expected_json, test_ids
):
    generated_filenames = _generate_poseinterface_filenames(
        sio.load_file(input_file),
        **test_ids,
        include_file_extension=include_file_extension,
    )
    # Load expected filenames from labels JSON file
    with open(expected_json) as f:
        frames_data = json.load(f)
    expected_frames_filenames = [
        img["file_name"] for img in frames_data["images"]
    ]
    assert generated_filenames == expected_frames_filenames


def test_pad_integers_to_same_width():
    """Test that integers are padded to the same width with leading zeros."""
    input = [0, 1, 10, 100]
    expected = ["000", "001", "010", "100"]
    assert _pad_integers_to_same_width(input) == expected


# ---------- Video to poseinterface ----------------


@pytest.mark.parametrize(
    "video_needs_reencoding",
    [False, True],
)
@patch("poseinterface.io._reencode_video")
@patch("poseinterface.io.shutil.copy")
@patch("poseinterface.io._needs_reencoding")
@patch("poseinterface.io._check_ffmpeg")
def test_video_to_poseinterface(
    mock_check_ffmpeg,
    mock_needs_reencoding,
    mock_copy,
    mock_reencode,
    video_needs_reencoding,
    test_ids,
    tmp_path,
):
    """Test that video is copied or reencoded with correct output path."""
    # Prepare input video
    input_video = tmp_path / "raw_video.mp4"
    input_video.touch()
    output_dir = tmp_path / "output"

    # Set mock return value for _needs_reencoding
    mock_needs_reencoding.return_value = video_needs_reencoding

    # Run conversion function
    output_video_path = video_to_poseinterface(
        input_video, output_dir, **test_ids
    )

    # Check output video path
    expected = output_dir / "sub-testSub123_ses-testSes123_cam-testCam123.mp4"
    assert output_video_path == expected

    # Check ffmpeg check was called
    mock_check_ffmpeg.assert_called_once()

    # Check correct branch was taken
    if video_needs_reencoding:
        mock_reencode.assert_called_once_with(input_video, expected)
        mock_copy.assert_not_called()
    else:
        mock_copy.assert_called_once_with(input_video, expected)
        mock_reencode.assert_not_called()


@pytest.mark.parametrize(
    "ffmpeg_available, expected_exception",
    [
        (True, does_not_raise()),
        (False, pytest.raises(RuntimeError, match="ffmpeg is required")),
    ],
)
@patch("poseinterface.io._is_ffmpeg_available")
def test_check_ffmpeg(
    mock_is_ffmpeg_available,
    ffmpeg_available,
    expected_exception,
):
    """Test ffmpeg check.

    RuntimeError is raised when ffmpeg is not available,
    otherwise ffmpeg is set as the default video plugin.
    """
    # Simulate return value for _is_ffmpeg_available
    mock_is_ffmpeg_available.return_value = ffmpeg_available

    # Check error is raised if required
    with expected_exception:
        _check_ffmpeg()

    # If no error raised: check default is set to ffmpeg
    if ffmpeg_available:
        assert sio.get_default_video_plugin().lower() == "ffmpeg"


@pytest.mark.parametrize(
    "extension, codec_pixelformat, expected_needs_reencoding",
    [
        (
            ".avi",
            None,
            True,
        ),  # wrong suffix, skip encoding check
        (
            ".mp4",
            {"codec": "foo", "pixelformat": "yuv420p"},
            True,
        ),  # wrong codec
        (
            ".mp4",
            {"codec": "h264", "pixelformat": "foo"},
            True,
        ),  # wrong pixelformat
        (
            ".mp4",
            {"codec": "h264", "pixelformat": "yuv420p"},
            False,
        ),  # all good
    ],
)
@patch("poseinterface.io._get_codec_pixelformat")
def test_needs_reencoding(
    mock_get_codec_pixelformat,
    extension,
    codec_pixelformat,
    expected_needs_reencoding,
    tmp_path,
):
    """Test function that determines if video needs reencoding."""
    # Create test video with input extension
    input_video = tmp_path / f"raw_video.{extension}"
    input_video.touch()

    # Mock encoding parameters
    mock_get_codec_pixelformat.return_value = codec_pixelformat

    # Run checking function
    assert _needs_reencoding(input_video) == expected_needs_reencoding

    # Check if relevant functions are called
    if extension != ".mp4":
        mock_get_codec_pixelformat.assert_not_called()
    else:
        mock_get_codec_pixelformat.assert_called_once_with(input_video)


@patch("poseinterface.io._get_video_encoding_info")
def test_get_codec_pixelformat(mock_get_encoding_info, tmp_path):
    """Test that codec and pixel_format are correctly extracted and renamed."""
    # Mock return from sleap-io's _get_video_encoding_info
    mock_get_encoding_info.return_value = MagicMock(
        codec="h264", pixel_format="yuv420p"
    )

    # Call function
    result = _get_codec_pixelformat(tmp_path / "video.mp4")

    assert result == {"codec": "h264", "pixelformat": "yuv420p"}


@patch("poseinterface.io.sio.save_video")
@patch("poseinterface.io.sio.load_video")
def test_reencode_video(mock_load_video, mock_save_video, tmp_path):
    """Test that video is loaded and saved with correct parameters."""
    video_fps = 100

    # Set input/output paths
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"

    # Mock loaded video object
    mock_video = MagicMock(fps=video_fps)
    mock_load_video.return_value = mock_video

    # Call reencoding function
    _reencode_video(input_path, output_path)

    # Check wrapped functions are called
    mock_load_video.assert_called_once_with(input_path)
    mock_save_video.assert_called_once_with(
        mock_video,
        filename=output_path,
        fps=video_fps,
        **REENCODING_PARAMS,
    )
