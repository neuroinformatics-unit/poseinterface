"""Convert DeepLabCut project to benchmark dataset
==================================================

Create a ``poseinterface`` benchmark dataset from a DeepLabCut (DLC) project.
"""

# %%
# Imports
# -------
import shutil
import tempfile
from pathlib import Path

from poseinterface.clips import extract_clip
from poseinterface.io import (
    annotations_to_poseinterface,
    frames_to_poseinterface,
    predictions_to_poseinterface,
    video_to_poseinterface,
)
from poseinterface.utils import tree

# %%
# Overview
# --------
# We'll handle the conversion in two steps:
#
# 1. **Convert:** DLC project files (session videos, frame annotations, and
#    model predictions) are restructured into the
#    :ref:`poseinterface benchmark layout <target-benchmark-dataset>`.
# 2. **Extract clips:** Short video clips and their label files are extracted
#    from the converted session videos, ready for expert review.
#
# .. figure:: /_static/DLC_to_poseinterface_worklow.svg
#    :alt: Workflow diagram showing how a DLC project is converted
#           to a poseinterface benchmark dataset
#    :align: center
#
#    High-level overview of the two-step conversion workflow.

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
# The two sub-directories we care about are:
#
# - ``videos/``: the session videos and their corresponding prediction files.
# - ``labeled-data/``: sampled frames and their ground-truth annotations.
#
# Let's peek inside each.

print(tree(source_project_dir / "videos", level=1, exclude_hidden=True))

# %%
# Each video (ending in ``converted.mp4``) has a companion .csv prediction
# file. The ``labeled-data`` sub-directories mirror the video names (without
# ``.mp4``) and contain the sampled frame images (.png) and their annotations
# (.csv). In real projects you may also find predictions and annotations in
# .h5 format, as well as filtered prediction files.

print(tree(source_project_dir / "labeled-data", level=2, exclude_hidden=True))

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
        "source_video": "M727755_EPM_20200317_170544999-converted.mp4",
        "sub_id": "M727755",
        "ses_id": "20200317",
        "cam_id": "topdown",
    },
    {
        "split": "Test",
        "source_video": "M708154_EPM_20200317_185651629-converted.mp4",
        "sub_id": "M708154",
        "ses_id": "20200317",
        "cam_id": "topdown",
    },
]

project_name = "SWC-plusmaze"

# Replace this with the path where you want to save your benchmark dataset.
benchmark_base_dir = Path(tempfile.mkdtemp())

# %%
# Convert to benchmark format
# ----------------------------
# For each session we: copy and re-encode the session video if necessary,
# convert DLC annotations to COCO frame labels, copy and rename the sampled
# frame images, and convert DLC predictions to COCO JSON.

