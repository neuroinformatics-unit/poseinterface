"""Export annotations to COCO JSON file"""
# %%
# Notes
# - all projects I tried are with a single video
# - in LP example project: no video directory
# - sleap io assumes frame paths are: (....)/ `labeled-data` / video-name / img0000x.extension
# - when loading DLC files with sleap-io: the frames need to exist

# %%
from pathlib import Path

from sleap_io.io import coco, dlc

# %%
# Input data: DLC project with a single video

data_dir = Path.home() / "swc" / "project_poseinterface" / "data"

# One annotation file per video
dlc_annotations_files_csv = (
    data_dir
    / "DLC-openfield-Pranav-2018-10-30"  # -no-frames"
    / Path("CollectedData_Pranav.csv")
)

video_name = dlc_annotations_files_csv.parent.stem
out_coco_json = (
    dlc_annotations_files_csv.parent
    / f"{video_name}_{dlc_annotations_files_csv.stem}.json"
)

# %%%%%%%%%%%%
# Read DLC file

labels = dlc.load_dlc(dlc_annotations_files_csv, video_search_paths=None)

print(labels)
print(labels.videos)  # paths to extracted frames?
print(labels.labeled_frames)
print(labels.skeletons)

assert len(labels.labeled_frames) != 0
assert len(labels.videos) == 1
assert len(labels.skeletons) == 1  # single animal?

# %%%%%%%%%%%%%%%%%%%
# Export as COCO JSON

coco.write_labels(labels, out_coco_json, visibility_encoding="ternary")

# %%
