import copy
import json
import re
from pathlib import Path
from typing import Literal, TypeAlias

import numpy as np
import sleap_io as sio
import xarray as xr
from movement.io import load_dataset
from movement.io.load import _build_suffix_map, _validate_file
from movement.validators.files import (
    ValidAniposeCSV,
    ValidDeepLabCutCSV,
    ValidDeepLabCutH5,
    ValidFile,
    ValidNWBFile,
    ValidSleapAnalysis,
    ValidSleapLabels,
    ValidVIATracksCSV,
)
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


# Guessing source software for movement
SourceSoftware: TypeAlias = Literal[
    "DeepLabCut",
    "SLEAP",
    "LightningPose",
    "Anipose",
    "NWB",
    "VIA-tracks",
]

_SOURCE_SOFTWARE_VALIDATORS: dict[SourceSoftware, list[type[ValidFile]]] = {
    "SLEAP": [ValidSleapLabels, ValidSleapAnalysis],
    "DeepLabCut": [ValidDeepLabCutH5, ValidDeepLabCutCSV],
    "Anipose": [ValidAniposeCSV],
    "VIA-tracks": [ValidVIATracksCSV],
    "NWB": [ValidNWBFile],
}
# Note: LightningPose is excluded because it uses the same file
# format (and validator) as DeepLabCut. A LightningPose file
# loaded as "DeepLabCut" will work correctly.


