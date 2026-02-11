import copy
import json
import re
from pathlib import Path

import sleap_io as sio
from sleap_io.io import coco
from sleap_io.io.dlc import is_dlc_file

_EMPTY_LABELS_ERROR_MSG = {
    "default": (
        "No annotations could be extracted from the input file. "
        "Please check that the input file contains labeled frames. "
    ),
    "dlc": (
        "Ensure that the paths to the labelled frames are in the "
        "standard DLC project format: "
        "labeled-data / <video-name> / "
        "<filename-with-frame-number>.<extension> "
        "and that the frames files exist."
    ),
}

POSEINTERFACE_FRAME_REGEXP = r"frame-(\d+)"


def annotations_to_coco(
    input_path: Path,
    output_json_path: Path,
    *,
    coco_image_filenames: str | list[str] | None = None,
    coco_visibility_encoding: str = "ternary",
) -> Path:
    """Export annotations file from a single video to poseinterface format.

    Parameters
    ----------
    input_path : pathlib.Path
        Path to the input annotations file.
    output_json_path : pathlib.Path
        Path to save the output COCO JSON file.
    coco_image_filenames : str | list[str] | None, optional
        Optional image filenames to use in the COCO JSON. If provided,
        must be a single string (for single-frame videos) or a list of
        strings matching the number of labeled frames. If None (default),
        generates filenames from video filenames and frame indices.
    coco_visibility_encoding : str, optional
        Encoding scheme for keypoint visibility in the COCO JSON file.
        Options are "ternary" (0: not labeled, 1: labeled but not visible,
        2: labeled and visible) or "binary" (0: not visible, 1: visible).
        Default is "ternary".

    Returns
    -------
    pathlib.Path
        Path to the saved COCO JSON file.

    Notes
    -----
    The format of the input annotations file is automatically inferred based
    on its extension. See :func:`sleap_io.io.main.load_file` for supported
    formats.

    In the poseinterface COCO output file, the image IDs correspond to the
    frame numbers and are derived from the image filenames. The annotation and
    category ids are 0-based indices.

    Example
    -------
    >>> from pathlib import Path
    >>> from poseinterface.io import annotations_to_coco
    >>> coco_json_path = annotations_to_coco(
    ...     input_path=Path("path/to/annotations.slp"),
    ...     output_json_path=Path("path/to/annotations_coco.json"),
    ... )
    """
    labels = sio.load_file(input_path)

    # Check if labels object is empty
    if len(labels.labeled_frames) == 0:
        error_msg = _EMPTY_LABELS_ERROR_MSG["default"]
        if is_dlc_file(input_path):
            error_msg += _EMPTY_LABELS_ERROR_MSG["dlc"]
        raise ValueError(error_msg)

    # Check single video
    if len(labels.videos) > 1:
        raise ValueError(
            "The annotations refer to multiple videos "
            f"(n={len(labels.videos)}). "
            "Please check that the input file contains annotations "
            "for a single video only."
        )

    # Generate COCO dict from sleap-io
    # with PR19 image_filenames = poseinterface filenames
    coco_data = coco.convert_labels(
        labels,
        image_filenames=coco_image_filenames,
        visibility_encoding=coco_visibility_encoding,
    )

    # Update image ids to match frame number
    # uncomment after PR19
    # coco_data = _update_image_ids(coco_data)

    # Save JSON file
    with open(output_json_path, "w") as f:
        json.dump(coco_data, f)

    return output_json_path


def _update_image_ids(input_data: dict) -> dict:
    """Assigns new image IDs based on the frame number in the filename."""
    # Create new dict
    data = copy.deepcopy(input_data)

    # Build map old-to-new image IDs and update image id in images list
    old_to_new_id = {}
    for img in data["images"]:
        # map old image_id to new image_id
        old_img_id = img["id"]
        new_img_id = _extract_frame_number(img["file_name"])
        old_to_new_id[old_img_id] = new_img_id

        # update image_id in images list
        img["id"] = new_img_id

    # Check new image IDs are unique
    if len(old_to_new_id) != len(set(old_to_new_id.values())):
        raise ValueError(
            "Extracted image IDs are not unique. Please check that the frame "
            "numbers as specified in the filename are unique."
        )

    # Update image_id in annotations list
    for annot in data["annotations"]:
        annot["image_id"] = old_to_new_id[annot["image_id"]]

    return data


def _extract_frame_number(
    filename: str, frame_regexp: str = POSEINTERFACE_FRAME_REGEXP
) -> int | None:
    """Extract the frame number in the input filename.

    If no frame number is found, returns None.
    """
    match = re.search(frame_regexp, filename)
    if match is None:
        raise ValueError(
            "No frame number could be extracted from filename "
            f"{filename}. Please check that the filename contains a "
            "frame number matching the provided regexp pattern "
            rf"'{frame_regexp}'."
        )
    return int(match.group(1))