for session in sessions:
    split = session["split"]
    ids = {k: session[k] for k in ["sub_id", "ses_id", "cam_id"]}
    sub_ses_prefix = f"sub-{ids['sub_id']}_ses-{ids['ses_id']}"
    sub_ses_cam_prefix = f"{sub_ses_prefix}_cam-{ids['cam_id']}"

    print(f"Converting session: {split}/{project_name}/{sub_ses_prefix}")

    # Derive source paths
    source_video_path = source_project_dir / "videos" / session["source_video"]
    source_frames_dir = (
        source_project_dir / "labeled-data" / source_video_path.stem
    )
    # Find the predictions .csv file. In real projects there may be multiple
    # (e.g. filtered versions), so adjust the glob pattern if needed.
    source_predictions_path = next(
        (source_project_dir / "videos").glob(f"{source_video_path.stem}*.csv")
    )
    # Find the annotations .csv file. In real projects there may be multiple
    # (e.g. for different labelers), so adjust the glob pattern if needed.
    source_annotations_path = next(
        source_frames_dir.glob("CollectedData_*.csv")
    )

    # Derive target paths
    target_session_dir = (
        benchmark_base_dir / split / project_name / sub_ses_prefix
    )
    target_frames_dir = target_session_dir / "Frames"
    target_frames_dir.mkdir(parents=True, exist_ok=True)

    # Copy the session video, re-encoding to H.264/yuv420p if necessary
    video_to_poseinterface(
        input_video=source_video_path,
        output_video_dir=target_session_dir,
        **ids,
    )
    print(f"\tvideo: {source_video_path.name} -> {sub_ses_cam_prefix}.mp4")

    # Convert DLC annotations to COCO frame labels JSON, then copy the
    # corresponding frame images with standardised poseinterface filenames.
    framelabels_path = annotations_to_poseinterface(
        input_path=source_annotations_path,
        output_dir=target_frames_dir,
        format="frame",
        **ids,
    )
    frames_to_poseinterface(
        source_dir=source_frames_dir,
        target_dir=target_frames_dir,
        framelabels_path=framelabels_path,
    )
    print(
        f"\tannotations (+ frame images): {source_annotations_path.name} -> "
        f"{framelabels_path.name}"
    )

    # Convert DLC predictions to COCO video labels JSON for clip extraction
    predictions_to_poseinterface(
        predictions_path=source_predictions_path,
        video_path=source_video_path,
        output_json_parent_dir=target_session_dir,
        **ids,
    )
    print(
        f"\tpredictions: {source_predictions_path.name} -> "
        f"{sub_ses_cam_prefix}_videolabels.json"
    )
    print("Done.\n")

# %%
# The resulting benchmark dataset:

print(tree(benchmark_base_dir, level=5))

# %%
# .. note::
#
#    Frame labels (``framelabels.json``) are generated for both splits, but in
#    the published dataset the ``Test`` split withholds them for evaluation.
#    See :ref:`benchmark dataset <target-benchmark-dataset>` for details.
#
#    The ``videolabels.json`` files generated alongside each session video are
#    intermediate artifacts used for clip extraction in the next section, and
#    will not be included in the published dataset.


# %%
# Extract clips
# -------------
# Let's extract short clips from the converted session videos. The resulting
# clip label files (``cliplabels.json``) can be proof-read and corrected by
# experts before being shared as part of the benchmark dataset.
#
# First, we specify the clip parameters. This step can be run multiple times
# with different parameters to grow the clip set incrementally.

duration = 5  # frames per clip
start_frames = [25, 50, 75]

# %%
# We loop over all sessions and extract clips at each start frame.
# The resulting video clips and their ``cliplabels.json`` files are saved
# in a ``Clips/`` subdirectory within each session folder.

for session in sessions:
    sub_ses_prefix = f"sub-{session['sub_id']}_ses-{session['ses_id']}"
    sub_ses_cam_prefix = f"{sub_ses_prefix}_cam-{session['cam_id']}"
    session_dir = (
        benchmark_base_dir / session["split"] / project_name / sub_ses_prefix
    )

    for start_frame in start_frames:
        clip_path, _ = extract_clip(
            video_path=session_dir / f"{sub_ses_cam_prefix}.mp4",
            start_frame=start_frame,
            duration=duration,
        )
        print(f"Extracted clip: {clip_path.stem}")


# %%
# The resulting benchmark dataset, including the extracted clips and their
# corresponding labels:

print(tree(benchmark_base_dir, level=5))


# %%
# .. note::
#
#    In the published dataset, the ``Train`` split includes all extracted clip
#    labels (``cliplabels.json``). The ``Test`` split withholds full clip
#    labels; only clip start labels (``startlabels.json``), derived from each
#    clip's first frame, are included to support point-tracker evaluation.
#    The `videolabels.json`` files generated in the previous section are
#    intermediate artifacts used for clip extraction, and are never shared.
#    See :ref:`benchmark dataset <target-benchmark-dataset>` for details.

# %%
# Clean up the temporary directory.

shutil.rmtree(benchmark_base_dir)

# %%
