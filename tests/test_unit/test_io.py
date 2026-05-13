import json
from contextlib import nullcontext
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
import sleap_io as sio
import xarray as xr
from pytest_lazy_fixtures import lf

from poseinterface.io import (
    _EMPTY_LABELS_ERROR_MSG,
    POSEINTERFACE_FRAME_REGEXP,
    REENCODING_PARAMS,
    _build_output_json_path,
    _check_ffmpeg,
    _convert_movement_ds_to_videolabels,
    _extract_frame_number,
    _generate_poseinterface_filenames,
    _get_codec_pixelformat,
    _needs_reencoding,
    _pad_integers_to_same_width,
    _reencode_video,
    _update_image_ids,
    annotations_to_poseinterface,
    predictions_to_poseinterface,
    video_to_poseinterface,
)


@pytest.fixture
def sample_movement_ds():
    """
    Build a minimal movement dataset.
    (2 frames, 2 keypoints, 1 individual)
    """
    # Initialise position array with NaN
    # shape: (time, space, keypoints, individuals)
    position_array = np.full((2, 2, 2, 1), np.nan)

    # Fill in frame 0: kpt0=(10, 30), kpt1=(20, 40)
    position_array[0, :, :, 0] = [
        [10.0, 20.0],  # x coordinates
        [30.0, 40.0],  # y coordinates
    ]

    # Fill in frame 1: kpt0=NaN, kpt1=(50, 60)
    position_array[1, :, 1, 0] = [50.0, 60.0]  # x,y

    # Build confidence array
    # shape: (time, keypoints, individuals)
    confidence_array = np.array(
        [
            [
                [0.9],  # kpt0
                [0.8],  # kpt1
            ],  # frame 0
            [
                [np.nan],  # kpt0
                [0.7],  # kpt1
            ],  # frame 1
        ],
        dtype=np.float32,
    )

    # Return dataset
    return xr.Dataset(
        {
            "position": (
                ["time", "space", "keypoints", "individuals"],
                position_array,
            ),
            "confidence": (
                ["time", "keypoints", "individuals"],
                confidence_array,
            ),
        },
        coords={
            "time": [0, 1],
            "space": ["x", "y"],
            "keypoints": ["Nose", "Tail"],
            "individuals": ["id_0"],
        },
    )


@pytest.fixture
def mock_video():
    """Mock Video object with 10 frames, matching video_labels fixture."""

    def _mock_video(n_frames):
        video = MagicMock()
        video.fps = 30
        video.shape = (n_frames, 480, 640, 3)
        video.stem = "sub-01_ses-01_cam-01"
        return video

    return _mock_video


@patch("poseinterface.io.coco.convert_labels")
@patch("poseinterface.io.sio.load_file")
@pytest.mark.parametrize(
    "format, output_filename, image_filename, expected_image_id",
    [
        (
            "frame",
            "sub-testSub123_ses-testSes123_cam-testCam123_framelabels.json",
            "sub-testSub123_ses-testSes123_cam-testCam123_frame-3.png",
            3,
        ),
        (
            "clip",
            "sub-testSub123_ses-testSes123_cam-testCam123_"
            "start-3_dur-1_cliplabels.json",
            "sub-testSub123_ses-testSes123_cam-testCam123_frame-3",
            0,
        ),
    ],
)
def test_annotations_to_poseinterface(
    mock_load_file,
    mock_convert_labels,
    format,
    output_filename,
    image_filename,
    expected_image_id,
    tmp_path,
    sub_ses_cam_ids,
):
    """Test that annotations are converted and saved to the expected location
    and with the expected content."""
    mock_labels = mock_load_file.return_value
    mock_labels.labeled_frames = [Mock(frame_idx=3)]
    mock_labels.videos = [Mock(filename="dummy.mp4")]
    mock_convert_labels.return_value = {
        "images": [
            {
                "id": 0,
                "file_name": image_filename,
            }
        ],
        "annotations": [{"id": 1, "image_id": 0}],
    }

    input_csv = tmp_path / "input.csv"
    output_path = tmp_path / output_filename
    result = annotations_to_poseinterface(
        input_csv,
        tmp_path,
        format=format,
        **sub_ses_cam_ids,
    )

    assert result == output_path
    assert output_path.exists()

    with open(output_path) as f:
        saved_data = json.load(f)

    assert saved_data == {
        "images": [
            {
                "id": expected_image_id,
                "file_name": image_filename,
            }
        ],
        "annotations": [{"id": 1, "image_id": expected_image_id}],
    }


