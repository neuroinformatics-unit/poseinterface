import json
from pathlib import Path

import pytest
import sleap_io as sio

from poseinterface.io import (
    _generate_poseinterface_filenames,
    _pad_integers_to_same_width,
)


@pytest.fixture
def dlc_data_dir():
    """Directory containing single-animal DLC CSV files."""
    return Path("tests/data/dlc/labeled-data/video")


@pytest.fixture
def dlc_testdata(dlc_data_dir):
    """Single-animal DLC CSV file."""
    return dlc_data_dir / "CollectedData_Loukia_start-1000_dur-5.csv"


@pytest.fixture
def dlc_testdata_v2(dlc_data_dir):
    """Single-animal DLC CSV file with multi-column image paths."""
    return dlc_data_dir / "CollectedData_Loukia_start-1000_dur-5_v2.csv"


@pytest.fixture
def framelabels_json_path():
    """Path to the framelabels JSON file."""
    return Path(
        "tests/data/Train/SWC-plusmaze/sub-M708149_ses-20200317/Frames/"
        "sub-M708149_ses-20200317_cam-topdown_framelabels.json"
    )


@pytest.fixture
def clips_json_path():
    """Path to the clips JSON file."""
    return Path(
        "tests/data/Train/SWC-plusmaze/sub-M708149_ses-20200317/Clips/"
        "sub-M708149_ses-20200317_cam-topdown_start-1000_dur-5_cliplabels.json"
    )


@pytest.mark.parametrize("include_file_extension", [True, False])
@pytest.mark.parametrize("input_path", ["dlc_testdata", "dlc_testdata_v2"])
def test_generate_poseinterface_filenames(
    input_path,
    include_file_extension,
    framelabels_json_path,
    clips_json_path,
    request,
):
    generated_filenames = _generate_poseinterface_filenames(
        sio.load_file(request.getfixturevalue(input_path)),
        sub_id="M708149",
        ses_id="20200317",
        cam_id="topdown",
        include_file_extension=include_file_extension,
    )
    # Load expected filenames from framelabels.json
    labels_json_path = (
        framelabels_json_path if include_file_extension else clips_json_path
    )
    with open(labels_json_path) as f:
        frames_data = json.load(f)
    expected_frames_filenames = [
        img["file_name"] for img in frames_data["images"]
    ]
    assert generated_filenames == expected_frames_filenames


def test_pad_integers_to_same_width():
    input = [1, 10, 100]
    expected_output = ["001", "010", "100"]
    assert _pad_integers_to_same_width(input) == expected_output