def annotations_to_coco(
    input_path: Path,
    output_json_path: Path,
    *,
    coco_image_filenames: str | list[str] | None = None,
    coco_visibility_encoding: str = "ternary",
) -> Path:
    """Export annotations file from a single video to ``poseinterface`` format.

    Parameters
    ----------
    input_path : pathlib.Path
        Path to the input annotations file.
    output_json_path : pathlib.Path
        Path to save the output ``poseinterface`` COCO JSON file.
    coco_image_filenames : str | list[str] | None, optional
        Optional image filenames to use in the ``poseinterface`` COCO JSON.
        If provided, must be a single string (for single-frame videos)
        or a list of strings matching the number of labeled frames.
        If None (default), generates filenames from video filenames
        and frame indices.
    coco_visibility_encoding : str, optional
        Encoding scheme for keypoint visibility in the ``poseinterface`` COCO
        JSON file. Options are "ternary" (0: not labeled, 1: labeled
        but not visible, 2: labeled and visible) or "binary" (0: not
        visible, 1: visible). Default is "ternary".

    Returns
    -------
    pathlib.Path
        Path to the saved ``poseinterface`` COCO JSON file.

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


def predictions_to_poseinterface(
    predictions_path: Path | str,
    video_path: Path | str,
    output_json_parent_dir: Path | str,
    *,
    sub_id: str,
    ses_id: str,
    cam_id: str,
) -> Path:
    """Convert a prediction file to ``poseinterface`` COCO JSON format.

    Reads a predictions file and writes a JSON with ``poseinterface``-style
    filenames suitable for clip-level labels (``_cliplabels.json``).

    Parameters
    ----------
    predictions_path
        Path to the DLC predictions CSV file.
    video_path
        Path to the corresponding video file.  Used to attach video
        metadata (resolution) to the COCO output.
    output_json_parent_dir
        Path to the directory where to save the output JSON file.
    sub_id
        Subject ID to include in the generated filenames.
    ses_id
        Session ID to include in the generated filenames.
    cam_id
        Camera ID to include in the generated filenames.

    Returns
    -------
    Path
        Path to the saved COCO JSON file.
    """
    # Guess source software using movement validators
    # (take first guess)
    source_software = _guess_source_software(predictions_path)[0]

    # Read input file as movement dataset
    # NOTE: fps=None is ignore with NWB files
    ds = load_dataset(
        file=predictions_path,
        source_software=source_software,
        fps=None,
    )

    # Get video image width and height
    video = sio.load_video(video_path)
    _, img_h, img_w, _ = video.shape

    # Convert movement dataset to cliplabels dict
    coco_data = _convert_movement_ds_to_cliplabels(
        ds,
        sub_id=sub_id,
        ses_id=ses_id,
        cam_id=cam_id,
        img_h=img_h,
        img_w=img_w,
    )

    # Export dict as JSON
    output_json_parent_dir = (
        Path(output_json_parent_dir)
        / f"sub-{sub_id}_ses-{ses_id}_cam-{cam_id}.json"
    )
    with open(output_json_parent_dir, "w") as f:
        json.dump(coco_data, f)

    return output_json_parent_dir


def _guess_source_software(file: Path | str) -> list[SourceSoftware]:
    """Guess the source software based on file validation.

    Tries each known file validator against the given file and returns
    the source software names whose validators accept the file.

    Parameters
    ----------
    file
        Path to the file to identify.

    Returns
    -------
    list[SourceSoftware]
        List of source software names whose validators matched.

    Examples
    --------
    >>> from movement.io.load import guess_source_software
    >>> guess_source_software("path/to/predictions.h5")
    ['DeepLabCut']

    """
    file = Path(file)
    suffix = file.suffix
    matches: list[SourceSoftware] = []

    for (
        source_software,
        validator_classes,
    ) in _SOURCE_SOFTWARE_VALIDATORS.items():
        map_suffix_to_validators = _build_suffix_map(validator_classes)
        # If input suffix not associated to this set of validators, continue
        if suffix not in map_suffix_to_validators:
            continue

        # If suffix is covered by these validators, use them to
        # validate the input file
        try:
            _validate_file(file, map_suffix_to_validators, source_software)
            matches.append(source_software)
        except Exception:
            continue

    return matches


def _convert_movement_ds_to_cliplabels(
    ds: xr.Dataset,
    *,
    sub_id: str,
    ses_id: str,
    cam_id: str,
    img_w: int,
    img_h: int,
) -> dict[str, list[dict]]:
    """Convert predictions in movement dataset to cliplabels.json"""
    # Extract position array and coordinates from dataset
    positions = ds["position"].values  # (time, space, keypoints, individuals)
    n_frames = positions.shape[0]

    keypoint_names = ds.coords["keypoints"].values.tolist()
    individual_names = ds.coords["individuals"].values.tolist()

    # Build categories list (one entry per individual)
    # NOTE: categories are 1-indexed to avoid conflicts
    # with models that treat category 0 as background.
    categories = [
        {
            "id": i + 1,
            "name": name,
            "keypoints": keypoint_names,
            "skeleton": [],
        }
        for i, name in enumerate(individual_names)
    ]

    # Build images list (one entry per frame)
    # NOTE: image id values are always 0-indexed
    images = [
        {
            "id": t,
            "file_name": (
                f"sub-{sub_id}_ses-{ses_id}_cam-{cam_id}_frame-{t:04d}"
            ),
            "width": img_w,
            "height": img_h,
        }
        for t in range(n_frames)
    ]

    # Build annotations list (one entry per frame per individual)
    annotations = []
    annot_id = 1
    for t in range(n_frames):
        for i in range(len(individual_names)):
            # Get position data for this frame and individual
            xy = positions[t, :, :, i]  # (2, n_keypoints)

            # Determine kpt visibility:
            # 0: not labeled
            # 1: labeled but not visible (occluded)
            # 2: labeled and visible
            # NOTE: The current code only assigns 0 or 2 because the movement
            # dataset doesn't carry occlusion information
            visible_array = ~np.isnan(xy[0]) & ~np.isnan(xy[1])
            n_visible = int(visible_array.sum())

            # Get list of flattened keypoints
            # [x1, y1, v1, x2, y2, v2, ...]
            x = np.where(visible_array, xy[0], 0.0)
            y = np.where(visible_array, xy[1], 0.0)
            v = np.where(visible_array, 2, 0)
            list_xyv_kpts = np.stack([x, y, v], axis=1).ravel().tolist()

            # Compute bbox from visible keypoints
            # (zeros if no keypoints are visible)
            if n_visible > 0:
                x_visible = xy[0, visible_array]
                y_visible = xy[1, visible_array]
                x_min = float(x_visible.min())
                y_min = float(y_visible.min())
                bbox_w = float(x_visible.max()) - x_min
                bbox_h = float(y_visible.max()) - y_min
            else:
                x_min, y_min, bbox_w, bbox_h = 0.0, 0.0, 0.0, 0.0

            # Append results to list of annotations
            annotations.append(
                {
                    "id": annot_id,
                    "image_id": t,
                    "category_id": i + 1,
                    "keypoints": list_xyv_kpts,
                    "num_keypoints": n_visible,
                    "bbox": [x_min, y_min, bbox_w, bbox_h],
                    "area": bbox_w * bbox_h,
                    "iscrowd": 0,
                }
            )
            annot_id += 1

    return {
        "images": images,
        "annotations": annotations,
        "categories": categories,
    }
