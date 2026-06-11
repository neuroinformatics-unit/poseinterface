"""Functions to convert annotations and videos to ``poseinterface`` format."""

import copy
import json
import logging
import re
import shutil
import warnings
from pathlib import Path
from typing import Literal, TypeAlias

import numpy as np
import pandas as pd
import sleap_io as sio
import xarray as xr
from movement.io import load_dataset
from sleap_io.io import coco
from sleap_io.io.cli import _get_video_encoding_info, _is_ffmpeg_available
from sleap_io.io.dlc import is_dlc_file

PoseInterfaceFormat: TypeAlias = Literal["clip", "frame"]

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

# We support sleap's MediaVideo files
EXPECTED_SUFFIX = ".mp4"
EXPECTED_ENCODING = {
    "pixelformat": "yuv420p",
    "codec": "h264",  # codec name
}
REENCODING_PARAMS = {
    **EXPECTED_ENCODING,
    "codec": "libx264",  # overwrite with encoder to use
    "crf": 25,
    "preset": "superfast",
}


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
        Whether to generate :ref:`frame labels<target-framelabels>` or
        :ref:`clip labels<target-cliplabels>`. Default is "frame".

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
    # Update image IDs in coco_data
    coco_data = _update_image_ids(coco_data, format=format)

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

    if len(coco_data["images"]) == 0:
        raise ValueError(
            "No images were found in the COCO data. "
            "Cannot infer start frame and duration for cliplabels format."
        )
    frame_numbers = [
        _extract_frame_number(img["file_name"]) for img in coco_data["images"]
    ]
    start_frame = min(frame_numbers)
    n_frames = len(frame_numbers)
    padded_start = str(start_frame).zfill(len(str(max(frame_numbers))))
    return (
        output_dir
        / f"{prefix}_start-{padded_start}_dur-{n_frames}_cliplabels.json"
    )


