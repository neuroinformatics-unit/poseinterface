"""Convert DeepLabCut predictions to COCO format
================================================

Use ``sleap-io`` to load keypoints predicted by DeepLabCut
and save them to COCO .json format.
"""

# %%
# Imports
# -------
from pathlib import Path

import sleap_io as sio
from movement import sample_data
from movement.io import load_poses, save_poses

# %%
# List available DeepLabCut sample datasets
# -----------------------------------------
# Let's see which DeepLabCut sample datasets are available
# through `movement.sample_data```. We will also include
# sample datasets from LightningPose, because they use
# the same file formats.

print("Available DeepLabCut and LightningPose sample datasets:\n")

sample_ds_names = [
    name
    for name in sample_data.list_datasets()
    if name.startswith("DLC_") or name.startswith("LP_")
]
print(*sample_ds_names, sep="\n")

# %%
# Fetch path to a sample dataset
# -------------------------------
# We pick one from the Allen Institute for Neural Dynamics (AIND)

ds_name = "LP_mouse-face_AIND.predictions.csv"
file_path = sample_data.fetch_dataset_paths(ds_name)["poses"]
ds_path = file_path.resolve()
print(f"\nPath to sample dataset '{ds_name}':\n{ds_path}")

# %%
# The df.index contains the frame numbers (0, 1, 2, ...)
# I want to convert them into a "fake" frame paths of the form
# "labeled_data/video/frame_00000.png", etc.
# Let's create a list of such paths

# `fps = None`` for time coordinates to be frame indices
ds = load_poses.from_dlc_file(ds_path, fps=None)
frame_ids = ds.coords["time"].values
num_frames = ds.sizes["time"]
# zero-padding width
pad_width = len(str(num_frames - 1))

frame_paths = [
    f"labeled-data/video/img{i:0{pad_width}d}.png" for i in frame_ids
]

print("\nFirst 5 frame paths:")
print("\n".join(frame_paths[:5]))


# %%
# Assign the frame paths to the dataset as time coordinates
ds = ds.assign_coords({"time": frame_paths})
print(ds.coords["time"].values[:5])

cwd = Path.cwd()

# uses a HACKED version of to_dlc_file that retains frame paths as csv index
save_poses.to_dlc_file(
    ds,
    cwd / "dlc_predictions_with_frame_paths.csv",
    split_individuals=False,
)


# %%
# Let's load it with sleap-io

print(f"\nCurrent working directory: {cwd}")

poses = sio.load_file(
    cwd / "dlc_predictions_with_frame_paths_no-likelihood.csv", format="dlc"
)

# %%
