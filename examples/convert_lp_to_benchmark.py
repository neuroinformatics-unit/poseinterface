"""Convert Lightning Pose project to benchmark dataset
======================================================

Create a ``poseinterface`` benchmark dataset from a Lightning Pose (LP)
project.
"""

# %%
# Imports
# -------
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import poseinterface
from poseinterface.clips import extract_single_clip
from poseinterface.io import (
    annotations_to_poseinterface,
    frames_to_poseinterface,
    predictions_to_poseinterface,
    split_lp_collected_data,
    video_to_poseinterface,
)
from poseinterface.utils import tree

# %%
# Overview
# --------
# We'll handle the conversion in two steps:
#
# 1. **Convert:** LP project files (videos, frame annotations, and keypoint
#    predictions) are restructured into the
#    :ref:`poseinterface benchmark layout <target-benchmark-dataset>`.
# 2. **Extract clips:** Short video clips and their labels are extracted
#    from the converted videos and their corresponding keypoint predictions,
#    ready for expert review.
#
# The workflow is similar to the one followed in
# :ref:`sphx_glr_auto_examples_convert_dlc_to_benchmark.py`,
# with a few differences explained below.

# %%
# Source Lightning Pose project
# -----------------------------
# We work with a dataset from the
# `International Brain Laboratory (IBL)
# <https://www.internationalbrainlab.com/>`_,
# containing videos of mouse paw movements analysed using
# `Lightning Pose <https://github.com/paninski-lab/lightning-pose>`_.
#
# .. note::
#
#    This example runs against a lightweight fixture shipped with the
#    repository (under ``tests/data/``). Replace ``source_project_dir``
#    and ``benchmark_base_dir`` with the paths to your LP project and
#    benchmark dataset directories, respectively. Keep in mind that your
#    project will contain more files than are shown here.
#
# .. warning::
#
#    Lightning Pose saves prediction files to the model output directory,
#    **not** to the project's ``videos/`` directory.  Before running this
#    script, move (or copy) each session's prediction CSV — and apply any
#    manual corrections you have made — into
#    ``<source_project_dir>/videos/``, named to match the corresponding
#    video stem (e.g. ``<video_stem>.csv``).

source_project_dir = (
    Path(".").resolve().parent / "tests" / "data" / "lightningpose" / "ibl-paw"
)
print(tree(source_project_dir, level=1, exclude_hidden=True))

# For this example we use a temporary directory, cleaned up at the end.
benchmark_base_dir = Path(tempfile.mkdtemp(prefix="poseinterface-benchmark-"))
print(f"\nBenchmark dataset will be saved to: {benchmark_base_dir}")

# %%
# The LP project differs from a DLC project in one key respect: all session
# annotations live in a **single project-level** ``CollectedData.csv`` rather
# than in per-session files inside ``labeled-data/``.  The two sub-directories
# we care about otherwise mirror the DLC layout:
#
# - ``videos/``: session videos and (after the move described above) their
#   corresponding prediction CSVs.
# - ``labeled-data/``: sampled frames.

print(tree(source_project_dir / "videos", level=1, exclude_hidden=True))

# %%

print(tree(source_project_dir / "labeled-data", level=2, exclude_hidden=True))

# %%
# Define sessions to convert
# ---------------------------
# We select two sessions from the LP project and assign each to either
# the ``Train`` or ``Test`` split of the
# :ref:`benchmark dataset <target-benchmark-dataset>`.
# You may expand this list with more sessions, but ensure that each session
# belongs to exactly one split, and that the same subject doesn't appear in
# both splits (to avoid data leakage).

sessions = [
    {
        "split": "Train",
        "source_video": "6c6983ef73834989918332b1a300d17a_left.mp4",
        "sub_id": "SWC054",
        "ses_id": "6c6983ef73834989918332b1a300d17a",
        "cam_id": "left",
    },
    {
        "split": "Test",
        "source_video": "a92c4b1d46bd457ea1f4414265f0e2d4_left.mp4",
        "sub_id": "KS023",
        "ses_id": "a92c4b1d46bd457ea1f4414265f0e2d4",
        "cam_id": "left",
    },
]

project_name = "IBL-paw"

