import json
from contextlib import nullcontext
from unittest.mock import Mock, patch

import pytest
import sleap_io as sio
from pytest_lazy_fixtures import lf

from poseinterface.io import (
    _EMPTY_LABELS_ERROR_MSG,
    POSEINTERFACE_FRAME_REGEXP,
    _build_output_json_path,
    _extract_frame_number,
    _generate_poseinterface_filenames,
    _pad_integers_to_same_width,
    _update_image_ids,
    annotations_to_poseinterface,
)


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
            "start",
            [0, 1],
            [100, 101],
            nullcontext("sub-a_ses-b_cam-c_start-100_dur-2_startlabels.json"),
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


def test_update_image_ids_duplicate_frame_numbers():
    """Test that duplicate frame numbers raise ValueError in frame format."""
    data = {
        "images": [
            {"id": 1, "file_name": "frame-0005.png"},
            {"id": 2, "file_name": "frame-0005.png"},
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
