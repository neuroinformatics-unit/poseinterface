import tempfile
from pathlib import Path

import pandas as pd
import sleap_io as sio

_EMPTY_LABELS_ERROR_MSG = (
    "No annotations could be extracted from the input file. "
    "Please check that the input file contains labeled frames "
    "and that the referenced frame files exist."
)


def _is_dlc_csv_with_multiindex_rows(file_path: Path) -> bool:
    """Check if file is a DLC CSV with multi-index rows for image paths.

    Newer DLC CSV files store the image path as a MultiIndex across 3 columns
    (labeled-data, video-folder, filename) instead of a single column with
    slash-separated path. This follows the detection logic from DLC's own
    conversioncode.py.

    Returns True if the file:
    - Has .csv extension
    - First line starts with 'scorer'
    - First data row starts with 'labeled-data' as a separate column
    """
    if file_path.suffix.lower() != ".csv":
        return False

    with open(file_path) as f:
        first_line = f.readline()
        if not first_line.startswith("scorer"):
            return False

        # Skip header rows: 3 for single-animal, 4 for multi-animal
        second_line = f.readline()
        f.readline()  # bodyparts (or individuals for multi-animal)
        if "individuals" in second_line:
            f.readline()  # coords (extra row for multi-animal)

        # Check if first data row starts with "labeled-data" as first column
        # This indicates MultiIndex format (3 columns for path)
        data_line = f.readline()
        return data_line.split(",")[0] == "labeled-data"


def _convert_dlc_csv_to_single_index(file_path: Path) -> Path:
    """Convert a DLC CSV with MultiIndex rows to single-index format.

    Reads the CSV using pandas with index_col=[0, 1, 2] to properly parse
    the 3-column path structure, then re-saves with a single-column path
    using forward slashes.

    This follows the approach used by DLC's own conversioncode.py.

    Returns path to the temporary file.
    """
    # Determine header rows (3 for standard, 4 for multi-animal)
    with open(file_path) as f:
        f.readline()  # scorer
        second_line = f.readline()
        header = list(range(4 if "individuals" in second_line else 3))

    # Read with 3-column index (labeled-data, video-folder, filename)
    df = pd.read_csv(file_path, index_col=[0, 1, 2], header=header)

    # Convert MultiIndex to single index by joining with '/'
    df.index = df.index.map("/".join)

    # Create temp file in same directory (so relative paths still work)
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        dir=file_path.parent,
        delete=False,
    )
    temp_file.close()

    # Save with single-column index
    df.to_csv(temp_file.name)

    return Path(temp_file.name)


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
    # Handle DLC CSV files with multi-column row index
    temp_file_path = None
    load_path = input_path
    if _is_dlc_csv_with_multiindex_rows(input_path):
        temp_file_path = _convert_dlc_csv_to_single_index(input_path)
        load_path = temp_file_path

    try:
        labels = sio.load_file(load_path)
        # Check if labels object is empty
        if len(labels.labeled_frames) == 0:
            raise ValueError(_EMPTY_LABELS_ERROR_MSG)
        sio.save_coco(
            labels,
            output_json_path,
            image_filenames=coco_image_filenames,
            visibility_encoding=coco_visibility_encoding,
        )
        return output_json_path
    finally:
        # Clean up temp file if created
        if temp_file_path is not None:
            temp_file_path.unlink(missing_ok=True)
