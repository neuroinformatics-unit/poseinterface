import json

import pytest

from poseinterface.clips import _extract_cliplabels


@pytest.fixture
def video_labels():
    n_images = 10
    n_annot = 5  # per image
    return {
        "images": [{"id": i} for i in range(n_images)],
        "annotations": [
            {"image_id": i, "id": j}
            for i in range(n_images)
            for j in range(n_annot)
        ],
        "categories": [{"id": 1, "name": "mouse"}],
    }


def test_extract_cliplabels(tmp_path, video_labels):
    """Test clip json file is extracted from the video cliplabels.json file."""
    # Set up fake video path and corresponding cliplabels.json
    video_path = tmp_path / "sub-01_ses-01_cam-01.mp4"
    json_path = tmp_path / "sub-01_ses-01_cam-01_cliplabels.json"
    json_path.write_text(json.dumps(video_labels))

    # Set up a "Clips" destination directory
    clips_dir = tmp_path / "Clips"
    clips_dir.mkdir()

    # Extract labels from frame 3 to frame 6, both included
    start_frame = 3
    duration = 4
    clip_json = _extract_cliplabels(
        video_path, clips_dir, start_frame=start_frame, duration=duration
    )

    # Load results
    clip_labels = json.loads(clip_json.read_text())

    # Check image IDs in results
    selected_img_ids = list(range(start_frame, start_frame + duration))
    assert [img["id"] for img in clip_labels["images"]] == selected_img_ids

    # Check annotations are unchanged for the selected image_id
    expected_annotations = [
        ann
        for ann in video_labels["annotations"]
        if ann["image_id"] in selected_img_ids
    ]
    assert clip_labels["annotations"] == expected_annotations

    # Check categories are unchanged
    assert clip_labels["categories"] == video_labels["categories"]


def test_extract_clip():
    pass
