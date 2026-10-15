import sys
import torch


class PointTrackerCoTracker(PointTracker):
    def __init__(self):
        model_name: str
        config: dict
        model: torch.nn.Module

        self.model = torch.hub.load("facebookresearch/co-tracker", "cotracker3_offline").to(device)

    def infer(self, startlabels: dict, video: torch.Tensor) -> dict:
        # convert from PoseMark to cotracker format
        # pred_tracks, pred_visibility = self.model(video, grid_size=grid_size) # B T N 2,  B T N 1
        pass 

    def evaluate(self, predicted_tracks: dict, gt_tracks: dict) -> dict:
        pass


def parse_args(args):
    pass

def main(args) -> None:
    point_tracker = PointTrackerCoTracker(args.model, args.config)
    point_tracker.infer(startlabels={})
    print("Inference completed successfully. Saved results .")


if __name__ == "__main__":
    infer_args = parse_args(sys.argv[1:])
    main(infer_args)
