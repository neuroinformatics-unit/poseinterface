"""Functions to extract clips from ``poseinterface`` videos."""

import argparse
import json
import logging
import sys
from pathlib import Path

import sleap_io as sio

from . import s3


def _validate_clip_request(start_frame: int, duration: int) -> None:
    if start_frame < 0:
        raise ValueError(
            f"start_frame must be non-negative, got {start_frame}"
        )
    if duration <= 0:
        raise ValueError(f"duration must be positive, got {duration}")


def extract_single_clip(
    video_path: str | Path,
    duration: int,
    start_frame: int,
) -> tuple[Path, Path | None]:
    """Extract a video clip (and its clip labels if available).

    Reads the source video and saves a ``.mp4`` clip to a ``Clips/``
    subdirectory next to the source video. If a sibling
    ``*_videolabels.json`` file exists (holding labels for the entire
    session video, using the same schema as ``cliplabels.json``), a
    matching ``_cliplabels.json`` containing only the annotations within
    the requested frame range is also written.

    Parameters
    ----------
    video_path
        Path to the input ``.mp4`` video. The filename should follow
        the convention ``sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4``, and
        if a sibling labels file exists, its filename should be
        ``sub-<subjectID>_ses-<sessionID>_cam-<camID>_videolabels.json``.
    duration
        Number of frames to include in the clip.  If ``start_frame +
        duration`` exceeds the video length, the duration is clamped to the
        remaining frames and a warning is logged.
    start_frame
        Index of the first frame to include in the clip (0-based).

    Returns
    -------
    clip_path : Path
        Path to the output clip file.
    clip_json : Path | None
        Path to the ``_cliplabels.json`` file for the clip if extracted,
        None otherwise.

    Raises
    ------
    ValueError
        If ``start_frame`` is negative or ``duration`` is not positive.

    Notes
    -----
    This function optionally consumes a ``*_videolabels.json`` file, sibling
    to the input video file and holding labels for the entire video. This
    file is an intermediate cache useful for data contributors: it follows
    the same schema as ``cliplabels.json`` but it refers to the full video,
    rather than to a clip of it. The ``*_videolabels.json`` file is not part
    of the published benchmark dataset. For further details, see the
    "Intermediate file: `videolabels.json`" section of the benchmark
    dataset specification.

    This function assumes that the ``id`` field in the ``images`` list of the
    source ``*_videolabels.json`` corresponds to 0-based global frame indices
    of the full video.
    """
    _validate_clip_request(start_frame, duration)

    # Create "Clips" directory if it doesn't exist
    video_path = Path(video_path)
    clips_dir = video_path.parent / "Clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # Read video as array
    video = sio.load_video(video_path)
    logging.info(
        f"filename: {video_path.name}, fps: {video.fps}, shape: {video.shape}"
    )

    # Clamp duration if it exceeds the video length
    if start_frame + duration > video.shape[0]:
        duration = video.shape[0] - start_frame
        logging.warning(
            "Clip exceeds video length. "
            f"Clamping duration to {duration} frames."
        )

    # Slice clip and save as mp4
    clip = video[start_frame : start_frame + duration]
    clip_path = (
        clips_dir / f"{video_path.stem}_start-{start_frame}_dur-{duration}.mp4"
    )
    sio.save_video(clip, clip_path, fps=video.fps)

    # Generate cliplabels.json only if a companion videolabels.json file exists
    video_json = video_path.parent / f"{video_path.stem}_videolabels.json"
    if video_json.exists():
        clip_json = _extract_cliplabels(
            video_path, clips_dir, start_frame, duration
        )
        logging.info(
            f"Extracted clip {clip_path.name} with labels {clip_json.name} "
            f"({duration} frames from start_frame={start_frame})."
        )
    else:
        clip_json = None
        logging.info(
            f"Extracted clip {clip_path.name} "
            f"({duration} frames from start_frame={start_frame}). "
            "No companion *_videolabels.json found; skipping label extraction."
        )

    return clip_path, clip_json


