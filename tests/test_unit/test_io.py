from pathlib import Path

import pytest

from poseinterface.io import annotations_to_coco


@pytest.mark.parametrize(
    "fixture_name",
    ["dlc_project_pranav", "dlc_project_loukia", "dlc_project_shailaja"],
)
def test_annotations_to_coco(fixture_name: str, request, tmp_path: Path):
    """Test that annotations_to_coco works with different DLC CSV formats."""
    csv_path = request.getfixturevalue(fixture_name)
    output_path = tmp_path / "output.json"

    result = annotations_to_coco(csv_path, output_path)

    assert result == output_path
    assert output_path.exists()