# Decorators are applied bottom-up, so the bottom-most @patch corresponds
# to the first mock argument and the top-most to the second.
# The order here is therefore deliberately:
#   bottom: sio.load_file  -> mock_load_file  (1st arg)
#   top:    is_dlc_file    -> mock_is_dlc_file (2nd arg)
@patch("poseinterface.io.is_dlc_file")
@patch("poseinterface.io.sio.load_file")
@pytest.mark.parametrize(
    "input_file, error_message, is_dlc",
    [
        ("foo.csv", "default", False),
        (lf("dlc_single_index_in_project_root"), "dlc", True),
        (lf("dlc_multi_index_in_project_root"), "dlc", True),
    ],
)
def test_annotations_to_poseinterface_invalid(
    mock_load_file,
    mock_is_dlc_file,
    input_file,
    error_message,
    is_dlc,
    tmp_path,
    sub_ses_cam_ids,
):
    # Configure sio.load_file to return empty labeled frames
    mock_load_file.return_value.labeled_frames = []  # empty
    mock_load_file.return_value.videos = []  # empty videos
    # Control whether is_dlc_file identifies the input as a DLC file,
    # so we can verify the correct error message is raised in each case
    mock_is_dlc_file.return_value = is_dlc

    # Check error is raised
    with pytest.raises(
        ValueError, match=_EMPTY_LABELS_ERROR_MSG[error_message]
    ):
        annotations_to_poseinterface(
            input_file,
            tmp_path,
            **sub_ses_cam_ids,
        )

    # Check is_dlc_file was called
    mock_is_dlc_file.assert_called_once_with(input_file)


@patch("poseinterface.io.sio.load_file")
def test_annotations_to_poseinterface_not_single_video(
    mock_load_file,
    tmp_path,
    sub_ses_cam_ids,
):
    """Test that error is raised when labels object contains >1 videos."""
    # Mock return value of load_file
    mock_labels = mock_load_file.return_value
    mock_frame = type("MockFrame", (), {"frame_idx": 0})()
    mock_labels.labeled_frames = [mock_frame]  # there are labelled frames
    mock_labels.videos = [1, 2]  # from multiple videos

    # Check error is raised
    with pytest.raises(
        ValueError,
        match=(r"The annotations refer to multiple videos.*Please check .*"),
    ):
        annotations_to_poseinterface(
            tmp_path / "input.csv",
            tmp_path,
            **sub_ses_cam_ids,
        )


@pytest.mark.parametrize(
    "format, image_ids, frame_numbers, expected_context",
    [
        (
            "frame",
            [1000, 1001, 1004],
            [1000, 1001, 1004],
            nullcontext("sub-a_ses-b_cam-c_framelabels.json"),
        ),
        (
            "clip",
            [0, 1, 2],
            [1000, 1001, 1004],
            nullcontext("sub-a_ses-b_cam-c_start-1000_dur-3_cliplabels.json"),
        ),
        (
            "clip",
            [0, 1, 2],
            [500, 1001, 1004],
            nullcontext("sub-a_ses-b_cam-c_start-0500_dur-3_cliplabels.json"),
        ),
        (
            "clip",
            [],
            [],
            pytest.raises(ValueError, match="No images were found"),
        ),
    ],
)
def test_build_output_json_path(
    format, image_ids, frame_numbers, expected_context, tmp_path
):
    """Test output JSON filename conventions for all formats."""
    coco_data = {
        "images": [
            {
                "id": img_id,
                "file_name": f"sub-a_ses-b_cam-c_frame-{frame_num:05d}.png",
            }
            for img_id, frame_num in zip(image_ids, frame_numbers)
        ],
        "annotations": [],
    }
    with expected_context as expected_filename:
        output_path = _build_output_json_path(
            output_dir=tmp_path / "nested" / "out",
            coco_data=coco_data,
            sub_id="a",
            ses_id="b",
            cam_id="c",
            format=format,
        )

        assert output_path == tmp_path / "nested" / "out" / expected_filename
        assert output_path.parent.exists()


def test_update_image_ids_frame_format():
    """Test that frame-format IDs match session-video frame numbers."""
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

    data = _update_image_ids(input_data, format="frame")

    assert [img["id"] for img in data["images"]] == [11, 12]
    assert [a["image_id"] for a in data["annotations"]] == [12, 11]