def extract_clips(
    video_path: Path,
    duration: int,
    start_frames: list[int],
) -> list[tuple[Path, Path | None]]:
    """Extract multiple clips from a video.

    Parameters
    ----------
    video_path
        Path to the input ``.mp4`` video. See :func:`extract_clip` for
        naming conventions.
    duration
        Number of frames per clip, common to all clips.
    start_frames
        Start frame indices (0-based) for each clip.

    Returns
    -------
    list[tuple[Path, Path | None]]
        One ``(clip_path, clip_json)`` tuple per extracted clip, in the
        same order as ``start_frames``. ``clip_json`` is ``None`` when no
        sibling ``*_videolabels.json`` file exists.
    """
    # duration and start_frame validated in
    # each call to extract_single_clip()
    return [
        extract_single_clip(video_path, duration, sf) for sf in start_frames
    ]


def extract_clips_uniform(
    video_path: Path,
    duration: int,
    num_clips: int,
) -> list[tuple[Path, Path | None]]:
    """Extract clips with uniformly spaced starting frames from a video.

    Clips are guaranteed to be fully within the video, but clips
    may overlap when ``duration > (total_n_frames - duration) / num_clips``.

    Parameters
    ----------
    video_path
        Path to the input ``.mp4`` video. See :func:`extract_single_clip` for
        naming conventions.
    duration
        Number of frames per clip.
    num_clips
        Number of clips to extract, spaced evenly across the video via
        :func:`_uniform_start_frames`.

    Returns
    -------
    list[tuple[Path, Path | None]]
        See :func:`extract_clips`.
    """
    n_frames = sio.load_video(Path(video_path)).shape[0]
    start_frames = _uniform_start_frames(num_clips, duration, n_frames)
    return extract_clips(video_path, duration, start_frames)


def _uniform_start_frames(
    num_clips: int, duration: int, n_frames: int
) -> list[int]:
    """Compute uniformly spaced clip start frames.

    Starts frames are spread evenly over [0, n_frames - duration]
    so every clip of length `duration` fits within the video.

    Parameters
    ----------
    num_clips
        Number of clips to extract.
    duration
        Length of each clip in frames.
    n_frames
        Total number of frames in the video.

    Returns
    -------
    list[int]
        Sorted list of ``num_clips`` start frames.

    Raises
    ------
    ValueError
        If ``num_clips`` is not positive or ``duration`` exceeds
        ``n_frames``.
    """
    if num_clips <= 0:
        raise ValueError(f"num_clips must be positive, got {num_clips}")
    if duration > n_frames:
        raise ValueError(
            f"duration ({duration}) exceeds video length ({n_frames})"
        )
    step = (n_frames - duration) / num_clips
    return [round(i * step) for i in range(num_clips)]


def _extract_cliplabels(
    video_path: Path, clips_dir: Path, start_frame: int, duration: int
) -> Path:
    """Extract clip labels from the sibling *_videolabels.json file."""
    # Read file with labels for the whole video
    video_json = video_path.parent / f"{video_path.stem}_videolabels.json"
    with open(video_json) as f:
        video_labels = json.load(f)

    # Compute clip end frame
    end_frame = start_frame + duration

    # Keep only data from the images in the clip, re-indexing ids to be
    # 0-based within the clip. file_name is left untouched to retain in it
    # the global (video-based) frame index
    clip_labels = {}
    clip_labels["images"] = [
        {
            **img,
            "id": img["id"] - start_frame,  # overwrite id
        }
        for img in video_labels["images"]
        if start_frame <= img["id"] < end_frame
    ]

    # Keep only annotations within the clip, remapping image_id to the local
    # (clip-based) frame index, and renumbering annotation ids to be 1-based
    # within the clip.
    clip_labels["annotations"] = [
        {
            **annot,
            "image_id": annot["image_id"] - start_frame,  # overwrite image_id
            "id": new_id,
        }
        for new_id, annot in enumerate(
            (
                ant
                for ant in video_labels["annotations"]
                if start_frame <= ant["image_id"] < end_frame
            ),  # generator lazily yields only annotations within the clip
            start=1,  # annotation ids are 1-based within clip
        )
    ]
    # pass categories unchanged
    clip_labels["categories"] = video_labels["categories"]

    # Save json with filtered data to clips directory
    clip_json = (
        clips_dir / f"{video_path.stem}_"
        f"start-{start_frame}_dur-{duration}_cliplabels.json"
    )
    with open(clip_json, "w") as f:
        json.dump(clip_labels, f)

    return clip_json


