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
):
    """Extract clip and clip labels.

    We assume:
    - the input video filename is in the format
    `sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4`,
    - a `sub-<subjectID>_ses-<sessionID>_cam-<camID>_cliplabels.json`
    file with tracks for the full video exists alongside the input video,
    where the `id` in `images` corresponds to the global video frame 0-based
    indices (note that the local frame index and the global frame index is the
    same if the data refers to the whole video),
    - `start_frame` is 0-based index,
    - `duration` is len(clip).
    """
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
        clips_dir / f"{video.stem}_start-{start_frame}_dur-{duration}.mp4"
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


def main(args: argparse.Namespace):
    # Extract clip
    extract_clip(args.video_path, args.start_frame, args.duration)


def parse_args(args) -> argparse.Namespace:
    """Parse command-line arguments."""
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


def wrapper():
    args = parse_args(sys.argv[1:])
    main(args)


if __name__ == "__main__":
    wrapper()
