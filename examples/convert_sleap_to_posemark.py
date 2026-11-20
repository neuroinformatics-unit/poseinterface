"""Convert SLEAP project to the PoseMark format
=============================================

Prepare a SLEAP project to be contributed
to the *PoseMark* corpus.
"""

# %%
# Imports
# -------
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import imageio.v3 as iio
import sleap_io as sio

import poseinterface
from poseinterface.clips import extract_single_clip
from poseinterface.io import (
    annotations_to_posemark,
    predictions_to_posemark,
    video_to_posemark,
)
from poseinterface.utils import tree

# %%
# Overview
# --------
# We'll handle the conversion in two steps:
#
# 1. **Convert:** SLEAP project files (videos, frame annotations, and
#    keypoint predictions) are restructured into the
#    :ref:`PoseMark format <target-posemark>`.
# 2. **Extract clips:** Short video clips and their labels are extracted
#    from the converted videos and their corresponding keypoint
#    predictions, ready for expert review.
#
# The workflow is similar to the one followed in
# :ref:`sphx_glr_auto_examples_convert_dlc_to_posemark.py`,
# with a few differences explained below.

# %%
# Source SLEAP project
# --------------------
# We work with a dataset from the
# `Sainsbury Wellcome Centre (SWC) <https://www.sainsburywellcome.org/>`_,
# produced by Loukia Katsouri from John O'Keefe's lab.
# It contains single-animal top-down videos of mice exploring an
# Elevated Plus Maze (EPM), analysed using
# `SLEAP <https://sleap.ai/>`_.
#
# .. note::
#
#    This example runs against a lightweight fixture shipped with the
#    repository (under ``tests/data/``). This fixture contains only a subset
#    of the original project, and is intended for testing and demonstration
#    purposes.
#
#    Replace ``source_project_dir`` and ``posemark_base_dir`` with the paths
#    to your SLEAP project and *PoseMark* directories, respectively. Keep
#    in mind that your project will contain more files than are shown here.

source_project_dir = (
    Path(".").resolve().parent
    / "tests"
    / "data"
    / "sleap"
    / "MouseTopDown-EPM"
)
print(tree(source_project_dir, level=1, exclude_hidden=True))

# For this example we use a temporary directory, cleaned up at the end.
posemark_base_dir = Path(tempfile.mkdtemp(prefix="posemark-"))
print(f"\nPoseMark dataset will be saved to: {posemark_base_dir}")

# %%
# The SLEAP project differs from a DLC project in a few key respects:
#
# - All annotations live in a **single project-level** labels file
#   (``labels.v001.slp``), which may cover multiple videos.
# - Labeled frames are not stored as separate image files. In this example
#   they are read directly from the videos referenced by the labels file
#   (SLEAP package files, ``.pkg.slp``, embed images as an HDF5 image dataset).
# - Predictions are stored per video in ``predictions/``, as
#   ``.predictions.slp`` files.
#
# Let's load the labels file and inspect the videos it references.

labels = sio.load_file(source_project_dir / "labels.v001.slp")
print(labels)
for video in labels.videos:
    print(video.filename)

# %%
# The video paths stored in the labels file are absolute paths on the
# machine where the project was created. If the project has since been moved,
# we need to point them to the videos' new location.

old_project_dir = "/home/user/sleap-projects/MouseTopDown-EPM"
labels.replace_filenames(
    prefix_map={old_project_dir: source_project_dir.as_posix()}
)
for video in labels.videos:
    print(video.filename, "exists:", video.exists())

# %%
# Define sessions to convert
# ---------------------------
# We select two sessions from the SLEAP project and assign each to either
# the ``Train`` or ``Test`` split of the
# :ref:`PoseMark <target-posemark>`.
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

# %%
# Convert to PoseMark format
# ----------------------------
# For each session we:
#
# 1. copy (and re-encode, if necessary) the session video;
# 2. extract the session's user annotations from the labels file,
#    convert them to COCO JSON, and save the labeled frames as images;
# 3. convert SLEAP predictions to COCO JSON.
#
# Since :func:`~poseinterface.io.annotations_to_posemark` expects
# annotations for a single video, we first extract each session's
# annotations and save them to a per-session ``.slp`` file in a temporary
# directory, kept separate from ``posemark_base_dir`` and removed
# automatically after conversion.

