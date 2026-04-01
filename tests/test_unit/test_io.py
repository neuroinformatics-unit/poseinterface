import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import xarray as xr
from pytest_lazy_fixtures import lf

from poseinterface.io import (
    _EMPTY_LABELS_ERROR_MSG,
    POSEINTERFACE_FRAME_REGEXP,
    _extract_frame_number,
    _update_image_ids,
    annotations_to_coco,
    predictions_to_poseinterface,
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
def test_annotations_to_coco(
    mock_load_file,
    mock_convert_labels,
    tmp_path,
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
    result = annotations_to_coco(input_csv, output_path)

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
        annotations_to_coco(
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
        annotations_to_coco(
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


@patch("poseinterface.io.sio.load_video")
@patch("poseinterface.io.load_dataset")
@patch("poseinterface.io._guess_source_software")
def test_predictions_to_poseinterface(
    mock_guess_source_software,
    mock_load_dataset,
    mock_load_video,
    sample_movement_ds,
    mock_video,
    tmp_path,
):
    """Test that predictions are converted to COCO JSON."""
    # Get movement dataset and video fixtures
    ds = sample_movement_ds
    video = mock_video(n_frames=3)
    _, img_h, img_w, _ = video.shape

    # Mock return values for supporting functions
    mock_guess_source_software.return_value = ["DeepLabCut"]
    mock_load_dataset.return_value = ds
    mock_load_video.return_value.shape = video.shape

    # Convert predictions
    result = predictions_to_poseinterface(
        predictions_path="fake.csv",
        video_path="fake.mp4",
        output_json_parent_dir=tmp_path,
        sub_id="M01",
        ses_id="20240101",
        cam_id="top",
    )

    # Check output file exists
    assert result.exists()
    assert result.name == "sub-M01_ses-20240101_cam-top.json"

    # Check content
    with open(result) as f:
        data = json.load(f)

    # Check top-level keys
    assert set(data.keys()) == {"images", "annotations", "categories"}

    # Check images
    assert len(data["images"]) == len(ds.time)
    for k in range(len(data["images"])):
        assert data["images"][k]["file_name"] == (
            f"sub-M01_ses-20240101_cam-top_frame-000{k}"
        )
        assert data["images"][k]["width"] == img_w
        assert data["images"][k]["height"] == img_h

    # Check categories
    assert len(data["categories"]) == len(ds.individuals)
    assert data["categories"][0]["name"] == ds.individuals.values.tolist()[0]
    assert data["categories"][0]["keypoints"] == ds.keypoints.values.tolist()

    # Check annotations
    # 2 frames x 1 individual = 2 annotations
    assert len(data["annotations"]) == len(ds.time) * len(ds.individuals)

    # Frame 0: both keypoints visible
    # kpt0=(10, 30), kpt1=(20, 40)
    annot0 = data["annotations"][0]
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
    annot1 = data["annotations"][1]
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
