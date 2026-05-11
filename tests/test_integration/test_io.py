import pytest
from pytest_lazy_fixtures import lf

from poseinterface.io import annotations_to_poseinterface

EXPECTED_FILENAME_BY_FORMAT = {
    "frame": "sub-testSub123_ses-testSes123_cam-testCam123_framelabels.json",
    "clip": (
        "sub-testSub123_ses-testSes123_cam-testCam123_"
        "start-{start_frame}_dur-5_cliplabels.json"
    ),
    "start": (
        "sub-testSub123_ses-testSes123_cam-testCam123_"
        "start-{start_frame}_dur-5_startlabels.json"
    ),
}


@pytest.mark.parametrize(
    "input_path, expected_start_frame",
    [
        (lf("dlc_single_index_in_video_folder"), "0"),
        (lf("dlc_multi_index_in_video_folder"), "06825"),
        (lf("dlc_single_index_in_project_root"), "0"),
        (lf("dlc_multi_index_in_project_root"), "06825"),
    ],
)
@pytest.mark.parametrize("format", ["frame", "clip", "start"])
def test_annotations_to_poseinterface(
    input_path,
    expected_start_frame,
    format,
    tmp_path,
    sub_ses_cam_ids,
):
    """Test that annotations in different project structures are converted."""

    expected_filename = EXPECTED_FILENAME_BY_FORMAT[format].format(
        start_frame=expected_start_frame
    )

    output_json_path = tmp_path / expected_filename
    result = annotations_to_poseinterface(
        input_path,
        tmp_path,
        format=format,
        **sub_ses_cam_ids,
    )

    assert result == output_json_path
    assert output_json_path.exists()
