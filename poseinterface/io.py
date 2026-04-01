import copy
import json
import re
from pathlib import Path
from typing import Literal, TypeAlias

import sleap_io as sio
from sleap_io.io import coco
from sleap_io.io.dlc import is_dlc_file

PoseInterfaceFormat: TypeAlias = Literal["clip", "frame", "start"]

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
DLC_FRAME_REGEXP = r"(\d+)"


def annotations_to_poseinterface(
    input_path: Path,
    output_dir: Path,
    *,
    sub_id: str,
    ses_id: str,
    cam_id: str,
    format: PoseInterfaceFormat = "frame",
) -> Path:
    """Export annotations file from a single video to ``poseinterface`` format.

    Parameters
    ----------
    input_path
        Path to the input annotations file.
    output_dir
        Directory where the output ``poseinterface`` COCO JSON file
        will be saved.
    sub_id
        Subject ID to include in the generated filenames.
    ses_id
        Session ID to include in the generated filenames.
    cam_id
        Camera ID to include in the generated filenames.
    format
        Whether to generate :ref:`frame labels<target-framelabels>`,
        :ref:`clip labels<target-cliplabels>`, or :ref:`clip start labels\
        <target-startlabels>`. Default is "frame".

    Returns
    -------
    pathlib.Path
        Path to the saved ``poseinterface`` COCO JSON file.

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
    sleap_io.io.main.load_file
        The underlying function used to load the input annotations file as
        a SLEAP labels object.
    sleap_io.io.coco.convert_labels
        The underlying function used to convert SLEAP labels to COCO format.

    Example
    -------
    >>> from pathlib import Path
    >>> from poseinterface.io import annotations_to_poseinterface
    >>> coco_json_path = annotations_to_poseinterface(
    ...     input_path=Path("path/to/annotations.slp"),
    ...     output_dir=Path("path/to/output_directory"),
    ...     sub_id="testSub123",
    ...     ses_id="testSes123",
    ...     cam_id="testCam123",
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
        include_file_extension=(format == "frame"),
    )
    # Generate COCO dict
    coco_data = coco.convert_labels(labels, image_filenames=image_filenames)
    # Update image IDs in coco_data to match the frame numbers in the filenames
    coco_data = _update_image_ids(coco_data)

    output_json_path = _build_output_json_path(
        output_dir=output_dir,
        coco_data=coco_data,
        sub_id=sub_id,
        ses_id=ses_id,
        cam_id=cam_id,
        format=format,
    )

    with open(output_json_path, "w") as f:
        json.dump(coco_data, f)

    return output_json_path


def _build_output_json_path(
    *,
    output_dir: Path,
    coco_data: dict,
    sub_id: str,
    ses_id: str,
    cam_id: str,
    format: PoseInterfaceFormat,
) -> Path:
    """Build output JSON path using poseinterface naming conventions."""
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"sub-{sub_id}_ses-{ses_id}_cam-{cam_id}"

    if format == "frame":
        return output_dir / f"{prefix}_framelabels.json"

    label_suffix = "cliplabels" if format == "clip" else "startlabels"
    image_ids = [img["id"] for img in coco_data["images"]]
    if len(image_ids) == 0:
        raise ValueError(
            "No image IDs were found in the COCO data. "
            f"Cannot infer start frame and duration for {label_suffix} format."
        )
    start_frame = min(image_ids)
    n_frames = len(image_ids)
    return (
        output_dir
        / f"{prefix}_start-{start_frame}_dur-{n_frames}_{label_suffix}.json"
    )


def _update_image_ids(coco_data: dict) -> dict:
    """Assign new image IDs based on the frame number in the filename."""
    # Create new dict
    data = copy.deepcopy(coco_data)

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
    labels
        SLEAP labels object containing the annotations and video information.
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

    Notes
    -----
    When the SLEAP labels video object is a video file, per-frame file
    extensions are not available. Therefore, when ``include_file_extension``
    is True, the generated filenames assume a ``.png`` extension.

    """
    video_filenames = labels.videos[0].filename
    if isinstance(video_filenames, list):  # Sequence of frame images
        frame_numbers = [
            _extract_frame_number(Path(fn).stem, frame_regexp=DLC_FRAME_REGEXP)
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
