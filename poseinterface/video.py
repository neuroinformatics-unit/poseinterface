import argparse
import logging
import sys
from pathlib import Path

import sleap_io as sio
from sleap_io.io.cli import _get_video_encoding_info, _is_ffmpeg_available
from sleap_io.model.video import Video

# from poseinterface.io import annotations_to_coco

# Check FFMPEG availability
sio.set_default_video_plugin("ffmpeg")
if not _is_ffmpeg_available():
    raise RuntimeError("ffmpeg is required but not found")

# We support MediaVideo files
SUPPORTED_EXTS = [".mp4", ".avi", ".mov", ".mkv", ".mj2"]

EXPECTED_ENCODING = {
    "pixelformat": "yuv420p",
    "codec": "libx264",
    "container": "mp4",
    # REENCODING PARAMETERS:
    "crf": 25,
    "preset": "superfast",
}


def read_video(input_video_path: str | Path) -> Video:
    "A wrapper around sleap-io load_video"
    input_path = check_reencoding(Path(input_video_path))
    video = sio.load_video(input_path)
    logging.info(
        f"filename: {input_path.name}, fps: {video.fps}, shape: {video.shape}"
    )
    return video


def check_reencoding(input_video_path: str | Path) -> Video:
    """Check encoding info and log if reencoding is required."""
    logging.info(f"Input video: {input_video_path}")
    encoding = get_video_encoding_info(input_video_path)

    expected_encoding = {k: EXPECTED_ENCODING[k] for k in encoding}
    if encoding != expected_encoding:
        raise RuntimeError(
            f"Video encoding {encoding} does not match "
            f"expected {EXPECTED_ENCODING}. Please reencode "
            "using the `reencode_video()` function."
        )
    else:
        return input_video_path


def extract_clip(
    video: Video,
    start_frame: int,
    duration: int,
):
    """Extract clip from input video.

    start_frame is 0-based index. Duration is len(clip).

    We assume the video filename is in the format
    sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4.
    """
    # Clip video
    clip = video[start_frame : start_frame + duration]

    # Set clip name
    output_path = f"{video.filename}_start-{start_frame}_dur-{duration}.mp4"

    # Save clip
    encoding_params = {
        ky: val for ky, val in EXPECTED_ENCODING.items() if ky != "container"
    }
    sio.save_video(clip, output_path, fps=video.fps, **encoding_params)

    # Generate clip labels from predictions ???
    # annotations_to_coco

    return output_path


def reencode_video(
    input_video_path: str | Path,
    overwrite: bool,
) -> Path:
    """Reencode video to default format."""

    # Read video
    input_video_path = Path(input_video_path)
    video = sio.load_video(input_video_path)

    # Compute output filenamename
    if not overwrite:
        output_video_path = (
            input_video_path.stem + "_reencoded" + input_video_path.suffix
        )

    # Save reencoded video
    reencoded_video_path = sio.save_video(
        video,
        filename=output_video_path,
        fps=video.fps,
        **EXPECTED_ENCODING,
    )
    logging.info(f"Re-encoded video saved to {reencoded_video_path}")
    return reencoded_video_path


def get_video_encoding_info(input_video_path: str | Path) -> dict:
    """Get video encoding parameters as dictionary.

    It wraps sleap-io's _get_video_encoding_info, which
    uses `ffmpeg -i` to extract metadata without requiring ffprobe in PATH.

    `_get_video_encoding_info` returns a VideoEncodingInfo object
    with attributes:
      codec: Video codec name (e.g., "h264", "hevc").
      codec_profile: Codec profile (e.g., "Main", "High").
      pixel_format: Pixel format (e.g., "yuv420p").
      bitrate_kbps: Bitrate in kilobits per second.
      fps: Frames per second.
      gop_size: Group of pictures size (keyframe interval).
      container: Container format (e.g., "mov", "avi").

    """
    info = _get_video_encoding_info(input_video_path)
    return {
        "codec": info.codec,
        "pixelformat": info.pixel_format,
        "container": info.container,
    }


def main(args: argparse.Namespace):
    video = read_video(args.video_path)
    extract_clip(video, args.start_frame, args.duration)


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
        require=True,
        help="Start frame of the clip as a 0-based index.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        required=True,
        help="Total length of the output clip in frames",
    )
    parser.add_argument(
        "--annotations_path",
        type=str,
        required=False,
        help="Path to the video annotations file.",
    )
    return parser.parse_args(args)


def wrapper():
    args = parse_args(sys.argv[1:])
    main(args)


if __name__ == "__main__":
    wrapper()