def test_update_image_ids_clip_format():
    """Test that clip-format IDs are 0-based, sorted by frame."""
    input_data = {
        "images": [
            {"id": 5, "file_name": "frame-01002"},
            {"id": 3, "file_name": "frame-01000"},
            {"id": 4, "file_name": "frame-01001"},
        ],
        "annotations": [
            {"id": 1, "image_id": 3},
            {"id": 2, "image_id": 5},
            {"id": 3, "image_id": 4},
        ],
    }

    data = _update_image_ids(input_data, format="clip")

    # Images should be sorted by frame number with 0-based IDs
    assert [img["file_name"] for img in data["images"]] == [
        "frame-01000",
        "frame-01001",
        "frame-01002",
    ]
    assert [img["id"] for img in data["images"]] == [0, 1, 2]
    # Annotations should reference the new 0-based IDs
    assert [a["image_id"] for a in data["annotations"]] == [0, 2, 1]


@pytest.mark.parametrize("format", ["frame", "clip"])
def test_update_image_ids_duplicate_filenames(format):
    """Test that duplicate filenames raise ValueError for both formats."""
    data = {
        "images": [
            {"id": 1, "file_name": "frame-0005.png"},
            {"id": 2, "file_name": "frame-0005.png"},
        ],
        "annotations": [],
    }

    with pytest.raises(ValueError, match="Duplicate image filenames"):
        _update_image_ids(data, format=format)


def test_update_image_ids_duplicate_frame_numbers():
    """Test that distinct filenames mapping to the same frame number raise
    ValueError in frame format."""
    data = {
        "images": [
            {"id": 1, "file_name": "frame-0005.png"},
            {"id": 2, "file_name": "frame-5.png"},
        ],
        "annotations": [],
    }

    with pytest.raises(ValueError, match="Extracted image IDs are not unique"):
        _update_image_ids(data, format="frame")


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
    input_file, include_file_extension, expected_json, sub_ses_cam_ids
):
    generated_filenames = _generate_poseinterface_filenames(
        sio.load_file(input_file),
        **sub_ses_cam_ids,
        include_file_extension=include_file_extension,
    )
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
    sub_ses_cam_ids,
    tmp_path,
):
    """Test that video is copied or reencoded with correct output path."""
    input_video = tmp_path / "raw_video.mp4"
    input_video.touch()
    output_dir = tmp_path / "output"

    mock_needs_reencoding.return_value = video_needs_reencoding

    output_video_path = video_to_poseinterface(
        input_video, output_dir, **sub_ses_cam_ids
    )

    expected = output_dir / "sub-testSub123_ses-testSes123_cam-testCam123.mp4"
    assert output_video_path == expected

    mock_check_ffmpeg.assert_called_once()

    if video_needs_reencoding:
        mock_reencode.assert_called_once_with(input_video, expected)
        mock_copy.assert_not_called()
    else:
        mock_copy.assert_called_once_with(input_video, expected)
        mock_reencode.assert_not_called()


