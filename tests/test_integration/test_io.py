import pytest

from poseinterface.io import annotations_to_poseinterface


@pytest.mark.parametrize(
    "input_path",
    [
        "dlc_single_index_in_video_folder",
        "dlc_multi_index_in_video_folder",
        "dlc_single_index_in_project_root",
        "dlc_multi_index_in_project_root",
    ],
)
def test_annotations_to_poseinterface(
    input_path, tmp_path, sub_ses_cam_ids, request
):
    """Test that annotations in different project structures are converted."""

    input_path = request.getfixturevalue(input_path)
    output_json_path = (
        tmp_path
        / "sub-testSub123_ses-testSes123_cam-testCam123_framelabels.json"
    )

    annotations_to_poseinterface(input_path, tmp_path, **sub_ses_cam_ids)

    assert output_json_path.exists()
