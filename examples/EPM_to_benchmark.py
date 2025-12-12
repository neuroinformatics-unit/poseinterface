"""Convert SWC EPM dataset to pose benchmarks format
====================================================
Convert keypoint annotations
from the Elevated Plus Maze (EPM) dataset from DLC to COCO format.

Also copy a video and its labeled frames to the target directory,
organised in the pose benchmarks dataset structure.
"""

# %%
# Imports
# -------
import shutil
from pathlib import Path

from poseinterface.io import annotations_to_coco

# %%
# Background
# ----------
# We've identified potential datasets from SWC that could be used for the pilot
# version of the pose benchmark dataset.
# Among these is the Elevated Plus Maze (EPM) dataset produced by
# Loukia Katsouri, for John O'Keefe's lab.
# It contains single-animal top-down videos of mice exploring an elevated plus
# maze, with keypoint annotations and predictions from DeepLabCut (DLC).
#
# In this notebook, we convert the DLC annotations to COCO .json format.

# %%
# Specify paths
# -------------
# We specify the paths to the source DLC project directory
# as well as the output directory where converted COCO files will be saved.
# The latter will be organised in the pose benchmark dataset structure.

base_dir = Path(
    "/media/ceph-niu/neuroinformatics/sirmpilatzen/behav_data"
    "/Loukia/MASTER_DoNotModify"
)
dlc_project_dir = base_dir / "MouseTopDown-Loukia-2022-09-13"
assert dlc_project_dir.exists(), (
    f"DLC project dir not found: {dlc_project_dir}"
)

pose_benchmarks_dir = Path("/mnt/Data/pose_benchmarks")
target_dir = pose_benchmarks_dir / "SWC_EPM"
target_dir.mkdir(parents=True, exist_ok=True)

# %%
# Copy a video to target location
# -------------------------------

# Let's identify a specific video by name
source_video_name = "M708149_EPM_20200317_165049331-converted.mp4"

# Define subject, session, and view IDs
sub_id = "M708149"
ses_id = "20200317"
view = "topdown"

# Create target session directory
target_ses_dir = target_dir / f"sub-{sub_id}_ses-{ses_id}"
target_ses_dir.mkdir(parents=True, exist_ok=True)

# Copy video to target location with appropriate naming
video_id = f"sub-{sub_id}_ses-{ses_id}_view-{view}"
source_video_path = dlc_project_dir / "videos" / source_video_name
target_video_path = target_ses_dir / f"{video_id}.mp4"

if not target_video_path.exists():
    shutil.copy2(source_video_path, target_video_path)
    print(f"Copied video to: {target_video_path}")
else:
    print(f"Video already exists at: {target_video_path}")

# %%
# Convert DLC annotations to COCO format
# --------------------------------------
# Here we use the :func:`annotations_to_coco` function from `poseinterface.io`
# which wraps around `sleap_io` functionality to perform the conversion.
#
# The first attempt failed because the paths in the DLC annotations
# csv file were given as
# ``labeled-data,<video-name>,<filename-with-frame-number>.<extension>``
# instead of the required
# ``labeled-data/<video-name>/<filename-with-frame-number>.<extension>``.
# We fixed this by replacing the commas with slashes in the csv file.

source_labels_dir = (
    dlc_project_dir / "labeled-data" / source_video_name.replace(".mp4", "")
)
dlc_annotations_file = source_labels_dir / "CollectedData_Loukia.csv"

out_json_path = target_ses_dir / f"{video_id}_framelabels.json"

annotations_to_coco(
    input_path=dlc_annotations_file,
    output_json_path=out_json_path,
    coco_visibility_encoding="ternary",
)

# %%
# Let's also copy the frames used for labeling to the target directory

target_frames_dir = target_ses_dir / "frames"
target_frames_dir.mkdir(parents=True, exist_ok=True)

for frame_file in source_labels_dir.glob("*.png"):
    target_frame_file = target_frames_dir / frame_file.name
    if not target_frame_file.exists():
        shutil.copy2(frame_file, target_frame_file)

# %%
