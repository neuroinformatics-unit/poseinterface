"""Export annotations to COCO JSON file"""
# %%
# Notes
# - all projects I tried are with a single video
# - in LP example project: no video directory
# - sleap io assumes frame paths are: (....)/ `labeled-data` / video-name / img0000x.extension
# - when loading DLC files with sleap-io: the frames need to exist

# %%
from pathlib import Path

from poseinterface.io import format_dlc_annotations_file

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Input data: DLC project with a single video

data_dir = Path.home() / "swc" / "project_poseinterface" / "data"

# One annotation file per video
dlc_annotations_files_csv = (
    data_dir
    / "DLC-openfield-Pranav-2018-10-30"
    / "labeled-data"
    / "m4s1"
    / Path("CollectedData_Pranav.csv")
)

# Output path
video_name = dlc_annotations_files_csv.parent.stem
out_coco_json = (
    dlc_annotations_files_csv.parent
    / f"{video_name}_{dlc_annotations_files_csv.stem}.json"
)

# %%%%%%%%%%%%
# Export as COCO

out_json = format_dlc_annotations_file(
    dlc_annotations_files_csv, out_coco_json
)

# %%
