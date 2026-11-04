import argparse
import sys
from pathlib import Path

import numpy as np
import torch

from poseinterface.trackers import PointTracker


class CoTracker3(PointTracker):
    def __init__(
        self, model_name: str = "cotracker3_offline", device: str = "cpu"
    ) -> None:
        """Load model and place in device.

        Parameters
        ----------
        model_name : str, optional
            Model names as described in https://github.com/facebookresearch/co-tracker/blob/main/hubconf.py.
            By default "cotracker3_offline"
        device : str, optional
            Usual options are 'cuda', 'cpu', and 'mps'. By default 'cpu'.
            Full description at https://docs.pytorch.org/docs/2.15/tensor_attributes.html#torch.device
        """
        self.device = torch.device(device)
        self.model = torch.hub.load(
            "facebookresearch/co-tracker",
            model_name,
            # Skip the GitHub API call that checks the repo isn't a fork:
            # it's rate-limited for unauthenticated requests (60/h per IP).
            skip_validation=True,
            trust_repo=True,
        ).to(self.device)

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
        video = self.load_video(video_path)  # (T, H, W, 3)
        queries = self.load_queries(startlabels_path)  # (N, 3) as (t, x, y)

        video_tensor = (
            torch.from_numpy(video).permute(0, 3, 1, 2)[None].float()
        ).to(self.device)  # (B, T, 3, H, W)
        queries_tensor = (
            torch.from_numpy(queries).float()[None].to(self.device)
        )  # (B, N, 3)

        pred_tracks, pred_visibility = self.model(
            video=video_tensor,
            queries=queries_tensor,
        )  # (B, T, N, 2), (B, T, N)

        return (
            pred_tracks[0].cpu().numpy(),
            pred_visibility[0].cpu().numpy(),
        )


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
    parser.add_argument("--model-name", default="cotracker3_offline")
    parser.add_argument("--device", default="cpu")

    return parser.parse_args(args)


def main(args: argparse.Namespace) -> None:
    tracker = CoTracker3(args.model_name, args.device)
    output_path = tracker.run(
        args.video,
        args.startlabels,
        args.output_dir,
        format=args.format,
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main(parse_args(sys.argv[1:]))
