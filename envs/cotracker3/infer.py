import argparse
import sys
from pathlib import Path

import numpy as np

from poseinterface.trackers import PointTracker


class CoTracker3(PointTracker):
    def __init__(
        self, checkpoint: str = "cotracker3_offline", device: str = "cpu"
    ) -> None:
        raise NotImplementedError

    def track(
        self, video: np.ndarray, queries: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError


def parse_args(args: list[str]) -> argparse.Namespace:
    # shared across trackers: --startlabels, --video, --out
    # tool-specific: --checkpoint, --device
    raise NotImplementedError


def main(args: argparse.Namespace) -> None:
    tracker = CoTracker3(args.checkpoint, args.device)
    tracker.run(args.startlabels, args.video, Path(args.out))


if __name__ == "__main__":
    main(parse_args(sys.argv[1:]))
