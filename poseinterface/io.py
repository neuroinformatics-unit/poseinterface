"""Functions to convert annotations and videos to ``poseinterface`` format."""

import copy
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Literal, TypeAlias

import sleap_io as sio
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
        logging.warning(
            f"Video encoding {encoding} does not match "
            f"expected {EXPECTED_ENCODING}. Please reencode "
            "using the `reencode_video()` function."
        )
        return True
    return False


def _get_codec_pixelformat(input_video_path: str | Path) -> dict[str, str]:
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
