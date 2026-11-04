"""Base class for point trackers.

Concrete trackers live in ``envs/<tool>/infer.py`` and run in their own
environment. This module must not import tool-specific dependencies
(e.g. ``torch``).
"""

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal

import numpy as np
import sleap_io as sio

from poseinterface.io import load_cliplabels

OutputFormat = Literal["annotations", "predictions"]


class PointTracker(ABC):
    """Track points through a clip, starting from its start labels.

    Subclasses implement :meth:`track`. Trackers that work on in-memory
    frames can use :meth:`load_video`; trackers that read video files
    themselves can pass ``video_path`` straight to the tool.
    """

    @abstractmethod
    def track(
        self, video_path: Path | str, startlabels_path: Path | str
    ) -> tuple[np.ndarray, np.ndarray]:
        """Track the start-label keypoints through a video.

        Parameters
        ----------
        video_path
            Path to the clip video.
        startlabels_path
            Path to the clip's ``*_startlabels.json``.

        Returns
        -------
        tracks
            Point positions, shape ``(T, N, 2)`` as ``(x, y)``, with
            ``N = n_instances * n_keypoints`` in :meth:`load_queries` order.
        visibility
            Point visibility, shape ``(T, N)``, ``bool``.
        """

    def run(
        self,
        video_path: Path | str,
        startlabels_path: Path | str,
        output_dir: Path | str,
        format: OutputFormat = "annotations",
    ) -> Path:
        """Track a clip and write the predictions to ``output_dir``."""
        tracks, visibility = self.track(video_path, startlabels_path)
        return self.write_cliplabels(
            tracks, visibility, startlabels_path, output_dir, format=format
        )

    @staticmethod
    def load_video(video_path: Path | str) -> np.ndarray:
        """Read a clip as an array of shape ``(T, H, W, 3)``, ``uint8``."""
        # sleap_io returns a negative-stride view (BGR -> RGB flip), which
        # e.g. torch.from_numpy rejects; return a contiguous copy instead.
        return np.ascontiguousarray(sio.load_video(str(video_path))[:])

    @staticmethod
    def load_queries(startlabels_path: Path | str) -> np.ndarray:
        """Convert *PoseMark* start labels to queries.

        Returns
        -------
        numpy.ndarray
            Queries of shape ``(N, 3)`` as ``(t, x, y)``, ordered by
            frame, then instance, then keypoint. Unlabelled keypoints
            have NaN ``x, y``.
        """
        start = load_cliplabels(startlabels_path)  # (F, I, K, 2)
        n_frames, n_instances, n_keypoints, _ = start.shape
        t = np.broadcast_to(
            np.arange(n_frames, dtype=float)[:, None, None, None],
            (n_frames, n_instances, n_keypoints, 1),
        )
        return np.concatenate([t, start], axis=-1).reshape(-1, 3)

    @staticmethod
    def write_cliplabels(
        tracks: np.ndarray,
        visibility: np.ndarray,
        startlabels_path: Path | str,
        output_dir: Path | str,
        format: OutputFormat = "annotations",
    ) -> Path:
        """Write tracker predictions as a COCO json file.

        Categories, image size and frame naming are taken from the start
        labels. The output filename replaces the ``_startlabels`` suffix
        with ``_cliplabels`` (annotations) or ``_clippredictions``
        (predictions).

        Parameters
        ----------
        tracks
            Predicted positions, shape ``(T, N, 2)`` as ``(x, y)``, with
            ``N = n_instances * n_keypoints`` in start-label order.
        visibility
            Predicted visibility, shape ``(T, N)`` (or ``(T, N, 1)``).
        startlabels_path
            Path to the start labels json used to build the queries.
        output_dir
            Directory where the json is written.
        format
            ``"annotations"`` writes a *PoseMark* clip labels file (COCO
            annotations format, with ``images`` and ``categories``).
            ``"predictions"`` writes a COCO results file: a list of
            ``{image_id, category_id, keypoints, score}``, where ``score``
            is the fraction of tracked keypoints predicted visible.

        Returns
        -------
        Path
            Path to the written json.
        """
        startlabels_path = Path(startlabels_path)
        with open(startlabels_path) as f:
            start = json.load(f)

        n_frames = tracks.shape[0]
        start_annots = start["annotations"]
        n_instances = len(start_annots)
        n_keypoints = max(
            len(cat.get("keypoints", [])) for cat in start["categories"]
        )
        tracks = tracks.reshape(n_frames, n_instances, n_keypoints, 2)
        visible = visibility.reshape(n_frames, n_instances, n_keypoints) > 0.5

        # Keypoints unlabelled in the start frame stay unlabelled (v=0).
        # Tracked keypoints are labelled: v=2 if visible, v=1 if occluded.
        labelled = ~np.isnan(load_cliplabels(startlabels_path)[0, ..., 0])
        v = np.where(visible, 2, 1) * labelled  # (T, n_inst, n_kpt)

        # Frame naming: continue from the start frame's file_name
        start_img = start["images"][0]
        match = re.search(r"frame-(\d+)", start_img["file_name"])
        if match is None:
            raise ValueError(
                f"Could not find frame number in {start_img['file_name']!r}."
            )
        prefix = start_img["file_name"][: match.start(1)]
        first = int(match.group(1))
        width = max(len(match.group(1)), len(str(first + n_frames - 1)))
        size = {k: start_img[k] for k in ("width", "height") if k in start_img}
        images = [
            {"id": t, "file_name": f"{prefix}{first + t:0{width}d}", **size}
            for t in range(n_frames)
        ]

        annotations: list[dict[str, Any]] = []
        for t in range(n_frames):
            for i, start_annot in enumerate(start_annots):
                xy = tracks[t, i].astype(float)
                vis = v[t, i]
                xy[vis == 0] = 0.0
                if vis.any():
                    x_min, y_min = xy[vis > 0].min(axis=0)
                    x_max, y_max = xy[vis > 0].max(axis=0)
                    bbox = [x_min, y_min, x_max - x_min, y_max - y_min]
                else:
                    bbox = [0.0, 0.0, 0.0, 0.0]
                bbox = [float(b) for b in bbox]
                annot = {
                    "id": len(annotations) + 1,
                    "image_id": t,
                    "category_id": start_annot["category_id"],
                    "keypoints": [
                        val
                        for (x, y), vi in zip(xy.tolist(), vis.tolist())
                        for val in (x, y, int(vi))
                    ],
                    "num_keypoints": int((vis > 0).sum()),
                    "bbox": bbox,
                    "area": bbox[2] * bbox[3],
                    "iscrowd": 0,
                }
                if "track_id" in start_annot:
                    annot["track_id"] = start_annot["track_id"]
                annotations.append(annot)

        if format == "annotations":
            suffix = "cliplabels"
            content: dict[str, Any] | list[dict[str, Any]] = {
                "images": images,
                "annotations": annotations,
                "categories": start["categories"],
            }
        elif format == "predictions":
            suffix = "clippredictions"
            n_tracked = np.maximum(labelled.sum(axis=-1), 1)  # (n_inst,)
            scores = (v == 2).sum(axis=-1) / n_tracked  # (T, n_inst)
            content = [
                {
                    "image_id": a["image_id"],
                    "category_id": a["category_id"],
                    "keypoints": a["keypoints"],
                    "score": float(scores.ravel()[k]),
                }
                for k, a in enumerate(annotations)
            ]
        else:
            raise ValueError(
                "format must be 'annotations' or 'predictions', "
                f"got {format!r}."
            )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = startlabels_path.stem.removesuffix("_startlabels")
        output_path = output_dir / f"{stem}_{suffix}.json"
        with open(output_path, "w") as f:
            json.dump(content, f)
        return output_path
