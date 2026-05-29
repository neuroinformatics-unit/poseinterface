"""Functions to extract clips from ``poseinterface`` videos."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import sleap_io as sio


def extract_clip(
    video_path: str | Path,
    start_frame: int,
    duration: int,
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
    start_frame
        Index of the first frame to include in the clip (0-based).
    duration
        Number of frames to include in the clip.  If ``start_frame +
        duration`` exceeds the video length, the duration is clamped to the
        remaining frames and a warning is logged.

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
    # Check input values
    if start_frame < 0:
        raise ValueError(
            f"start_frame must be non-negative, got {start_frame}"
        )
    if duration <= 0:
        raise ValueError(f"duration must be positive, got {duration}")

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
    sampling: str,
    **kwargs: Any,
) -> list[tuple[Path, Path | None]]:
    """Extract multiple clips from a video.

    Parameters
    ----------
    video_path
        Path to the input ``.mp4`` video. See :func:`extract_clip` for
        naming conventions.
    duration
        Number of frames per clip.
    sampling
        Strategy used to select clip start frames. Supported values:

        ``"manual"``
            Use explicitly provided start frames. Requires the
            ``start_frames`` keyword argument (``list[int]``).
        ``"uniform"``
            Space clips evenly across the video. Requires the
            ``num_clips`` keyword argument (``int``). Start frames are
            computed with :func:`_uniform_start_frames`.

    **kwargs
        Additional arguments required by the chosen sampling strategy
        (see above).

    Returns
    -------
    list[tuple[Path, Path | None]]
        One ``(clip_path, clip_json)`` tuple per extracted clip, in the
        same order as the start frames. ``clip_json`` is ``None`` when no
        sibling ``*_videolabels.json`` file exists.

    Raises
    ------
    ValueError
        If ``sampling`` is not a recognised strategy, or if a required
        keyword argument for the chosen strategy is missing.
    """
    if sampling == "manual":
        if "start_frames" not in kwargs:
            raise ValueError(
                "sampling='manual' requires the start_frames keyword argument"
            )
        start_frames = list(kwargs["start_frames"])
    elif sampling == "uniform":
        if "num_clips" not in kwargs:
            raise ValueError(
                "sampling='uniform' requires the num_clips keyword argument"
            )
        n_frames = sio.load_video(Path(video_path)).shape[0]
        start_frames = _uniform_start_frames(
            int(kwargs["num_clips"]),
            duration,
            n_frames,
        )
    else:
        raise ValueError(
            f"Unknown sampling strategy {sampling!r}. "
            "Supported strategies: 'manual', 'uniform'."
        )

    return [extract_clip(video_path, sf, duration) for sf in start_frames]


def _uniform_start_frames(
    num_clips: int, duration: int, n_frames: int
) -> list[int]:
    """Compute uniformly spaced clip start frames.

    The first clip starts at frame 0 and the last starts at
    ``n_frames - duration``, with the remaining clips evenly distributed
    in between.

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
    max_start = n_frames - duration
    if max_start < 0:
        raise ValueError(
            f"duration ({duration}) exceeds video length ({n_frames})"
        )
    if num_clips == 1:
        return [0]
    step = max_start / (num_clips - 1)
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


def main(args: argparse.Namespace) -> None:
    """Run clip extraction from parsed command-line arguments.

    Parameters
    ----------
    args
        Parsed arguments containing ``video_path``, ``start_frame``,
        and ``duration``.
    """
    # Extract clip
    extract_clip(args.video_path, args.start_frame, args.duration)


def parse_args(args: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for clip extraction.

    Parameters
    ----------
    args
        List of command-line argument strings (e.g. ``sys.argv[1:]``).

    Returns
    -------
    argparse.Namespace
        Parsed arguments with attributes ``video_path`` (str),
        ``start_frame`` (int), and ``duration`` (int).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Extract clips from video (and corresponding "
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
        "--start_frame",
        type=int,
        required=True,
        help="Start frame of the clip as a 0-based index.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        required=True,
        help="Total length of the output clip in frames",
    )
    return parser.parse_args(args)


def wrapper() -> None:
    """Entry point for the ``extract-clip`` console script."""
    args = parse_args(sys.argv[1:])
    main(args)


if __name__ == "__main__":
    wrapper()
