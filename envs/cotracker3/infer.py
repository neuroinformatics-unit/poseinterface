import argparse
import json
import re
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

        # Get right shape and to cpu
        pred_tracks = pred_tracks[0].cpu().numpy()  # (T, N, 2),
        pred_visibility = pred_visibility[0].cpu().numpy()  # (T, N) -- ok?

        return pred_tracks, pred_visibility

    @staticmethod
    def write_cliplabels(
        pred_tracks: np.ndarray,
        pred_visibility: np.ndarray,
        startlabels_path: Path | str,
        output_dir: Path | str,
    ) -> Path:
        """Write the output of :meth:`track` as a *PoseMark* cliplabels.json.

        Image metadata, categories and the output filename are derived from
        the startlabels file used as queries.

        Parameters
        ----------
        pred_tracks : np.ndarray
            Predicted positions, shape ``(T, N, 2)`` as ``(x, y)``, with
            ``N = n_instances * n_keypoints`` in the order of the
            startlabels annotations.
        pred_visibility : np.ndarray
            Predicted visibility, shape ``(T, N)``.
        startlabels_path : Path | str
            Path to the ``*_startlabels.json`` used for tracking.
        output_dir : Path | str
            Directory where the cliplabels file is written.

        Returns
        -------
        Path
            Path to the written ``*_cliplabels.json`` file.
        """
        startlabels_path = Path(startlabels_path)
        if not startlabels_path.name.endswith("_startlabels.json"):
            raise ValueError(
                f"Expected a '*_startlabels.json' file, got {startlabels_path}"
            )
        with open(startlabels_path) as f:
            startlabels = json.load(f)

        # Reference image (first frame of the clip)
        (start_image,) = startlabels["images"]
        prefix, start_str = re.fullmatch(
            r"(.*_frame-)(\d+)", start_image["file_name"]
        ).groups()
        start_frame = int(start_str)

        # Instances in file order, as stacked by load_cliplabels
        start_annots = [
            a
            for a in startlabels["annotations"]
            if a["image_id"] == start_image["id"]
        ]
        n_frames, n_points, _ = pred_tracks.shape
        n_instances = len(start_annots)
        n_keypoints = n_points // n_instances
        tracks = pred_tracks.reshape(n_frames, n_instances, n_keypoints, 2)
        visible = (
            np.asarray(pred_visibility)
            .astype(bool)
            .reshape(n_frames, n_instances, n_keypoints)
        )

        # Keypoints unlabelled in startlabels (v=0) are not tracked
        start_labelled = np.stack(
            [
                np.asarray(a["keypoints"]).reshape(-1, 3)[:, 2] > 0
                for a in start_annots
            ]
        )  # (n_instances, n_keypoints)

        frame_width = max(len(start_str), len(str(start_frame + n_frames - 1)))
        images = [
            {
                **start_image,
                "id": t,
                "file_name": f"{prefix}{start_frame + t:0{frame_width}d}",
            }
            for t in range(n_frames)
        ]

        annotations = []
        annot_id = 1
        for t in range(n_frames):
            for i, start_annot in enumerate(start_annots):
                xy = tracks[t, i]  # (n_keypoints, 2)
                labelled = start_labelled[i] & np.isfinite(xy).all(axis=1)
                # COCO visibility: 0 unlabelled, 1 occluded, 2 visible
                v = np.where(labelled, np.where(visible[t, i], 2, 1), 0)
                xy = np.where(labelled[:, None], xy, 0.0)

                if labelled.any():
                    x_min, y_min = xy[labelled].min(axis=0)
                    x_max, y_max = xy[labelled].max(axis=0)
                    bbox = [x_min, y_min, x_max - x_min, y_max - y_min]
                else:
                    bbox = [0.0, 0.0, 0.0, 0.0]
                bbox = [float(b) for b in bbox]

                annotation = {
                    "id": annot_id,
                    "image_id": t,
                    "category_id": start_annot["category_id"],
                    "keypoints": [
                        val
                        for (x, y), vis in zip(xy, v)
                        for val in (float(x), float(y), int(vis))
                    ],
                    "num_keypoints": int(labelled.sum()),
                    "bbox": bbox,
                    "area": bbox[2] * bbox[3],
                    "iscrowd": 0,
                }
                if "track_id" in start_annot:
                    annotation["track_id"] = start_annot["track_id"]
                annotations.append(annotation)
                annot_id += 1

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / startlabels_path.name.replace(
            "_startlabels.json", "_cliplabels.json"
        )
        with open(output_path, "w") as f:
            json.dump(
                {
                    "images": images,
                    "annotations": annotations,
                    "categories": startlabels["categories"],
                },
                f,
            )
        return output_path


def parse_args(args: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    # shared across trackers
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--startlabels", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)

    # tool-specific
    parser.add_argument("--model-name", default="cotracker3_offline")
    parser.add_argument("--device", default="cpu")

    return parser.parse_args(args)


def main(args: argparse.Namespace) -> None:
    tracker = CoTracker3(args.model_name, args.device)
    output_path = tracker.run(
        args.video,
        args.startlabels,
    )

    print(f"pred tracks shape: {pred_tracks.shape}")
    print(f"pred vis shape: {pred_visibility.shape}")

    output_path = tracker.write_cliplabels(
        pred_tracks,
        pred_visibility,
        startlabels_path=args.startlabels,
        output_dir=args.output_dir,
    )
    print(f"Saved cliplabels to {output_path}")


if __name__ == "__main__":
    main(parse_args(sys.argv[1:]))
