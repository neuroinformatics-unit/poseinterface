from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import xarray as xr

from poseinterface.io import (
    _convert_movement_ds_to_videolabels,
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
