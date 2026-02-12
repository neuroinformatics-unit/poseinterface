import copy
import json
import re
from pathlib import Path
from typing import Literal

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
    sub_id: str,
    ses_id: str,
    cam_id: str,
    mode: Literal["clip", "frame"] = "frame",
) -> Path:
    """Export annotations file from a single video to ``poseinterface`` format.

    Parameters
    ----------
    input_path
        Path to the input annotations file.
    output_json_path
        Path to save the output ``poseinterface`` COCO JSON file.
    sub_id
        Subject ID to include in the generated filenames.
    ses_id
        Session ID to include in the generated filenames.
    cam_id
        Camera ID to include in the generated filenames.
    mode
        Whether to generate framelabels.json or cliplabels.json.
        If "frame", the image filenames will include the file
        extension of frame files. If "clip", the image filenames
        will not include the file extension as these frame files
        may not exist (e.g. if the frames files have not been
        extracted from the clip).

    Returns
    -------
    Path
        Path to the saved COCO JSON file.

    Raises
    ------
    ValueError
        If no labeled frames could be extracted from the input file,
        or if the annotations refer to multiple videos.

    Notes
    -----
    The format of the input annotations file is automatically inferred based
    on its extension. See :func:`sleap_io.io.main.load_file` for supported
    formats.

    See Also
    --------
    sleap_io.io.coco.convert_labels
        The underlying function used to convert SLEAP labels to COCO format.

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

    if len(labels.labeled_frames) == 0:
        error_msg = _EMPTY_LABELS_ERROR_MSG["default"]
        if is_dlc_file(input_path):
            error_msg += _EMPTY_LABELS_ERROR_MSG["dlc"]
        raise ValueError(error_msg)

    if len(labels.videos) > 1:
        raise ValueError(
            "The annotations refer to multiple videos "
            f"(n={len(labels.videos)}). "
            "Please check that the input file contains annotations "
            "for a single video only."
        )

    # Generate image filenames in the poseinterface format
    image_filenames = _generate_poseinterface_filenames(
        labels,
        sub_id=sub_id,
        ses_id=ses_id,
        cam_id=cam_id,
        include_file_extension=(mode == "frame"),
    )
    # Generate COCO dict
    coco_data = coco.convert_labels(labels, image_filenames=image_filenames)
    # Update image IDs in coco_data to match the frame IDs in the filenames
    coco_data = _update_image_ids(coco_data)

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
) -> int:
    """Extract the frame number in the input filename.

    If no frame number is found, a ValueError is raised.
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


def _generate_poseinterface_filenames(
    labels: sio.Labels,
    *,
    sub_id: str,
    ses_id: str,
    cam_id: str,
    include_file_extension: bool = False,
) -> list[str]:
    """Generate PoseInterface image filenames an input annotations file.

    The generated filenames are in the format:
    {sub_id}_{ses_id}_{cam_id}_frame-{0-padded_frame_number}

    If `include_file_extension` is True, the generated filenames will include
    the file extension of the original frame files, in the format:
    {sub_id}_{ses_id}_{cam_id}_frame-{0-padded_frame_number}.{file_extension}

    Parameters
    ----------
    input_path
        Path to the input annotations file.
    sub_id
        Subject ID to include in the generated filenames.
    ses_id
        Session ID to include in the generated filenames.
    cam_id
        Camera ID to include in the generated filenames.
    include_file_extension
        Whether to include the file extension of the original frame files
        in the generated filenames. Default is False.

    Returns
    -------
    list[str]
        List of generated COCO image filenames corresponding to each
        labeled frame.

    Raises
    ------
    ValueError
        If no labeled frames could be extracted from the input file.
    """
    video_filenames = labels.videos[0].filename
    if isinstance(video_filenames, list):  # Sequence of frame images
        frame_numbers = [
            _extract_frame_number(Path(fn).stem, frame_regexp=r"(\d+)")
            for fn in video_filenames
        ]
        file_extensions = (
            [Path(fn).suffix for fn in video_filenames]
            if include_file_extension
            else []
        )
    else:  # Video file
        frame_numbers = [lf.frame_idx for lf in labels.labeled_frames]
        file_extensions = (
            [".png"] * len(frame_numbers) if include_file_extension else []
        )
    # Pad frame_numbers to the same width
    padded_frame_numbers = _pad_integers_to_same_width(frame_numbers)
    # Build filenames
    prefix = f"sub-{sub_id}_ses-{ses_id}_cam-{cam_id}_frame-"
    if include_file_extension:
        return [
            prefix + frame_id + ext
            for frame_id, ext in zip(padded_frame_numbers, file_extensions)
        ]
    else:
        return [prefix + frame_id for frame_id in padded_frame_numbers]


def _pad_integers_to_same_width(input: list[int]) -> list[str]:
    """Pad a list of integers to the same width with leading zeros."""
    width = len(str(max(input)))
    padded_numbers = [str(number).zfill(width) for number in input]
    return padded_numbers