# %%
# Split the project-level annotation file
# ----------------------------------------
# Unlike DLC, Lightning Pose stores all session annotations in a single
# project-level ``CollectedData.csv``.  We split it into per-session
# ``CollectedData_<scorer>.csv`` files and create a temporary directory
# mirroring the ``labeled-data/`` structure with symlinks to the original
# frames.  This is necessary because the underlying loader (sleap-io)
# resolves image paths relative to the CSV location, so the split CSV
# must live alongside the frame images it references.

lp_session_base = benchmark_base_dir / ".lp_sessions"
split_results = split_lp_collected_data(
    input_path=source_project_dir / "CollectedData.csv",
    output_dir=lp_session_base,
)
for ses_name, split_csv in split_results.items():
    orig_frames_dir = source_project_dir / "labeled-data" / ses_name
    ses_dir = split_csv.parent
    for img in sorted(orig_frames_dir.glob("*.png")):
        (ses_dir / img.name).symlink_to(img)
print("Split annotation files:")
for ses_name, csv_path in split_results.items():
    print(f"  {ses_name}: {csv_path.name}")

# %%
# Convert to benchmark format
# ----------------------------
# For each session we:
#
# 1. copy (and re-encode, if necessary) the session video;
# 2. convert LP keypoint annotations to COCO JSON, as well as copy and
#    rename the corresponding frame images;
# 3. convert LP keypoint predictions to COCO JSON.

for session in sessions:
    split = session["split"]
    ids = {k: session[k] for k in ["sub_id", "ses_id", "cam_id"]}
    sub_ses_prefix = f"sub-{ids['sub_id']}_ses-{ids['ses_id']}"
    sub_ses_cam_prefix = f"{sub_ses_prefix}_cam-{ids['cam_id']}"
    source_video_path = source_project_dir / "videos" / session["source_video"]
    target_session_dir = (
        benchmark_base_dir / split / project_name / sub_ses_prefix
    )
    target_frames_dir = target_session_dir / "Frames"
    target_frames_dir.mkdir(parents=True, exist_ok=True)

    # LP session name matches ses_id + "_" + cam_id (e.g. labeled-data/ dir).
    video_stem = source_video_path.stem
    _lp_key = f"{session['ses_id']}_{session['cam_id']}"
    lp_session_name: str | None = _lp_key if _lp_key in split_results else None

    print(f"Converting session: {split}/{project_name}/{sub_ses_prefix}")
    # Copy the session video, re-encoding to H.264/yuv420p if necessary.
    video_to_poseinterface(
        input_video=source_video_path,
        output_video_dir=target_session_dir,
        **ids,
    )
    print(f"\tvideo: {source_video_path.name} -> {sub_ses_cam_prefix}.mp4")

    # Convert LP annotations to COCO frame labels JSON, then copy the
    # corresponding frame images with standardised poseinterface filenames.
    if lp_session_name is None:
        print(
            f"\tNo matching LP session found for {video_stem!r}."
            " Skipping annotations-to-poseinterface conversion."
        )
    else:
        # The split CSV lives in the temp dir alongside frame symlinks so
        # that sleap-io can resolve image paths relative to the CSV location.
        source_annotations_path = split_results[lp_session_name]
        # Use the original frames dir (not the symlinks) for the copy step.
        source_frames_dir = (
            source_project_dir / "labeled-data" / lp_session_name
        )
        framelabels_path = annotations_to_poseinterface(
            input_path=source_annotations_path,
            output_dir=target_frames_dir,
            format="frame",
            **ids,
        )
        frames_to_poseinterface(
            input_dir=source_frames_dir,
            output_dir=target_frames_dir,
            framelabels_path=framelabels_path,
        )
        print(
            f"\tannotations (+ frame images): "
            f"{source_annotations_path.name} -> {framelabels_path.name}"
        )

    # Convert LP predictions to COCO video labels JSON for clip extraction.
    # Prediction CSVs must be present in videos/ before running this script;
    # see the warning in the "Source Lightning Pose project" section above.
    source_predictions_path = next(
        (source_project_dir / "videos").glob(f"{video_stem}*.csv"),
        None,
    )
    if source_predictions_path is None:
        print(
            f"\tNo prediction CSV found for {video_stem!r} in "
            f"{source_project_dir / 'videos'}. Skipping predictions-to-"
            "poseinterface conversion."
        )
    else:
        predictions_to_poseinterface(
            input_path=source_predictions_path,
            video_path=source_video_path,
            output_dir=target_session_dir,
            **ids,
        )
        print(
            f"\tpredictions: {source_predictions_path.name} -> "
            f"{sub_ses_cam_prefix}_videolabels.json"
        )
    print("Done.\n")

