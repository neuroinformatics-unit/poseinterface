import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from huggingface_hub import hf_hub_download
from tapnet.tapnextpp.votsp2026.model import TAPNextPP

from poseinterface.trackers import PointTracker


class TAPNet(PointTracker):
    def __init__(
        self, model_name: str = "tapnextpp_256", device: str = "cpu"
    ) -> None:
        """Load model and place in device.

        Parameters
        ----------
        model_name : str, optional
            ...
        device : str, optional
            Usual options are 'cuda', 'cpu', and 'mps'. By default 'cpu'.
            Full description at https://docs.pytorch.org/docs/2.15/tensor_attributes.html#torch.device
        """
        # Get internal model name and resolution
        if model_name == "tapnextpp_256":
            self.model_name = "tapnextpp_ckpt.pt"
            model_resolution = 256
        elif model_name == "tapnextpp_512":
            self.model_name = "tapnextpp_512.ckpt"
            model_resolution = 512

        # Download model via HF hub
        checkpoint_path = hf_hub_download(
            repo_id="google/tapnet", filename=self.model_name
        )

        self.model = TAPNextPP.from_checkpoint(
            checkpoint_path, device=device, input_resolution=model_resolution
        )

        self.device = torch.device(device)

    def track(
        self,
        video_path: Path | str,
        startlabels_path: Path | str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Track the start-label keypoints through a video.

        Parameters
        ----------
        video_path : Path | str
            Path to the clip video.
        startlabels_path : Path | str
            Path to the clip's startlabels json.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Tracks of shape ``(T, N, 2)`` as ``(x, y)`` and visibility of
            shape ``(T, N)``.
        """
        video = self.load_video(video_path)  # (T, H, W, 3), RGB uint8
        queries = self.load_queries(startlabels_path)  # (N, 3) as (t, x, y)
        n_frames, n_queries = video.shape[0], queries.shape[0]

        # track_frame defines all queries on the first frame it receives
        if np.any(queries[:, 0] != 0):
            raise ValueError("TAPNext++ queries must all be on frame 0.")

        # track_frame takes numpy inputs (it handles resizing, normalising
        # and moving to device):
        # - frame: (H, W, 3) uint8 in **BGR**
        # - query points: (Q, 2) float32 as (x, y) in pixels of the frame
        video_bgr = video[..., ::-1]
        query_xy = queries[:, 1:].astype(np.float32)  # (N, 2)

        # Only track non-nan keypoints
        not_nan = ~np.isnan(query_xy).any(axis=1)  # (N,)

        # initialise output arrays
        tracks = np.full((n_frames, n_queries, 2), np.nan, dtype=np.float32)
        visibility = np.zeros((n_frames, n_queries), dtype=bool)

        # Online tracking (per frame)
        state = None
        for frame_i, frame in enumerate(video_bgr):
            positions, visible, state = self.model.track_frame(
                frame,
                # queries go in with the first frame only,
                # subsequent frames use the recurrent state
                query_points_xy=query_xy[not_nan] if frame_i == 0 else None,
                state=state,
            )  # (Q, 2) float32 as (x, y), (Q,) bool

            # fill in non-nan values in output arrays
            tracks[frame_i, not_nan] = positions
            visibility[frame_i, not_nan] = visible

        return tracks, visibility


def parse_args(args: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    # shared across trackers
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--startlabels", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to write the output json. Default: current directory.",
    )
    parser.add_argument(
        "--format",
        choices=["annotations", "predictions"],
        default="annotations",
        help="COCO annotations (PoseMark clip labels) or COCO predictions.",
    )

    # tool-specific
    parser.add_argument("--model-name", default="tapnextpp_256")
    parser.add_argument("--device", default="cpu")

    return parser.parse_args(args)


def main(args: argparse.Namespace) -> None:
    tracker = TAPNet(args.model_name, args.device)
    output_path = tracker.run(
        args.video,
        args.startlabels,
        args.output_dir,
        format=args.format,
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main(parse_args(sys.argv[1:]))
