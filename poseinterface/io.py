from pathlib import Path

import sleap_io as sio
from sleap_io.io import dlc

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


def annotations_to_coco(
    input_path: Path,
    output_json_path: Path,
    *,
    coco_image_filenames: str | list[str] | None = None,
    coco_visibility_encoding: str = "ternary",
) -> Path:
    """Export annotations file to COCO format.

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
        if dlc.is_dlc_file(input_path):
            error_msg += _EMPTY_LABELS_ERROR_MSG["dlc"]
        raise ValueError(error_msg)
    sio.save_coco(
        labels,
        output_json_path,
        image_filenames=coco_image_filenames,
        visibility_encoding=coco_visibility_encoding,
    )
    return output_json_path
