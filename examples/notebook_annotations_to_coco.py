"""Export annotations to COCO JSON file"""
# %%
# Notes
# - all projects I tried are with a single video
# - in LP example project: no video directory
# - sleap-io assumes frame paths have minimally:
#   labeled-data/<video-name>/<img-name>.<ext>
# - <img-name> must contain the (sequence of) digits representing
#   the frame index
# - if <img-name> is alphanumerical, the last sequence of digits is assumed to
#   be the frame index
# - when loading DLC files with sleap-io: the frames need to exist

# %%
from pathlib import Path

from poseinterface.io import annotations_to_coco

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Input data: DLC project with a single video

data_dir = Path.home() / "swc" / "project_poseinterface" / "data"

# One annotation file per video
dlc_annotations_files_csv = (
    data_dir
    / "DLC-openfield-Pranav-2018-10-30"
    / "labeled-data"
    / "m4s1"
    / "CollectedData_Pranav.csv"
)

# Output path
video_name = dlc_annotations_files_csv.parent.stem
out_coco_json = (
    dlc_annotations_files_csv.parent
    / f"{video_name}_{dlc_annotations_files_csv.stem}.json"
)

# %%%%%%%%%%%%
# Export as COCO

out_json = annotations_to_coco(dlc_annotations_files_csv, out_coco_json)

# %%
