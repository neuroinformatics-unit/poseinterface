from pathlib import Path

from sleap_io.io import coco, dlc


def format_dlc_annotations_file(
    input_path: Path,
    output_json_path: Path,
    coco_image_filenames: str | list[str] | None = None,
    coco_visibility_encoding: str = "ternary",
) -> dict:
    """Export input DLC annotations file to COCO format."""
    # Read annotations as Labels object
    labels = dlc.load_dlc(input_path, video_search_paths=None)

    # Check if labels object is empty
    if len(labels.labeled_frames) == 0:
        raise ValueError(
            "No annotations could be extracted from the input file."
            "Please check the paths to the labelled frames are in the "
            "standard DLC project format: "
            "labeled-data / <video-name> / "
            "<filename-with-frame-number>.<extension>"
            "and that the frames files exist."
        )

    # Export Labels object to COCO
    coco.write_labels(
        labels,
        output_json_path,
        visibility_encoding=coco_visibility_encoding,
        image_filenames=coco_image_filenames,
    )

    return output_json_path
