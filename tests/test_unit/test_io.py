from pathlib import Path

from poseinterface.io import annotations_to_coco


def test_annotations_to_coco_pranav(dlc_project_pranav: Path, tmp_path: Path):
    """Test that annotations_to_coco works with the Pranav CSV file."""
    output_path = tmp_path / "output.json"

    result = annotations_to_coco(dlc_project_pranav, output_path)

    assert result == output_path
    assert output_path.exists()
