# Benchmark project structure

This page describes the expected folder structure and file naming conventions for pose estimation benchmark datasets.

:::{note}
We mark requirements with italicised *keywords* that should be interpreted as described by the [Network Working Group](https://www.ietf.org/rfc/rfc2119.txt). In decreasing order of requirement, these are: *must*, *should*, and *may*.
:::

## Overview

A benchmark dataset is organised into a `Train` and a `Test` split. Each split contains one or more **projects** (i.e. datasets contributed by different groups). Each project contains one or more **sessions**. A session centres on a single video file (the **session video**), from which **frames** (individually sampled images) and optionally **clips** (short video segments) are extracted. In the `Train` split, frames and clips are accompanied by keypoint annotations.

The current scope is limited to **single-animal pose estimation** from a **single camera view**. Support for multi-camera setups is planned for a future version.

## Folder structure

```
.
├── Train/
│   └── <ProjectName>/
│       └── sub-<subjectID>_ses-<sessionID>/
│           ├── Frames/
│           │   ├── sub-<subjectID>_ses-<sessionID>_cam-<camID>_frame-<frameID>.png
│           │   ├── ...
│           │   └── sub-<subjectID>_ses-<sessionID>_cam-<camID>_framelabels.json
│           ├── Clips/    (optional)
│           │   ├── sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>.mp4
│           │   ├── sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>_cliplabels.json
│           │   └── ...
│           └── sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4
└── Test/
    └── <ProjectName>/
        └── sub-<subjectID>_ses-<sessionID>/
            ├── Frames/
            │   └── sub-<subjectID>_ses-<sessionID>_cam-<camID>_frame-<frameID>.png
            ├── Clips/    (optional)
            │   └── sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>.mp4
            └── sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4
```

:::{note}
The `Test` split follows the same structure as `Train`, but label files (`framelabels.json` and `cliplabels.json`) *must* not be included so that they can be used for evaluation.
:::

### Train / Test

* The top level *must* contain a `Train` and a `Test` folder.
* Each split *must* contain at least one project folder.

### Project

* Each project *must* have exactly one project-level folder within a given split.
* The project folder name *should* be descriptive and without spaces (e.g. `SWC-plusmaze`, `IBL-headfixed`, `AIND-openfield`).

### Session

* Each session *must* have exactly one session-level folder within a project.
* Session folder names *must* be formatted as `sub-<subjectID>_ses-<sessionID>`.
* `<subjectID>` and `<sessionID>` *must* be strictly alphanumeric (i.e. only `A-Z`, `a-z`, `0-9`).
* A session folder *must* contain exactly one session video file at its root.
* A session folder *must* contain a `Frames` folder.
* A session folder *may* contain a `Clips` folder.

:::{admonition} Examples
:class: tip

* valid: `sub-M708149_ses-20200317`, `sub-001_ses-01`
* invalid:
  * `mouse-M708149_ses-20200317`: the first key should be `sub`.
  * `sub-M708149_20200317`: missing the `ses` key.
  * `sub-M70_8149_ses-20200317`: underscores are not allowed within values (ambiguous parsing).
  * `sub-M70-8149_ses-2020-03-17`: hyphens are not allowed within values (ambiguous parsing).
:::

### Session video

* All video files (session videos and clips) *should* be in MP4 format (H.264 codec, yuv420p pixel format). Contributors *should* re-encode their videos to this format before submission (see [SLEAP documentation](https://docs.sleap.ai/latest/help/#usage) for guidance).
* Session video filenames *must* follow the pattern: `sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4`.

### Frames

The `Frames` folder contains individually sampled images and their annotations.

* Frames *must* be extracted from the session video.
* Frame images *must* be in PNG format.
* Frame image filenames *must* follow the pattern: `sub-<subjectID>_ses-<sessionID>_cam-<camID>_frame-<frameID>.png`.
* `<frameID>` *must* be the 0-based index of the frame in the session video.
* `<frameID>` *must* be padded to a consistent width across all frame files within a session (e.g. `0000`, `1000`).
* In the `Train` split, a single label file *must* be provided per camera view, named `sub-<subjectID>_ses-<sessionID>_cam-<camID>_framelabels.json`. At present, only one camera view is included, so the split contains exactly one such label file. See [Label format](#label-format) for details.

### Clips

A session *may* include a `Clips` folder containing short video segments and their annotations.

* Clips *must* be extracted from the session video and *must* have the same file format.
* Clip filenames *must* follow the pattern: `sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>.mp4`.
* `<frameID>` in the `start` field *must* be the 0-based index of the first frame of the clip in the session video, padded to a consistent width (e.g. `0500`, `1000`).
* `<nFrames>` in the `dur` field *must* be the duration of the clip in number of frames (e.g. `5`, `30`).
* In the `Train` split, a single label file *must* be provided per clip, named `sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>_cliplabels.json`. See [Label format](#label-format) for details.

## File naming

All filenames follow a key-value pair convention, similar to the [BIDS standard](https://bids-specification.readthedocs.io/en/stable/02-common-principles.html) and [NeuroBlueprint](https://neuroblueprint.neuroinformatics.dev/latest/specification.html).

* Filenames *must* consist of key-value pairs separated by underscores, with keys and values separated by hyphens. A filename *may* end with an additional suffix (not a key-value pair) before the extension:
  ```
  <key>-<value>_<key>-<value>.<extension>
  <key>-<value>_<key>-<value>_<suffix>.<extension>
  ```
  The recognised suffixes are `framelabels` (for frame label files) and `cliplabels` (for clip label files).
* The following keys are used:

| Key     | Description                                    | Examples         |
|---------|------------------------------------------------|-----------------|
| `sub`   | Subject identifier                             | `sub-001`, `sub-M708149`   |
| `ses`   | Session identifier                             | `ses-02`, `ses-25`, `ses-20200317`  |
| `cam`   | Camera identifier                              | `cam-topdown`, `cam-side2`   |
| `frame` | 0-based frame index in the session video        | `frame-0000`, `frame-0500`, `frame-1000`   |
| `start` | 0-based frame index of the first frame of a clip in the session video | `start-0000`, `start-0500`, `start-1000` |
| `dur`   | Clip duration in number of frames              | `dur-5`, `dur-30`         |

* The keys `sub`, `ses`, and `cam` *must* appear in every filename, in that order.
* Key values *must* be strictly alphanumeric for `sub`, `ses` and `cam` (i.e. only `A-Z`, `a-z`, `0-9`).
* Key values *must* be strictly numeric for `frame`, `start` and `dur` (i.e. only `0-9`).
* Filenames *must* not contain spaces.

## Label format

* Labels (also referred to as annotations) are only included in the `Train` split, and *must* be stored in the same folder as the corresponding frames or clips.
* Annotations *must* be stored in [COCO keypoints format](https://cocodataset.org/), with some additional requirements described below. Each label file is a JSON file with `images`, `annotations`, and `categories` arrays. Image, annotation and category `id` values *must* be unique integers within a label file.

:::{note}
Annotation and category `id` values *should* be 1-indexed. This convention follows sleap-io's [`save_coco`](https://io.sleap.ai/latest/reference/sleap_io/io/coco/) function and avoids conflicts with models that treat category `0` as background.

Image `id` indexing differs between frame and clip labels — see below for details.
:::

### Frame labels (`framelabels.json`)

* There *must* be one `framelabels.json` per camera view within the `Frames` folder.
* Each entry in the `images` array *must* have an `id` equal to the integer frame index in the session video (matching the `<frameID>` in the corresponding image filename).
* Each entry in the `images` array *must* have a `file_name` that matches the full filename (including the `.png` extension) of an existing frame image in the `Frames` folder.

:::{admonition} Example
:class: tip

For a session with 5 labelled frames sampled from different parts of the video, the `images` array would be:

```json
[
  {"id": 1000, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-01000.png", "width": 1300, "height": 1028},
  {"id": 2300, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-02300.png", "width": 1300, "height": 1028},
  {"id": 3500, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-03500.png", "width": 1300, "height": 1028},
  {"id": 7200, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-07200.png", "width": 1300, "height": 1028},
  {"id": 9800, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-09800.png", "width": 1300, "height": 1028}
]
```

Here each `id` is the frame index in the session video (matching the `<frameID>` in the filename), and each `file_name` includes the `.png` extension.
:::

### Clip labels (`cliplabels.json`)

* There *must* be one `cliplabels.json` per clip.
* The `images` array *must* contain an entry for every frame in the clip, in consecutive, monotonically increasing order (covering the entire clip duration).
* Clip labels follow the same COCO keypoints format as frame labels, but with different conventions for image `id` and `file_name` values:
  * Each image `id` *must* be the **0-based index of the frame within the clip** (i.e. `0`, `1`, `2`, ...), not the index in the session video.
  * Each `file_name` *must* follow the same pattern as frame image filenames, but **without the `.png` extension**. The `frame` field in the `file_name` *must* hold the index of that frame in the **session video**.

This means that each entry in the `images` array encodes two pieces of information: the `id` gives the local position within the clip, while the `frame` field in `file_name` gives the global position in the session video.

:::{admonition} Example
:class: tip

For a clip starting at frame 1000 with a duration of 5 frames, the `images` array would be:

```json
[
  {"id": 0, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-01000", "width": 1300, "height": 1028},
  {"id": 1, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-01001", "width": 1300, "height": 1028},
  {"id": 2, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-01002", "width": 1300, "height": 1028},
  {"id": 3, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-01003", "width": 1300, "height": 1028},
  {"id": 4, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-01004", "width": 1300, "height": 1028}
]
```

Here `id: 0` through `id: 4` are the local clip indices, while `frame-01000` through `frame-01004` in the `file_name` values refer to the original frame positions in the session video.
:::

### Visibility encoding

* Keypoint visibility *must* use ternary encoding:
  * `0`: not labelled
  * `1`: labelled but not visible (occluded)
  * `2`: labelled and visible

## Example

Below is a concrete example project structure (only the `Train` split is shown):

```
Train/
└── SWC-plusmaze/
    └── sub-M708149_ses-20200317/
        ├── Frames/
        │   ├── sub-M708149_ses-20200317_cam-topdown_frame-01000.png
        │   ├── sub-M708149_ses-20200317_cam-topdown_frame-02300.png
        │   ├── sub-M708149_ses-20200317_cam-topdown_frame-03500.png
        │   ├── sub-M708149_ses-20200317_cam-topdown_frame-07200.png
        │   ├── sub-M708149_ses-20200317_cam-topdown_frame-09800.png
        │   └── sub-M708149_ses-20200317_cam-topdown_framelabels.json
        ├── Clips/
        │   ├── sub-M708149_ses-20200317_cam-topdown_start-01000_dur-5.mp4
        │   └── sub-M708149_ses-20200317_cam-topdown_start-01000_dur-5_cliplabels.json
        └── sub-M708149_ses-20200317_cam-topdown.mp4
```
