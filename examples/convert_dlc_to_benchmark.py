"""Convert DeepLabCut project to benchmark dataset
==================================================

Convert videos and labelled frames from DeepLabCut to
``poseinterface`` benchmark dataset format.
"""

# %%
# Imports
# -------
import shutil
import tempfile
from pathlib import Path

from poseinterface.io import (
    annotations_to_poseinterface,
    frames_to_poseinterface,
)
from poseinterface.utils import tree

# %%
# Source DLC project
# ------------------
# We work with a dataset from the
# `Sainsbury Wellcome Centre (SWC) <https://www.sainsburywellcome.org/>`_,
# produced by Loukia Katsouri from John O'Keefe's lab.
# It contains single-animal top-down videos of mice exploring an elevated plus
# maze, with keypoint annotations generated using
# `DeepLabCut (DLC) <https://www.mackenziemathislab.org/deeplabcut>`_.
#
# .. note::
#
#    This example runs against a lightweight fixture shipped with the
#    repository (under ``tests/data/``). This fixture contains only a subset
#    of the original DLC project, and is intended for testing and demonstration
#    purposes.
#    Replace ``source_project_dir`` with the path to your own DLC project to
#    convert real data, and keep in mind that your project will contain more
#    files than are shown here.

source_project_dir = (
    Path(".").resolve().parent
    / "tests"
    / "data"
    / "dlc"
    / "MouseTopDown-Loukia-2022-09-13"
)

print(tree(source_project_dir, level=1, exclude_hidden=True))

# %%
# The only sub-directories we care about are:
#
# - ``videos/``: the videos and their corresponding DLC prediction files.
# - ``labeled-data/``: sampled frames and their annotations.
#
# Let's peek at both.

print(
    tree(
        source_project_dir / "videos",
        level=1,
        exclude_hidden=True,
    )
)

# %%
# Each video (ending in ``converted.mp4``) has a companion .csv prediction
# file. In real projects you will also find predictions in .h5 format,
# filtered versions of the predictions, and other files.

print(
    tree(
        source_project_dir / "labeled-data",
        level=2,
        exclude_hidden=True,
    )
)

# %%
# The ``labeled-data`` sub-directories mirror video names (without ``.mp4``)
# and contain the sampled frames (.png files) and their annotations
# (here as .csv files, but in real projects you may also find them as .h5).

# %%
# Define sessions to convert
# ---------------------------
# We select two sessions from the DLC project and assign each to either
# the ``Train`` or ``Test`` split of the
# :ref:`benchmark dataset <target-benchmark-dataset>`.
# You may expand this list with more sessions, but ensure that each session
# belongs to exactly one split, and that the same subject doesn't appear in
# both splits (to avoid data leakage).
# All videos use the same top-down camera view (``cam-topdown``).

sessions = [
    {
        "split": "Train",
        "source_video": ("M727755_EPM_20200317_170544999-converted.mp4"),
        "subject_id": "M727755",
        "session_id": "20200317",
    },
    {
        "split": "Test",
        "source_video": ("M708154_EPM_20200317_185651629-converted.mp4"),
        "subject_id": "M708154",
        "session_id": "20200317",
    },
]

camera_id = "topdown"
project_name = "SWC-plusmaze"

# Replace this with the path where you want to save your benchmark dataset.
benchmark_base_dir = Path(tempfile.mkdtemp())

# %%
# Convert to benchmark format
# ----------------------------
# For each session we create the target directories, copy the session video,
# convert DLC annotations to COCO .json, and copy the frame images with
# standardised names.

for session in sessions:
    split = session["split"]
    subject_id = session["subject_id"]
    session_id = session["session_id"]

    # Derive source paths
    source_video_path = source_project_dir / "videos" / session["source_video"]
    source_frames_dir = (
        source_project_dir / "labeled-data" / source_video_path.stem
    )

    # Derive target paths
    session_prefix = f"sub-{subject_id}_ses-{session_id}"
    video_prefix = f"{session_prefix}_cam-{camera_id}"
    target_session_dir = (
        benchmark_base_dir / split / project_name / session_prefix
    )
    target_frames_dir = target_session_dir / "Frames"
    target_frames_dir.mkdir(parents=True, exist_ok=True)

    # Copy the session video
    target_video_path = target_session_dir / f"{video_prefix}.mp4"
    if not target_video_path.exists():
        shutil.copy2(source_video_path, target_video_path)

    # Convert annotations from DLC CSV to COCO JSON
    framelabels_path = target_frames_dir / f"{video_prefix}_framelabels.json"
    annotations_to_poseinterface(
        input_path=(source_frames_dir / "CollectedData_Loukia.csv"),
        output_dir=target_frames_dir,
        sub_id=subject_id,
        ses_id=session_id,
        cam_id=camera_id,
    )

    # Copy frames, renaming per the COCO JSON filenames.
    frames_to_poseinterface(
        source_dir=source_frames_dir,
        target_dir=target_frames_dir,
        framelabels_path=framelabels_path,
    )

    print(f"Done: {split}/{project_name}/{session_prefix}")

# %%
# The resulting benchmark dataset:

print(tree(benchmark_base_dir, level=5))

# %%
# .. note::
#
#    The ``framelabels.json`` files are generated for both splits during
#    conversion, but in the publicly shared benchmark dataset they will be
#    **stripped from the Test split**. This is because the ``Test`` labels
#    are withheld for evaluation purposes
#    (see :ref:`benchmark dataset <target-benchmark-dataset>` for details).

# %%
# Clean up the temporary directory.

shutil.rmtree(benchmark_base_dir)
