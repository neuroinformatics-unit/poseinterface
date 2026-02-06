import pytest

from poseinterface.io import annotations_to_coco


@pytest.mark.parametrize(
    "input_path",
    [
        "dlc_single_index_in_video_folder",
        "dlc_multi_index_in_video_folder",
        "dlc_single_index_in_project_root",
        "dlc_multi_index_in_project_root",
    ],
)
def test_annotations_to_coco(input_path, tmp_path, request):
    """Test that annotations in different project structures are converted."""

    input_path = request.getfixturevalue(input_path)
    output_json_path = tmp_path / "output.json"

    annotations_to_coco(input_path, output_json_path)

    assert output_json_path.exists()
