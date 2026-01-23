from unittest.mock import patch

import pytest

from poseinterface.io import (
    _extract_image_id_from_filename,
    _update_annotation_ids,
    _update_category_ids,
    _update_image_ids,
    update_ids,
)


@pytest.mark.parametrize(
    "filename, expected_image_id",
    [
        ("sub-M708149_ses-20200317_view-topdown_frame-00000.png", 0),
        ("frame-0234", 234),
        ("frame-0234abcd", 234),
    ],
)
def test_extract_image_id_from_filename(filename, expected_image_id):
    """Test that image id is correctly extracted from filename."""
    image_id = _extract_image_id_from_filename(filename)
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
def test_extract_image_id_from_filename_invalid(filename):
    """Test that ValueError is raised when frame number cannot be extracted."""
    with pytest.raises(ValueError) as excinfo:
        _extract_image_id_from_filename(filename)

    assert "No frame number could be extracted from filename" in str(
        excinfo.value
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
        img["id"]: _extract_image_id_from_filename(img["file_name"])
        for img in input_data["images"]
    }

    # Update image IDs
    data = _update_image_ids(input_data)

    # Check in list of images
    list_ids = [img["id"] for img in data["images"]]
    expected_list_ids = [
        expected_old_to_new_image_ids[img["id"]]
        for img in input_data["images"]
    ]
    assert expected_list_ids == list_ids

    # Check ids in list of annotations
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


def test_update_annotation_ids():
    """Test that annotation ids are updated to 0-based."""
    # Define a COCO data dict with minimal info
    input_data = {
        "annotations": [
            {"id": 1},
            {"id": 2},
        ],
    }

    # New annotation IDs follow enumerate
    expected_old_to_new_annotation_ids = {
        annot["id"]: i for i, annot in enumerate(input_data["annotations"])
    }

    # Update image IDs
    data = _update_annotation_ids(input_data)

    # Check in list of images
    list_ids = [annot["id"] for annot in data["annotations"]]
    expected_list_ids = [
        expected_old_to_new_annotation_ids[annot["id"]]
        for annot in input_data["annotations"]
    ]
    assert expected_list_ids == list_ids


def test_update_category_ids():
    """Test that category ids are updated to 0-based."""
    # Define a COCO data dict with minimal info
    input_data = {
        "categories": [
            {"id": 22},
            {"id": 11},
        ],
        "annotations": [
            {"id": 0, "category_id": 11},
            {"id": 1, "category_id": 22},
        ],
    }

    # New category IDs follow enumerate in categories list
    expected_old_to_new_category_ids = {
        cat["id"]: i for i, cat in enumerate(input_data["categories"])
    }

    # Update category IDs
    data = _update_category_ids(input_data)

    # Check in list of categories
    list_ids = [cat["id"] for cat in data["categories"]]
    expected_list_ids = [
        expected_old_to_new_category_ids[cat["id"]]
        for cat in input_data["categories"]
    ]
    assert expected_list_ids == list_ids


@patch("poseinterface.io._update_category_ids")
@patch("poseinterface.io._update_annotation_ids")
@patch("poseinterface.io._update_image_ids")
def test_update_ids(
    mock_update_image_ids,
    mock_update_annotation_ids,
    mock_update_category_ids,
    tmp_path,
):
    """Test that update functions are called and a file is saved."""
    # Input data
    input_data = {}
    output_file = tmp_path / "output.json"

    # Configure mock return values for each update step
    mock_update_image_ids.return_value = {"step": 1}
    mock_update_annotation_ids.return_value = {"step": 2}
    mock_update_category_ids.return_value = {"step": 3}

    # Call the function under test
    result = update_ids(input_data, output_file)

    # Assert each function was called with correct input
    mock_update_image_ids.assert_called_once_with(input_data)
    mock_update_annotation_ids.assert_called_once_with({"step": 1})
    mock_update_category_ids.assert_called_once_with({"step": 2})

    # Assert output file exists
    assert output_file.exists()
    assert result == output_file


# def test_annotations_to_coco():
#     """Test that annotations are converted to COCO format."""
#     pass
