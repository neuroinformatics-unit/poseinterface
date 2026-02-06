from unittest.mock import patch

import pytest
from pytest_lazy_fixtures import lf

from poseinterface.io import (
    _EMPTY_LABELS_ERROR_MSG,
    _extract_frame_number,
    _update_image_ids,
    annotations_to_coco,
    update_ids,
)


@patch("poseinterface.io.update_ids")
@patch("poseinterface.io.convert_labels")
@patch("poseinterface.io.sio.load_file")
def test_annotations_to_coco(
    mock_load_file,
    mock_convert_labels,
    mock_update_ids,
    tmp_path,
):
    """Test that the relevant subfunctions are called."""
    # Mock return value of load_file
    mock_labels = mock_load_file.return_value
    mock_labels.labeled_frames = [1]  # non-empty

    # Mock return value of convert_labels
    mock_convert_labels.return_value = {"images": [], "annotations": []}

    # Mock return value of update_ids
    output_path = tmp_path / "output.json"
    mock_update_ids.return_value = output_path

    # Run function to test
    input_csv = tmp_path / "input.csv"
    result = annotations_to_coco(input_csv, output_path)

    # Check subfunctions are all called
    mock_load_file.assert_called_once_with(input_csv)
    mock_convert_labels.assert_called_once_with(
        mock_labels,
        image_filenames=None,
        visibility_encoding="ternary",
    )
    mock_update_ids.assert_called_once()

    # Check output file path is as expected
    assert result == output_path


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
    request,
):
    # Mock return value of load_file to have empty
    # labeled frames
    mock_labels = mock_load_file.return_value
    mock_labels.labeled_frames = []  # empty

    # Check error is raised
    with pytest.raises(
        ValueError, match=_EMPTY_LABELS_ERROR_MSG[error_message]
    ):
        annotations_to_coco(
            input_file,
            tmp_path / "output.json",
        )

    # Check is_dlc_file was called
    mock_is_dlc_file.assert_called_once_with(input_file)


@patch("poseinterface.io._update_image_ids")
def test_update_ids(
    mock_update_image_ids,
    tmp_path,
):
    """Test that update functions are called and a file is saved."""
    # Input data
    input_data = {}
    output_file = tmp_path / "output.json"

    # Configure the mock to return a JSON-serializable dict
    mock_update_image_ids.return_value = {"images": [], "annotations": []}

    # Call the function under test
    result = update_ids(input_data, output_file)

    # Assert each function was called with correct input
    mock_update_image_ids.assert_called_once_with(input_data)

    # Assert output file exists
    assert output_file.exists()
    assert result == output_file


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
        img["id"]: _extract_frame_number(img["file_name"])
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
    "filename, expected_image_id",
    [
        ("sub-M708149_ses-20200317_view-topdown_frame-00000.png", 0),
        ("frame-0234", 234),
        ("frame-0234abcd", 234),
    ],
)
def test_extract_frame_number(filename, expected_image_id):
    """Test that image id is correctly extracted from filename."""
    image_id = _extract_frame_number(filename)
    assert isinstance(image_id, int)
    assert image_id == expected_image_id


@pytest.mark.parametrize(
    "filename",
    [
        "sub-M708149_ses-20200317_view-topdown_frame.png",
        # no frame number after "frame-"
        "frame-234",
        # no leading zero
        "sub-M708149_ses-20200317_view-topdown_.png",
        # no "frame-" prefix
    ],
)
def test_extract_frame_number_invalid(filename):
    """Test that ValueError is raised when frame number cannot be extracted."""
    with pytest.raises(ValueError) as excinfo:
        _extract_frame_number(filename)

    assert "No frame number could be extracted from filename" in str(
        excinfo.value
    )