def _suffix_error(name: str, suffix: str) -> str:
    return f"File must end with '{suffix}', got {name}"


def _extract_startlabels_from_dict(clip_labels: dict) -> dict:
    start_images = [img for img in clip_labels["images"] if img["id"] == 0]
    if len(start_images) != 1:
        raise ValueError(
            "Clip labels must contain exactly one first-frame image with id 0"
        )

    return {
        "images": start_images,
        "annotations": [
            annot
            for annot in clip_labels["annotations"]
            if annot["image_id"] == 0
        ],
        "categories": clip_labels["categories"],
    }


def extract_startlabels(
    cliplabels_path: str | Path, output_path: str | Path | None = None
) -> Path:
    """Extract only the first frame's labels from a cliplabels.json file.

    Reads a ``*_cliplabels.json`` file and creates a corresponding
    ``*_startlabels.json`` file containing only the labels for the first
    frame (frame with id=0).

    Parameters
    ----------
    cliplabels_path
        Path to the input ``*_cliplabels.json`` file.
    output_path
        Path to the output ``*_startlabels.json`` file. If ``None``
        (default), it is derived from ``cliplabels_path`` by replacing
        ``_cliplabels.json`` with ``_startlabels.json``.

    Returns
    -------
    Path
        Path to the output ``*_startlabels.json`` file.

    Raises
    ------
    FileNotFoundError
        If the input file does not exist.
    ValueError
        If the input filename does not end with ``_cliplabels.json``,
        ``output_path`` does not end with ``_startlabels.json``, or the
        clip labels do not contain exactly one first-frame image (``id: 0``).
    """
    cliplabels_path = Path(cliplabels_path)

    # Validate input file exists
    if not cliplabels_path.exists():
        raise FileNotFoundError(f"Input file not found: {cliplabels_path}")

    # Validate input filename
    if not cliplabels_path.name.endswith("_cliplabels.json"):
        raise ValueError(
            _suffix_error(cliplabels_path.name, "_cliplabels.json")
        )

    # Read the cliplabels file
    with open(cliplabels_path) as f:
        clip_labels = json.load(f)

    start_labels = _extract_startlabels_from_dict(clip_labels)

    # Generate output path by replacing _cliplabels.json with _startlabels.json
    if output_path is None:
        output_path = cliplabels_path.parent / cliplabels_path.name.replace(
            "_cliplabels.json", "_startlabels.json"
        )
    else:
        output_path = Path(output_path)
        if not output_path.name.endswith("_startlabels.json"):
            raise ValueError(
                _suffix_error(output_path.name, "_startlabels.json")
            )

    # Save the start labels
    with open(output_path, "w") as f:
        json.dump(start_labels, f)

    logging.info(
        f"Extracted start frame labels from {cliplabels_path.name} "
        f"to {output_path.name}"
    )

    return output_path