@pytest.mark.parametrize(
    "ffmpeg_available, expected_exception",
    [
        (True, nullcontext()),
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
    mock_is_ffmpeg_available.return_value = ffmpeg_available

    with expected_exception:
        _check_ffmpeg()

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
    input_video = tmp_path / f"raw_video.{extension}"
    input_video.touch()

    mock_get_codec_pixelformat.return_value = codec_pixelformat

    assert _needs_reencoding(input_video) == expected_needs_reencoding

    if extension != ".mp4":
        mock_get_codec_pixelformat.assert_not_called()
    else:
        mock_get_codec_pixelformat.assert_called_once_with(input_video)


@patch("poseinterface.io._get_video_encoding_info")
def test_get_codec_pixelformat(mock_get_encoding_info, tmp_path):
    """Test that codec and pixel_format are correctly extracted and renamed."""
    mock_get_encoding_info.return_value = MagicMock(
        codec="h264", pixel_format="yuv420p"
    )

    result = _get_codec_pixelformat(tmp_path / "video.mp4")

    assert result == {"codec": "h264", "pixelformat": "yuv420p"}


@patch("poseinterface.io.sio.save_video")
@patch("poseinterface.io.sio.load_video")
def test_reencode_video(mock_load_video, mock_save_video, tmp_path):
    """Test that video is loaded and saved with correct parameters."""
    video_fps = 100

    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"

    mock_video = MagicMock(fps=video_fps)
    mock_load_video.return_value = mock_video

    _reencode_video(input_path, output_path)

    mock_load_video.assert_called_once_with(input_path)
    mock_save_video.assert_called_once_with(
        mock_video,
        filename=output_path,
        fps=video_fps,
        **REENCODING_PARAMS,
    )


# ---------- predictions to poseinterface ----------------


@patch("poseinterface.io._convert_movement_ds_to_videolabels")
@patch("poseinterface.io.sio.load_video")
@patch("poseinterface.io.load_dataset")
@patch("poseinterface.io._guess_source_software")
def test_predictions_to_poseinterface(
    mock_guess_source_software,
    mock_load_dataset,
    mock_load_video,
    mock_convert,
    sample_movement_ds,
    mock_video,
    tmp_path,
):
    """Test that the relevant subfunctions are called."""
    # Get movement dataset and video fixtures
    ds = sample_movement_ds
    video = mock_video(n_frames=3)

    # Mock return values for supporting functions
    mock_guess_source_software.return_value = ["DeepLabCut"]
    mock_load_dataset.return_value = ds
    mock_load_video.return_value.shape = video.shape
    mock_convert.return_value = {
        "images": [],
        "annotations": [],
        "categories": [],
    }

    # Convert predictions
    result = predictions_to_poseinterface(
        predictions_path="fake.csv",
        video_path="fake.mp4",
        output_json_parent_dir=tmp_path,
        sub_id="M01",
        ses_id="20240101",
        cam_id="top",
    )

    # Check subfunctions are called
    mock_guess_source_software.assert_called_once()
    mock_load_dataset.assert_called_once()
    mock_load_video.assert_called_once()
    mock_convert.assert_called_once()

    # Check output file exists with expected name
    assert result.exists()
    assert result.name == "sub-M01_ses-20240101_cam-top_videolabels.json"


def test_convert_movement_ds_to_videolabels(
    sample_movement_ds,
    mock_video,
):
    """Test that movement dataset is converted to videolabels dict."""
    # Get movement dataset and video fixtures
    ds = sample_movement_ds
    video = mock_video(n_frames=3)
    _, img_h, img_w, _ = video.shape

    # Convert dataset to videolabels dict
    coco_data = _convert_movement_ds_to_videolabels(
        ds,
        sub_id="M01",
        ses_id="20240101",
        cam_id="top",
        img_h=img_h,
        img_w=img_w,
    )

    # Check top-level keys
    assert set(coco_data.keys()) == {"images", "annotations", "categories"}

    # Check images
    assert len(coco_data["images"]) == len(ds.time)
    for k in range(len(coco_data["images"])):
        assert coco_data["images"][k]["file_name"] == (
            f"sub-M01_ses-20240101_cam-top_frame-000{k}"
        )
        assert coco_data["images"][k]["width"] == img_w
        assert coco_data["images"][k]["height"] == img_h

    # Check categories
    assert len(coco_data["categories"]) == len(ds.individuals)
    assert (
        coco_data["categories"][0]["name"] == ds.individuals.values.tolist()[0]
    )
    assert (
        coco_data["categories"][0]["keypoints"] == ds.keypoints.values.tolist()
    )

    # Check annotations
    # 2 frames x 1 individual = 2 annotations
    assert len(coco_data["annotations"]) == len(ds.time) * len(ds.individuals)

    # Frame 0: both keypoints visible
    # kpt0=(10, 30), kpt1=(20, 40)
    annot0 = coco_data["annotations"][0]
    assert annot0["num_keypoints"] == 2
    assert annot0["keypoints"] == [
        *ds.position.isel(time=0, keypoints=0).values.squeeze().tolist(),
        2.0,
        *ds.position.isel(time=0, keypoints=1).values.squeeze().tolist(),
        2.0,
    ]
    # bbox: [xmin, ymin, width, height]
    assert annot0["bbox"] == [10.0, 30.0, 10.0, 10.0]
    assert annot0["area"] == 100.0

    # Frame 1: kpt0 is NaN, kpt1=(50, 60)
    annot1 = coco_data["annotations"][1]
    assert annot1["num_keypoints"] == 1
    assert annot1["keypoints"] == [
        0.0,
        0.0,
        0.0,
        *ds.position.isel(time=1, keypoints=1).values.squeeze().tolist(),
        2.0,
    ]
    # bbox covers only the single visible keypoint
    assert annot1["bbox"] == [50.0, 60.0, 0.0, 0.0]
    assert annot1["area"] == 0.0