# %%
# The resulting benchmark dataset:

print(tree(benchmark_base_dir, level=5, exclude_hidden=True))

# %%
# .. note::
#
#    Frame labels (``framelabels.json``) are generated for both splits,
#    but in the **published** dataset the ``Test`` split intentionally
#    omits them for evaluation. See the
#    :ref:`folder structure specification<target-benchmark-dataset>` for
#    details.
#
#    The ``videolabels.json`` files generated alongside each session video
#    are intermediate artifacts used for clip extraction in the next
#    section, and will not be included in the published dataset.


# %%
# Extract clips
# -------------
# Clips (short video segments) can be extracted from the converted session
# videos. When the ``videolabels.json`` files are present, the corresponding
# clip label files (``cliplabels.json``) are generated automatically during
# clip extraction.
# These clip label files should then be proof-read and corrected by
# experts before being included in the benchmark dataset.
#
# First, we specify the clip-extraction parameters. This step can be
# repeated with different parameters to incrementally expand the clip set.

duration = 5  # in frames
start_frames = [25, 50, 75]
print(f"Extracting {duration}-frame clips starting at frames: {start_frames}")

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
        clip_path, _ = extract_single_clip(
            video_path=session_dir / f"{sub_ses_cam_prefix}.mp4",
            start_frame=start_frame,
            duration=duration,
        )
        print(f"Extracted clip: {clip_path.stem}")


# %%
# The resulting benchmark dataset, including the extracted clips and their
# corresponding labels:

print(tree(benchmark_base_dir, level=5, exclude_hidden=True))


# %%
# .. note::
#
#    In the published dataset, the ``Train`` split includes all
#    ``cliplabels.json`` files. The ``Test`` split omits all
#    ``cliplabels.json`` files and instead provides only clip start labels
#    (``startlabels.json``), derived from each clip's first frame,
#    to support point-tracker evaluation.
#    The ``videolabels.json`` files generated in the previous section are
#    intermediate artifacts used for clip extraction, and are never shared.
#    See the :ref:`folder structure specification<target-benchmark-dataset>`
#    for details.


# %%
# Record provenance (optional)
# ----------------------------
# This step is optional and can be safely skipped, but it is highly
# recommended when converting real data, for book-keeping and
# reproducibility purposes.
#
# We save a copy of this script alongside a JSON sidecar with the
# ``poseinterface`` version (including git commit, via ``setuptools_scm``)
# and a UTC timestamp. Both files are written to a top-level
# ``.provenance/`` folder, named by project, so multiple projects under
# the same ``benchmark_base_dir`` stay distinct.

# sphinx_gallery_capture_repr = ()
provenance_dir = benchmark_base_dir / ".provenance"
provenance_dir.mkdir(parents=True, exist_ok=True)

# ``__file__`` is set when running this script directly with Python, but
# not when sphinx-gallery executes it during the docs build.
script_path_str = globals().get("__file__")
if script_path_str:
    shutil.copy(Path(script_path_str), provenance_dir / f"{project_name}.py")

(provenance_dir / f"{project_name}.json").write_text(
    json.dumps(
        {
            "poseinterface_version": poseinterface.__version__,
            "converted_at": datetime.now(timezone.utc).isoformat(),
            "source_project_dir": str(source_project_dir),
        },
        indent=2,
    )
)

# %%
# Clean up
# --------
# Since this example writes to a temporary directory, we remove it at the
# end.
#
# .. warning::
#
#    Only run this cell when ``benchmark_base_dir`` points to a temporary
#    location. The guard below refuses to delete anything outside the
#    system temp directory, so it is safe to leave in place when you adapt
#    this example to a real benchmark dataset path.

system_tempdir = Path(tempfile.gettempdir()).resolve()
target = benchmark_base_dir.resolve()
if target.is_relative_to(system_tempdir) and target != system_tempdir:
    shutil.rmtree(target)
    print(f"Removed temporary benchmark directory: {target}")
else:
    print(
        f"Refusing to remove {target}: not inside system temp dir "
        f"({system_tempdir}). Delete manually if you really want to."
    )