def extract_startlabels_s3(
    s3_cliplabels_uri: str,
    output_uri: str | None = None,
    aws_profile: str | None = None,
) -> str:
    """Extract first frame's labels from a cliplabels.json file on S3.

    Reads a ``*_cliplabels.json`` file from S3 and creates a corresponding
    ``*_startlabels.json`` file on S3 containing only the labels for the first
    frame (frame with id=0).

    Parameters
    ----------
    s3_cliplabels_uri
        S3 URI of the input ``*_cliplabels.json`` file in the format
        ``s3://bucket-name/path/to/file_cliplabels.json``.
    output_uri
        Optional S3 URI for the output file. If ``None`` (default), it is
        derived from the ``s3_cliplabels_uri`` by replacing
        ``_cliplabels.json`` with ``_startlabels.json``.
    aws_profile
        Optional AWS profile name to use for authentication. If None, uses
        the default AWS credentials chain.

    Returns
    -------
    str
        S3 URI of the output ``*_startlabels.json`` file.

    Raises
    ------
    ValueError
        If the S3 URI format is invalid, the input filename does not end
        with ``_cliplabels.json``, ``output_uri`` does not end with
        ``_startlabels.json``, or the clip labels do not contain exactly
        one first-frame image (``id: 0``).
    FileNotFoundError
        If the input file does not exist on S3.
    ClientError
        If there are other S3 access issues (e.g. permissions).
    """
    # Parse S3 URI and validate filename
    bucket_name, key = s3.parse_s3_uri(s3_cliplabels_uri)
    if not key.endswith("_cliplabels.json"):
        raise ValueError(_suffix_error(key, "_cliplabels.json"))

    # Download cliplabels from S3
    clip_labels = s3.download_json_from_s3(bucket_name, key, aws_profile)

    # Extract start labels using local function
    start_labels = _extract_startlabels_from_dict(clip_labels)

    # Generate output key/URI if not provided
    if output_uri is None:
        output_key = key.replace("_cliplabels.json", "_startlabels.json")
        output_uri = f"s3://{bucket_name}/{output_key}"
    else:
        _, output_key = s3.parse_s3_uri(output_uri)
        if not output_key.endswith("_startlabels.json"):
            raise ValueError(_suffix_error(output_key, "_startlabels.json"))

    # Upload start labels to S3
    s3.upload_json_to_s3(start_labels, bucket_name, output_key, aws_profile)

    logging.info(f"Extracted start frame labels from {key} to {output_key}")

    return output_uri


def main(args: argparse.Namespace) -> None:
    """Run multi-clip extraction from parsed command-line arguments."""
    try:
        if args.sampling == "uniform":
            if args.num_clips is None:
                raise SystemExit(
                    "error: --num_clips is required when --sampling uniform"
                )
            extract_clips_uniform(
                args.video_path, args.duration, args.num_clips
            )
        elif args.sampling == "manual":
            if not args.start_frames:
                raise SystemExit(
                    "error: --start_frames is required when --sampling manual"
                )
            extract_clips(args.video_path, args.duration, args.start_frames)
    except ValueError as e:
        raise SystemExit(f"error: {e}")


def parse_args(args: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for multi-clip extraction.

    Parameters
    ----------
    args
        List of command-line argument strings (e.g. ``sys.argv[1:]``).

    Returns
    -------
    argparse.Namespace
        Parsed arguments with attributes ``video_path`` (str),
        ``duration`` (int), ``sampling`` (str), ``num_clips``
        (int | None), and ``start_frames`` (list[int] | None).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Extract multiple clips from a video (and corresponding "
            "clip labels if available)."
        )
    )
    parser.add_argument(
        "--video_path",
        type=str,
        required=True,
        help="Path to video file to clip. The filename should follow "
        "the convention ``sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4``, "
        "and if a sibling labels file exists, its filename should be "
        "``sub-<subjectID>_ses-<sessionID>_cam-<camID>_videolabels.json``.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        required=True,
        help="Number of frames per clip.",
    )
    parser.add_argument(
        "--sampling",
        type=str,
        required=True,
        choices=["uniform", "manual"],
        help=(
            "Clip selection strategy. "
            "'uniform': evenly space clips across the video "
            "(requires --num_clips). "
            "'manual': use explicit start frames "
            "(requires --start_frames)."
        ),
    )
    parser.add_argument(
        "--num_clips",
        type=int,
        default=None,
        help="Number of clips to extract. Required when --sampling uniform.",
    )
    parser.add_argument(
        "--start_frames",
        type=int,
        nargs="+",
        default=None,
        help=(
            "Start frame indices (0-based, space-separated). "
            "Required when --sampling manual."
        ),
    )
    return parser.parse_args(args)


def wrapper() -> None:
    """Entry point for the ``extract-clips`` console script."""
    args = parse_args(sys.argv[1:])
    main(args)


if __name__ == "__main__":
    wrapper()
