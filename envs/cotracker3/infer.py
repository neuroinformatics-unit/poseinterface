import argparse
import sys
from pathlib import Path

import imageio.v3 as iio
import numpy as np
import torch

from poseinterface.io import load_cliplabels
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
        self.model = torch.hub.load(
            "facebookresearch/co-tracker",
            model_name,
        ).to(device)

    def track(
        self,
        video_path: Path | str,
        startlabels_path: Path | str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Track video.

        Parameters
        ----------
        video_path : Path | str
            Path to video to track.
        startlabels_path : Path | str
            Path to startlabels json.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            _description_
        """
        # Get model's device
        device = self.model.device

        # Read video as numpy array
        video = iio.imread(video_path, plugin="FFMPEG")  # (T, H, W, 3)

        # Put video as torch tensor in expected shape and on device
        video_tensor = (
            torch.tensor(video).permute(0, 3, 1, 2)[None].float().to(device)
        )  # B, T, 3, H, W

        # ----------------
        # Read queries as numpy array
        # in: json
        # out: A numpy array of shape (N, 3) in format (t, x, y)
        queries_from_coco = load_cliplabels(startlabels_path)
        # for startlabels and one animal:
        # (n_frames=1, n_instances=1, n_keypoints, 2)
        n_frames, n_instances, n_keypoints, _ = queries_from_coco.shape

        # frame index broadcast to every
        # (frame, instance, keypoint) ->
        # (n_frames, n_instances, n_keypoints, 1)
        t = np.broadcast_to(
            np.arange(n_frames)[:, None, None, None],
            (n_frames, n_instances, n_keypoints, 1),
        )
        queries = np.concatenate(
            [
                t,
                queries_from_coco,
            ],
            axis=-1,  # (n_frames, n_instances, n_keypoints, 3)
        ).reshape(-1, 3)  # (N, 3) as (frame, x, y)

        # ----------------

        # Put queries as torch tensor in the right shape and device
        queries_tensor: torch.Tensor = (
            torch.from_numpy(queries).to(torch.float).to(device)
        )[None]  # B, N, 3; (3 == frame, x, y)

        # Run tracking
        pred_tracks, pred_visibility = self.model(
            video=video_tensor,
            queries=queries_tensor,
        )  # B, T, N, 2;  B, T, N, 1

        # Get right shape and to cpu
        pred_tracks = pred_tracks[0].cpu().numpy()  # (T, N, 2),
        pred_visibility = pred_visibility[0].cpu().numpy()  # (T, N) -- ok?

        return pred_tracks, pred_visibility

    def write_cliplabels(
        pred_tracks,
        pred_visibility,
        output_dir: Path | str,
    ) -> Path:
        """Format output from cotracker as cliplabels.json."""
        # save pred_tracks, pred_visibility to a cliplabels.json
        # Derive filename from startlabels, or pass output file?
        raise NotImplementedError


def parse_args(args: list[str]) -> argparse.Namespace:
    # shared across trackers: --startlabels, --video, --out
    # tool-specific: --model-name, --device
    raise NotImplementedError


def main(args: argparse.Namespace) -> None:
    tracker = CoTracker3(args.model_name, args.device)

    pred_tracks, pred_visibility = tracker.track(
        args.video,
        args.startlabels,
    )

    # TODO: write results to a cliplabels file
    # using write_cliplabels method?
    # write_cliplabels(pred_tracks, pred_visibility,
    # output_dir=args.output_dir)


if __name__ == "__main__":
    main(parse_args(sys.argv[1:]))
