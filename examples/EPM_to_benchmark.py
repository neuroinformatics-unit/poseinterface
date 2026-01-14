"""Convert SWC EPM dataset to pose benchmarks format
====================================================
Convert keypoint annotations
from the Elevated Plus Maze (EPM) dataset from DLC to COCO format.

Also copy a video and its labeled frames to a target directory,
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
# In this example, we convert the DLC annotations to COCO .json format.

# %%
# Define source and target directories
# ------------------------------------
# We specify the paths to the source DLC project directory
# as well as the target directory where converted files will be saved.
# The target will be organised in the pose benchmarks dataset structure.

source_base_dir = Path(
    "/media/ceph-niu/neuroinformatics/sirmpilatzen/behav_data"
    "/Loukia/MASTER_DoNotModify"
)
source_project_dir = source_base_dir / "MouseTopDown-Loukia-2022-09-13"
assert source_project_dir.exists(), (
    f"DLC project directory not found: {source_project_dir}"
)

target_base_dir = Path("/mnt/Data/pose_benchmarks")
target_dataset_dir = target_base_dir / "SWC-EPM"
target_dataset_dir.mkdir(parents=True, exist_ok=True)

# %%
# Copy video to target location
# -----------------------------
# We identify a specific video by name and copy it to the target directory
# with a standardised naming convention.

source_video_name = "M708149_EPM_20200317_165049331-converted.mp4"
source_video_path = source_project_dir / "videos" / source_video_name

# Define subject, session, and view identifiers
subject_id = "M708149"
session_id = "20200317"
view_id = "topdown"
video_id = f"sub-{subject_id}_ses-{session_id}_view-{view_id}"

# Create target session directory
target_session_dir = target_dataset_dir / f"sub-{subject_id}_ses-{session_id}"
target_session_dir.mkdir(parents=True, exist_ok=True)

# Copy video to target location
target_video_path = target_session_dir / f"{video_id}.mp4"
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
    source_project_dir / "labeled-data" / source_video_name.replace(".mp4", "")
)
source_annotations_path = source_labels_dir / "CollectedData_Loukia.csv"

# Create Frames directory inside the session directory
target_frames_dir = target_session_dir / "Frames"
target_frames_dir.mkdir(parents=True, exist_ok=True)

# Save COCO annotations inside the Frames directory
target_annotations_path = target_frames_dir / f"{video_id}_framelabels.json"

annotations_to_coco(
    input_path=source_annotations_path,
    output_json_path=target_annotations_path,
    coco_visibility_encoding="ternary",
)
print(f"Saved COCO annotations to: {target_annotations_path}")

# %%
# Copy labeled frames to target directory
# ---------------------------------------
# Copy the frames used for labeling and rename them to follow
# the naming convention:
# ``sub-{subjectID}_ses-{SessionID}_view-{ViewID}_frame-{FrameID}.png``

for source_frame_path in source_labels_dir.glob("*.png"):
    # Extract frame number from original filename, e.g. "img0042.png" -> "0042"
    frame_number = source_frame_path.stem.replace("img", "")
    target_frame_path = (
        target_frames_dir / f"{video_id}_frame-{frame_number}.png"
    )
    if not target_frame_path.exists():
        shutil.copy2(source_frame_path, target_frame_path)

print(f"Copied labeled frames to: {target_frames_dir}")

# %%