def _update_image_ids(
    coco_data: dict, format: PoseInterfaceFormat = "frame"
) -> dict:
    """Assign new image IDs based on the format.

    For frame format, each image ID is set to the session-video frame number
    extracted from the filename. For clip format, images are sorted by frame
    number and assigned 0-based indices within the clip.
    """
    file_names = [img["file_name"] for img in coco_data["images"]]
    if len(file_names) != len(set(file_names)):
        raise ValueError(
            "Duplicate image filenames were found. Please check that the "
            "input annotations do not contain duplicate frames."
        )

    data = copy.deepcopy(coco_data)

    old_to_new_id = {}
    if format == "frame":
        for img in data["images"]:
            old_img_id = img["id"]
            new_img_id = _extract_frame_number(img["file_name"])
            old_to_new_id[old_img_id] = new_img_id
    else:
        data["images"].sort(
            key=lambda img: _extract_frame_number(img["file_name"])
        )
        for idx, img in enumerate(data["images"]):
            old_to_new_id[img["id"]] = idx

    if len(old_to_new_id) != len(set(old_to_new_id.values())):
        raise ValueError(
            "Extracted image IDs are not unique. Please check that the frame "
            "numbers as specified in the filename are unique."
        )

    for img in data["images"]:
        img["id"] = old_to_new_id[img["id"]]
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
    """Generate PoseInterface image filenames for frames in the input labels.

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
    padded_frame_numbers = _pad_integers_to_same_width(frame_numbers)
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


def video_to_poseinterface(
    input_video: Path | str,
    output_video_dir: Path | str,
    *,
    sub_id: str,
    ses_id: str,
    cam_id: str,
) -> Path:
    """Reencode and rename a video to ``poseinterface`` format.

    Copies the input video to ``output_video_dir`` with the filename
    ``sub-<sub_id>_ses-<ses_id>_cam-<cam_id>.mp4``.  If the video is
    not already encoded as H.264 + yuv420p in an ``.mp4`` container, it
    is re-encoded with ffmpeg before saving.

    Parameters
    ----------
    input_video
        Path to the video to convert.
    output_video_dir
        Directory where the converted video will be written (created
        automatically if it does not exist).
    sub_id
        Subject ID used to build the output filename.
    ses_id
        Session ID used to build the output filename.
    cam_id
        Camera ID used to build the output filename.

    Returns
    -------
    Path
        Path to the saved ``.mp4`` file.

    Raises
    ------
    RuntimeError
        If ffmpeg is not available on the system PATH.
    """
    _check_ffmpeg()

    output_video = (
        Path(output_video_dir) / f"sub-{sub_id}_ses-{ses_id}_cam-{cam_id}.mp4"
    )
    Path(output_video_dir).mkdir(parents=True, exist_ok=True)

    if not _needs_reencoding(input_video):
        shutil.copy(input_video, output_video)
    else:
        _reencode_video(input_video, output_video)

    return output_video


def _check_ffmpeg() -> None:
    """Check ffmpeg is available and can be executed."""
    if not _is_ffmpeg_available():
        raise RuntimeError("ffmpeg is required but not found")
    sio.set_default_video_plugin("ffmpeg")


def _needs_reencoding(input_video_path: str | Path) -> bool:
    """Check if reencoding is required for input video."""
    input_video_path = Path(input_video_path)
    logging.info(f"Input video: {input_video_path}")

    if input_video_path.suffix.lower() != EXPECTED_SUFFIX:
        return True

    encoding = _get_codec_pixelformat(input_video_path)
    if encoding != EXPECTED_ENCODING:
        logging.info(
            f"Video encoding ({encoding}) does not match "
            f"the expected values ({EXPECTED_ENCODING}). "
            "The video will be reencoded."
        )
        return True
    return False


def _get_codec_pixelformat(
    input_video_path: str | Path,
) -> dict[str, str | None]:
    """Get relevant video encoding parameters as a dictionary.

    It wraps sleap-io's `_get_video_encoding_info`, which
    uses `ffmpeg -i` to extract metadata without requiring
    `ffprobe` to be in PATH.

    Notes
    -----
    `_get_video_encoding_info` returns a `VideoEncodingInfo`
    object with the following attributes:
    - codec: Video codec name (e.g., "h264", "hevc").
    - codec_profile: Codec profile (e.g., "Main", "High").
    - pixel_format: Pixel format (e.g., "yuv420p").
    - bitrate_kbps: Bitrate in kilobits per second.
    - fps: Frames per second.
    - gop_size: Group of pictures size (keyframe interval).
    - container: Container format (e.g., "mov", "avi").

    """
    info = _get_video_encoding_info(input_video_path)
    if info is None:
        raise RuntimeError(
            f"Could not read encoding info from {input_video_path}. "
            "Ensure ffmpeg is installed and the file is a valid video."
        )
    return {
        "codec": info.codec,
        "pixelformat": info.pixel_format,
    }


def _reencode_video(
    input_video_path: str | Path,
    output_video_path: str | Path,
) -> Path:
    """Reencode video to default format."""
    video = sio.load_video(Path(input_video_path))
    reencoded_video_path = sio.save_video(
        video,
        filename=output_video_path,
        fps=video.fps,
        **REENCODING_PARAMS,
    )
    logging.info(f"Re-encoded video saved to {reencoded_video_path}")
    return reencoded_video_path


def frames_to_poseinterface(
    input_dir: Path,
    output_dir: Path,
    framelabels_path: Path,
) -> None:
    """Copy and rename frame images to match filenames in COCO JSON.

    Source frames are matched to target names by frame number: the
    first group of digits in each source filename is compared against
    the ``frame-<ID>`` field in the COCO ``file_name`` entries.

    Parameters
    ----------
    input_dir
        Directory containing the source frame images (e.g. DLC
        ``labeled-data/<video>/`` folder).
    output_dir
        Directory to copy the renamed frames into.
    framelabels_path
        Path to a COCO JSON file whose ``images`` entries provide
        the target filenames.

    Raises
    ------
    FileNotFoundError
        If a source frame cannot be found for a frame number
        listed in the COCO JSON.
    """
    # Build a map from frame number to source image path
    source_frame_map: dict[int, Path] = {}
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        for img_path in input_dir.glob(ext):
            match = re.search(r"(\d+)", img_path.stem)
            if match:
                source_frame_map[int(match.group(1))] = img_path

    if not source_frame_map:
        raise FileNotFoundError(f"No image files found in {input_dir}")

    with open(framelabels_path) as f:
        coco_data = json.load(f)

    missing_frames = []
    for img in coco_data["images"]:
        target_filename = img["file_name"]
        frame_number = _extract_frame_number(target_filename)
        if frame_number not in source_frame_map:
            missing_frames.append(target_filename)
            continue
        target_path = output_dir / target_filename
        if not target_path.exists():
            shutil.copy2(source_frame_map[frame_number], target_path)

    if missing_frames:
        missing = "\n".join(f"  {f}" for f in missing_frames)
        warnings.warn(
            f"{len(missing_frames)} frame(s) not found in {input_dir} "
            f"and were skipped:\n{missing}",
            UserWarning,
            stacklevel=2,
        )


def predictions_to_poseinterface(
    input_path: Path | str,
    video_path: Path | str,
    output_dir: Path | str,
    *,
    sub_id: str,
    ses_id: str,
    cam_id: str,
) -> Path:
    """Convert a prediction file to ``poseinterface`` COCO JSON format.

    This function reads predictions for a given video and writes the
    corresponding "video-level" COCO JSON labels in the ``poseinterface``
    format, (i.e. a
    ``sub-<sub_id>_ses-<ses_id>_cam-<cam_id>_videolabels.json`` file).

    The output JSON file is meant to facilitate the extraction of "clip-level"
    labels, (i.e. files of the format
    ``sub-<sub_id>_ses-<ses_id>_cam-<cam_id>_start-<frame_id>_dur-<n_frames>_cliplabels.json``).

    Parameters
    ----------
    input_path
        Path to the predictions file. It should be one of the formats
        supported by ``movement`` (see `movement supported formats`_)
    video_path
        Path to the corresponding video file.  Used to attach video
        metadata (resolution) to the COCO output.
    output_dir
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

    Notes
    -------
    For the full list of supported formats for the input file, see
    `movement supported formats`_.

    .. _movement supported formats:
       https://movement.neuroinformatics.dev/dev/user_guide/input_output.html#supported-third-party-formats


    """
    # Read input file as movement dataset
    # NOTE: fps=None is ignore with NWB files
    ds = load_dataset(
        file=input_path,
        source_software="auto",  # infer from validators
        fps=None,
    )

    # Read video object
    video_path = Path(video_path)
    if not video_path.is_file():
        raise FileNotFoundError(
            f"Input video file does not exist: {video_path}"
        )
    video = sio.load_video(video_path)

    # Get video image width and height
    if video.shape is None:
        raise ValueError(f"Could not extract video shape from {video_path}. ")
    _, img_h, img_w, _ = video.shape

    # Convert movement dataset to videolabels dict
    coco_data = _convert_movement_ds_to_videolabels(
        ds,
        sub_id=sub_id,
        ses_id=ses_id,
        cam_id=cam_id,
        img_h=img_h,
        img_w=img_w,
    )

    # Export dict as JSON
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_json_path = (
        output_dir / f"sub-{sub_id}_ses-{ses_id}_cam-{cam_id}_videolabels.json"
    )
    with open(output_json_path, "w") as f:
        json.dump(coco_data, f)

    return output_json_path


def _convert_movement_ds_to_videolabels(
    ds: xr.Dataset,
    *,
    sub_id: str,
    ses_id: str,
    cam_id: str,
    img_w: int,
    img_h: int,
) -> dict[str, list[dict]]:
    """Convert predictions in movement dataset to videolabels dict."""
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
            "id": i,
            "name": name,
            "keypoints": keypoint_names,
            "skeleton": [],
        }
        for i, name in enumerate(individual_names, start=1)
    ]

    # Build images list (one entry per frame)
    # NOTE: image id values are always 0-indexed
    frame_idx_width = len(str(n_frames - 1))
    images = [
        {
            "id": t,
            "file_name": (
                f"sub-{sub_id}_ses-{ses_id}_cam-{cam_id}_frame-{t:0{frame_idx_width}d}"
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
            xy = positions[t, :, :, i].T  # (n_keypoints, 2)

            # Determine kpt visibility:
            # 0: not labeled
            # 1: labeled but not visible (occluded)
            # 2: labeled and visible
            # NOTE: The current code only assigns 0 or 2 because the movement
            # dataset doesn't carry occlusion information
            visible_array = ~np.isnan(xy[:, 0]) & ~np.isnan(
                xy[:, 1]
            )  # (n_keypoints,)
            n_visible = int(visible_array.sum())

            # Compute bbox from visible keypoints
            # (zeros if no keypoints are visible)
            if n_visible > 0:
                x_visible = xy[visible_array, 0]
                y_visible = xy[visible_array, 1]
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
                    "keypoints": coco.encode_keypoints(
                        np.c_[xy, visible_array]
                    ),  # returns flattened kpts [x1, y1, v1, x2, y2, v2, ...]
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


def split_lp_collected_data(
    input_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    """Split a Lightning Pose project-level CollectedData.csv into
    per-session CSVs.

    Lightning Pose stores labels for all sessions in a single project-level
    ``CollectedData.csv``, with full image paths (e.g.
    ``labeled-data/<session>/<image>.png``) as the row index.
    This function splits that file into one CSV per session, each formatted
    as a DLC-style ``CollectedData_<scorer>.csv`` with a three-level row
    MultiIndex ``(top_dir, session, image)``.  The resulting per-session
    files can be passed directly to
    :func:`poseinterface.io.annotations_to_poseinterface`.

    Parameters
    ----------
    input_path
        Path to the Lightning Pose project-level ``CollectedData.csv``.
    output_dir
        Parent directory for the per-session output CSVs. Each session is
        written to ``<output_dir>/<session>/CollectedData_<scorer>.csv``,
        mirroring the DLC ``labeled-data/`` layout.

    Returns
    -------
    dict[str, Path]
        Mapping from session name to the path of the per-session CSV.

    Raises
    ------
    ValueError
        If any row index entry cannot be parsed into exactly three path
        components ``(top_dir, session, image)``.

    Examples
    --------
    >>> from pathlib import Path
    >>> from poseinterface.io import split_lp_collected_data
    >>> session_csvs = split_lp_collected_data(
    ...     input_path=Path("path/to/CollectedData.csv"),
    ...     output_dir=Path("path/to/labeled-data"),
    ... )
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)

    # Read LP CSV: 3-row column MultiIndex header, single-path row index.
    # pandas uses the first element of each header row as the column level
    # name (scorer, bodyparts, coords), which is what we need for DLC output.
    df = pd.read_csv(input_path, header=[0, 1, 2], index_col=0)

    # Parse every row path and group by session (the middle path component)
    index_tuples: list[tuple[str, str, str]] = []
    session_order: list[str] = []
    for row_path in df.index:
        parts = _parse_lp_image_path(row_path)
        index_tuples.append(parts)
        session = parts[1]
        if session not in session_order:
            session_order.append(session)

    scorer = df.columns.get_level_values(0)[0]

    results: dict[str, Path] = {}
    for session_name in session_order:
        positions = [
            i
            for i, (_, ses, _) in enumerate(index_tuples)
            if ses == session_name
        ]
        session_df = df.iloc[positions].copy()
        session_df.index = pd.MultiIndex.from_tuples(
            [index_tuples[i] for i in positions]
        )

        session_dir = output_dir / session_name
        session_dir.mkdir(parents=True, exist_ok=True)
        output_path = session_dir / f"CollectedData_{scorer}.csv"
        session_df.to_csv(output_path)
        results[session_name] = output_path

    return results


def _parse_lp_image_path(path_str: str) -> tuple[str, str, str]:
    """Parse a Lightning Pose image path into ``(top_dir, session, image)``."""
    parts = Path(path_str.replace("\\", "/")).parts
    if len(parts) != 3:
        raise ValueError(
            f"Expected a path with exactly 3 components "
            f"(top_dir/session/image.png), got {len(parts)} in {path_str!r}."
        )
    return parts[0], parts[1], parts[2]