for session in sessions:
    split = session["split"]
    ids = {k: session[k] for k in ["sub_id", "ses_id", "cam_id"]}
    sub_ses_prefix = f"sub-{ids['sub_id']}_ses-{ids['ses_id']}"
    sub_ses_cam_prefix = f"{sub_ses_prefix}_cam-{ids['cam_id']}"
    source_video_path = source_project_dir / "videos" / session["source_video"]
    target_session_dir = (
        posemark_base_dir / split / project_name / sub_ses_prefix
    )
    target_frames_dir = target_session_dir / "Frames"
    target_frames_dir.mkdir(parents=True, exist_ok=True)

    print(f"Converting session: {split}/{project_name}/{sub_ses_prefix}")
    # Copy the session video, re-encoding to H.264/yuv420p if necessary
    video_to_posemark(
        input_video=source_video_path,
        output_video_dir=target_session_dir,
        **ids,
    )
    print(f"\tvideo: {source_video_path.name} -> {sub_ses_cam_prefix}.mp4")

    # Extract this session's user annotations (dropping any predicted
    # instances), save them to a temporary per-session labels file, and
    # convert them to COCO frame labels JSON.
    session_labels = labels.extract(source_video_path)
    session_labels.remove_predictions()
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_labels_path = Path(tmp_dir) / f"{source_video_path.stem}.slp"
        session_labels.save(session_labels_path)
        framelabels_path = annotations_to_posemark(
            input_path=session_labels_path,
            output_dir=target_frames_dir,
            format="frame",
            **ids,
        )

    # Save the labeled frames, read from the video, with standardised
    # PoseMark filenames.
    video = session_labels.video
    for image in json.loads(framelabels_path.read_text())["images"]:
        frame = video[image["id"]].squeeze()
        iio.imwrite(target_frames_dir / image["file_name"], frame)
    print(
        f"\tannotations (+ frame images): {session_labels_path.name} "
        f"-> {framelabels_path.name}"
    )

    # Convert SLEAP predictions to COCO video labels JSON for clip extraction.
    # The default predictions output path varies depending on whether
    # inference was run from the SLEAP GUI or the ``sleap predict`` command,
    # and on its inputs. Here we assume predictions were generated from the
    # GUI, which saves them to a ``predictions/`` folder alongside the labels
    # file, and pick the most recent run. Adjust the directory and glob
    # pattern below accordingly.
    source_predictions_path = max(
        (source_project_dir / "predictions").glob(
            f"{source_video_path.name}*.slp"
        ),
        default=None,
    )
    if source_predictions_path is None:
        print(
            f"\tNo predictions found for {source_video_path.stem!r} in "
            f"{source_project_dir / 'predictions'}. Skipping predictions-to-"
            "PoseMark conversion."
        )
    else:
        predictions_to_posemark(
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
# The resulting *PoseMark* dataset:

print(tree(posemark_base_dir, level=5))

# %%
# .. note::
#
#    Frame labels (``framelabels.json``) are generated for both splits, but in
#    the **published** dataset the ``Test`` split intentionally omits them for
#    evaluation. See the :ref:`folder structure specification
#    <target-posemark-folder-structure>` for details.
#
#    The ``videolabels.json`` files generated alongside each session video are
#    intermediate artifacts used for clip extraction in the next section, and
#    will not be included in the published dataset.


# %%
# Extract clips
# -------------
# Clips (short video segments) can be extracted from the converted session
# videos. When the ``videolabels.json`` files are present, the corresponding
# clip label files (``cliplabels.json``) are generated automatically during
# clip extraction.
# These clip label files should then be proof-read and corrected by
# experts before being included in *PoseMark*.
#
# First, we specify the clip-extraction parameters. This step can be repeated
# with different parameters to incrementally expand the clip set.

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
        posemark_base_dir / session["split"] / project_name / sub_ses_prefix
    )

    for start_frame in start_frames:
        clip_path, _ = extract_single_clip(
            video_path=session_dir / f"{sub_ses_cam_prefix}.mp4",
            start_frame=start_frame,
            duration=duration,
        )
        print(f"Extracted clip: {clip_path.stem}")


# %%
# The resulting *PoseMark* dataset, including the extracted clips and their
# corresponding labels:

print(tree(posemark_base_dir, level=5))


# %%
# .. note::
#
#    In the published dataset, the ``Train`` split includes all
#    ``cliplabels.json`` files, while the ``Test`` split omits them. Clip
#    start labels (``startlabels.json``) are automatically derived during
#    data submission from each clip's first frame, and are included in
#    both splits to support point-tracker evaluation.
#    The ``videolabels.json`` files generated in the previous section are
#    intermediate artifacts used for clip extraction, and are never shared.
#    See the :ref:`folder structure specification
#    <target-posemark-folder-structure>` for details.


# %%
# Record provenance (optional)
# ----------------------------
# This step is optional and can be safely skipped, but it is highly recommended
# when converting real data, for book-keeping and reproducibility purposes.
#
# We save a copy of this script alongside a JSON sidecar with the
# ``poseinterface`` version (including git commit, via ``setuptools_scm``)
# and a UTC timestamp. Both files are written to a top-level
# ``.provenance/`` folder, named by project, so multiple projects under the
# same ``posemark_base_dir`` stay distinct.

# sphinx_gallery_capture_repr = ()
provenance_dir = posemark_base_dir / ".provenance"
provenance_dir.mkdir(parents=True, exist_ok=True)

# ``__file__`` is set when running this script directly with Python, but not
# when sphinx-gallery executes it during the docs build, guard accordingly.
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
# Since this example writes to a temporary directory, we remove it at the end.
#
# .. warning::
#
#    Only run this cell when ``posemark_base_dir`` points to a temporary
#    location. The guard below refuses to delete anything outside the system
#    temp directory, so it is safe to leave in place when you adapt this
#    example to a real *PoseMark* dataset path.

system_tempdir = Path(tempfile.gettempdir()).resolve()
target = posemark_base_dir.resolve()
if target.is_relative_to(system_tempdir) and target != system_tempdir:
    shutil.rmtree(target)
    print(f"Removed temporary PoseMark directory: {target}")
else:
    print(
        f"Refusing to remove {target}: not inside system temp dir "
        f"({system_tempdir}). Delete manually if you really want to."
    )
