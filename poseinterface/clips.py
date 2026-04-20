"""Functions to extract clips from poseinterface videos."""

import argparse
import json
import logging
import sys
from pathlib import Path

import sleap_io as sio


def extract_clip(
    video_path: str | Path,
    start_frame: int,
    duration: int,
) -> tuple[Path, Path]:
    """Extract a video clip and its corresponding clip labels.

    Reads the source video and its paired ``_cliplabels.json`` file, and saves
    to a ``Clips/`` subdirectory next to the source video: a ``.mp4`` clip, and
    a matching ``_cliplabels.json`` file containing only the annotations that
    fall within the requested frame range.

    Parameters
    ----------
    video_path
        Path to the input ``.mp4`` video.  The filename is expected to follow
        the convention ``sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4``
        and a sibling ``*_cliplabels.json`` file must exist.
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
    clip_json : Path
        Path to the ``_cliplabels.json`` file for the clip.

    Raises
    ------
    ValueError
        If ``start_frame`` is negative or ``duration`` is not positive.

    Notes
    -----
    This function assumes that the  ``id`` field in the ``images`` list of the
    source ``_cliplabels.json`` corresponds to 0-based global frame indices of
    the full video.
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

    # Generate cliplabels.json from the full video labels
    clip_json = _extract_cliplabels(
        video_path, clips_dir, start_frame, duration
    )

    return clip_path, clip_json


def _extract_cliplabels(video_path, clips_dir, start_frame, duration):
    """Extract clip labels from the video cliplabels.json file."""
    # Read file with labels for the whole video
    video_json = video_path.parent / f"{video_path.stem}_cliplabels.json"
    with open(video_json) as f:
        video_labels = json.load(f)

    # Keep only data from the images in the clip
    clip_labels = {}
    clip_labels["images"] = [
        img
        for img in video_labels["images"]
        if start_frame <= img["id"] < start_frame + duration
    ]
    clip_labels["annotations"] = [
        annot
        for annot in video_labels["annotations"]
        if start_frame <= annot["image_id"] < start_frame + duration
    ]
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
    parser = argparse.ArgumentParser(description="Extract clips from video")
    parser.add_argument(
        "--video_path",
        type=str,
        required=True,
        help="Path to video file to clip.",
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
