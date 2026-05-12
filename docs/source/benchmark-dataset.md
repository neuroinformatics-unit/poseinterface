(target-benchmark-dataset)=
# Benchmark dataset

This page describes the expected folder structure and file naming conventions for `poseinterface` benchmark datasets.

:::{note}
We mark requirements with italicised *keywords* that should be interpreted as described by the [Network Working Group](https://www.ietf.org/rfc/rfc2119.txt). In decreasing order of requirement, these are: *must*, *should*, and *may*.
:::

## Overview

- A benchmark dataset is organised into a `Train` and a `Test` split.
- Each split contains one or more [projects](#project) (i.e. datasets contributed by different groups).
- Each project contains one or more [sessions](#session).
- A session centres on a single video file (the [session video](#session-video)), from which [frames](#frames) (individually sampled images) and optionally [clips](#clips) (short video segments) are extracted.
- Frames and clips are accompanied by [label files](#label-format) in COCO keypoints format.

The current scope is limited to **single-animal pose estimation** from a **single camera view**. Support for multi-camera setups is planned for a future version.

## Folder structure

:::{note}
This specification describes both the **contributed** and the **published** versions of the dataset. Data contributors *must* provide full keypoint annotations (frame labels and clip labels) for both `Train` and `Test` splits. During the upload process, labels for the `Test` split are partially withheld to support evaluation. See [Label format](#label-format) for details.
:::

:::: {tab-set}

::: {tab-item} Contributed
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
            │   ├── sub-<subjectID>_ses-<sessionID>_cam-<camID>_frame-<frameID>.png
            │   ├── ...
            │   └── sub-<subjectID>_ses-<sessionID>_cam-<camID>_framelabels.json
            ├── Clips/    (optional)
            │   ├── sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>.mp4
            │   ├── sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>_cliplabels.json
            │   └── ...
            └── sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4
```
:::

::: {tab-item} Published
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
            │   ├── sub-<subjectID>_ses-<sessionID>_cam-<camID>_frame-<frameID>.png
            │   └── ...
            ├── Clips/    (optional)
            │   ├── sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>.mp4
            │   ├── sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>_startlabels.json
            │   └── ...
            └── sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4
```
:::

::::


### Train / Test

* The top level *must* contain a `Train` and a `Test` folder.
* Each split *must* contain at least one project folder.
* Each session *must* belong to exactly one split.

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

* All video files (session videos and clips) *should* be in MP4 format (H.264 codec, yuv420p pixel format). Data contributors *should* re-encode their videos to this format before submission (see [SLEAP documentation](https://docs.sleap.ai/latest/help/#usage) for guidance).
* Session video filenames *must* follow the pattern: `sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4`.

### Frames

The `Frames` folder contains individually sampled images and their label files.

* Frames *must* be extracted from the session video.
* Frame images *should* be in PNG format (`.png`). JPEG format (`.jpg` or `.jpeg`) *may* also be used.
* Frame image filenames *must* follow the pattern: `sub-<subjectID>_ses-<sessionID>_cam-<camID>_frame-<frameID>.<ext>`, where `<ext>` is `.png`, `.jpg`, or `.jpeg`.
* `<frameID>` *must* be the 0-based index of the frame in the session video.
* `<frameID>` *must* be padded to a consistent width across all frame files within a session (e.g. `0000`, `1000`).
* One frame label file (named `sub-<subjectID>_ses-<sessionID>_cam-<camID>_framelabels.json`) *must* be provided per camera view. At present, only one camera view is included, so each split contains exactly one such file. See [Label format](#label-format) for differences between contributed and published versions.

### Clips

A session *may* include a `Clips` folder containing short video segments and their label files.

* Clips *must* be extracted from the session video and *must* have the same file format.
* Clip filenames *must* follow the pattern: `sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>.mp4`.
* `<frameID>` in the `start` field *must* be the 0-based index of the first frame of the clip in the session video, padded to a consistent width (e.g. `0500`, `1000`).
* `<nFrames>` in the `dur` field *must* be the duration of the clip in number of frames (e.g. `5`, `30`).
* One clip label file (named `sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>_cliplabels.json`) *must* be provided per clip. See [Label format](#label-format) for differences between contributed and published versions.

## File naming

All filenames follow a key-value pair convention, similar to the [BIDS standard](https://bids-specification.readthedocs.io/en/stable/02-common-principles.html) and [NeuroBlueprint](https://neuroblueprint.neuroinformatics.dev/latest/specification.html).

* Filenames *must* consist of key-value pairs separated by underscores, with keys and values separated by hyphens. A filename *may* end with an additional suffix (not a key-value pair) before the extension:
  ```
  <key>-<value>_<key>-<value>.<extension>
  <key>-<value>_<key>-<value>_<suffix>.<extension>
  ```
  The recognised suffixes are:

  * `framelabels` for [frame label files](target-framelabels).
  * `cliplabels` for [clip label files](target-cliplabels).
  * `startlabels` for [clip start label files](target-startlabels).

* The following keys are used:

  | Key     | Description                                    | Value format   | Examples         |
  |---------|------------------------------------------------|----------------|-----------------|
  | `sub`   | Subject identifier                             | alphanumeric   | `sub-001`, `sub-M708149`   |
  | `ses`   | Session identifier                             | alphanumeric   | `ses-02`, `ses-25`, `ses-20200317`  |
  | `cam`   | Camera identifier                              | alphanumeric   | `cam-topdown`, `cam-side2`   |
  | `frame` | 0-based frame index in the session video        | numeric        | `frame-0000`, `frame-0500`, `frame-1000`   |
  | `start` | 0-based frame index of the first frame of a clip in the session video | numeric | `start-0000`, `start-0500`, `start-1000` |
  | `dur`   | Clip duration in number of frames              | numeric        | `dur-5`, `dur-30`         |

* The keys `sub`, `ses`, and `cam` *must* appear in every filename, in that order.
* Filenames *must* not contain spaces.

## Label format

* Data contributors *must* provide ground-truth keypoint annotations for both `Train` and `Test` splits: frame labels (`framelabels.json`) for sampled frames, and clip labels (`cliplabels.json`) for entire clips, if present.
* In the published dataset, the `Train` split includes all submitted labels. The `Test` split withholds frame labels and full clip labels to support evaluation; only clip start labels (`startlabels.json`), derived from the first frame of each clip's annotations, are published.
* Labels *must* be stored in the same folder as the corresponding frames or clips.
* Labels *must* be stored in [COCO keypoints format](https://cocodataset.org/#format-data), with additional requirements described below. Each label file is a JSON file with `images`, `annotations`, and `categories` arrays. Image, annotation and category `id` values *must* be unique integers within a label file.
* The `name` field in each `categories` entry *should* be the common English name of the species in lowercase (e.g. `"mouse"`, `"rat"`, `"zebrafish"`, `"macaque"`).

:::{note}
Annotation and category `id` values *should* be 1-indexed. This convention follows sleap-io's [`save_coco`](https://io.sleap.ai/latest/reference/sleap_io/io/coco/) function and avoids conflicts with models that treat category `0` as background.

Image `id` values are always 0-indexed. The indexing origin differs for frame labels and clip labels, and clip start labels follow the same conventions as clip labels. Details are provided below.

Complete examples of label files are available in the repository under [tests/data/Train](repo:tree/main/tests/data/Train).
:::

(target-framelabels)=
### Frame labels (`framelabels.json`)

* Within the `Frames` folder, there *must* be one frame label file per camera view, named `sub-<subjectID>_ses-<sessionID>_cam-<camID>_framelabels.json`.
* Each entry in the `images` array *must* have an `id` equal to the 0-based frame index in the session video (matching the `<frameID>` in the corresponding image filename).
* Each entry in the `images` array *must* have a `file_name` that exactly matches the name of an existing [frame image](#frames) in the `Frames` folder (including the extension).

:::{admonition} Example
:class: tip

For a session with 5 labelled frames sampled from different parts of the video, the `images` array would be:

```json
[
  {"id": 1000, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-01000.png", "width": 1300, "height": 1028},
  {"id": 2300, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-02300.png", "width": 1300, "height": 1028},
  {"id": 3500, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-03500.png", "width": 1300, "height": 1028},
  {"id": 7200, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-07200.png", "width": 1300, "height": 1028},
  {"id": 19800, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-19800.png", "width": 1300, "height": 1028}
]
```

Here each `id` is the 0-based frame index in the session video (matching the `<frameID>` in the filename), and each `file_name` includes the `.png` extension.
:::

(target-cliplabels)=
### Clip labels (`cliplabels.json`)

* If a `Clips` folder is present, there *must* be one clip label file per clip, named `sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>_cliplabels.json`.
* The `images` array *must* contain an entry for every frame in the clip, in consecutive, monotonically increasing order (covering the entire clip duration).
* Clip labels follow the same COCO keypoints format as frame labels, but with different conventions for image `id` and `file_name` values:
  * Each image `id` *must* be the **0-based index of the frame within the clip** (i.e. `0`, `1`, `2`, ...), not the index in the session video.
  * Each `file_name` *must* follow the same pattern as [frame image filenames](#frames), but **without the extension**. The `frame` field in the `file_name` *must* correspond to the index of that frame in the **session video**.

This means that each entry in the `images` array encodes two pieces of information: the `id` gives the local position within the clip, while the `frame` field in `file_name` gives the global position in the session video. Note that in both cases the indices are 0-based.

:::{admonition} Example
:class: tip

For a clip starting at frame 1000 with a duration of 5 frames, the `images` array would be:

```json
[
  {"id": 0, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-1000", "width": 1300, "height": 1028},
  {"id": 1, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-1001", "width": 1300, "height": 1028},
  {"id": 2, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-1002", "width": 1300, "height": 1028},
  {"id": 3, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-1003", "width": 1300, "height": 1028},
  {"id": 4, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-1004", "width": 1300, "height": 1028}
]
```

Here `id: 0` through `id: 4` are the local clip indices, while `frame-1000` through `frame-1004` in the `file_name` values refer to the original frame positions in the session video.
:::

(target-videolabels)=
#### Intermediate file `videolabels.json`

:::{note}
This file is **not a required part of a benchmark dataset**. It is an intermediate cache file useful for data contributors when preparing labelled clips, and it is documented here only because it is optionally auto-discovered by the `extract-clip` command and the corresponding `extract_clip` function.
:::

* A `videolabels.json` file uses the **same schema as [`cliplabels.json`](target-cliplabels)**, but it refers to a full video rather than to a clip of it.
* It is produced once per video (e.g. by converting model predictions for the entire video into the `cliplabels` schema) and reused to extract any number of clip label files from that video.
* When present alongside a session video as `sub-<subjectID>_ses-<sessionID>_cam-<camID>_videolabels.json`, the `extract-clip` command will slice it into per-clip `cliplabels.json` files matching the requested frame ranges.
* In the `videolabels.json` file, each entry in the `images` list uses the **0-based frame index in the video** as its `id` (same convention as [frame labels](target-framelabels)).

(target-startlabels)=
### Clip start labels (`startlabels.json`)

* Clip start labels only exist in the published `Test` split and are derived automatically from the contributed [clip labels](target-cliplabels) during the upload process.
* They are identical to [clip labels](target-cliplabels), except that the `images` array *must* contain exactly one entry (the first frame of the clip, with `id: 0`). They are intended for point-tracker evaluation, where the annotated points serve as the initial positions from which a tracker should propagate.

:::{admonition} Example
:class: tip

For a clip starting at frame 1000 with a duration of 5 frames, the `images` array would be:

```json
[
  {"id": 0, "file_name": "sub-M708149_ses-20200317_cam-topdown_frame-1000", "width": 1300, "height": 1028}
]
```
:::

### Visibility encoding

* Keypoint visibility *must* use ternary encoding:
  * `0`: not labelled
  * `1`: labelled but not visible (occluded)
  * `2`: labelled and visible

## Example

Below is a concrete example. A matching example dataset (with label files) is available in the repository under [tests/data/Train](repo:tree/main/tests/data/Train).

:::: {tab-set}

::: {tab-item} Contributed
```
.
├── Train/
│   └── SWC-plusmaze/
│       └── sub-M708149_ses-20200317/
│           ├── Frames/
│           │   ├── sub-M708149_ses-20200317_cam-topdown_frame-01000.png
│           │   ├── sub-M708149_ses-20200317_cam-topdown_frame-02300.png
│           │   ├── sub-M708149_ses-20200317_cam-topdown_frame-03500.png
│           │   ├── sub-M708149_ses-20200317_cam-topdown_frame-07200.png
│           │   ├── sub-M708149_ses-20200317_cam-topdown_frame-19800.png
│           │   └── sub-M708149_ses-20200317_cam-topdown_framelabels.json
│           ├── Clips/
│           │   ├── sub-M708149_ses-20200317_cam-topdown_start-1000_dur-5.mp4
│           │   └── sub-M708149_ses-20200317_cam-topdown_start-1000_dur-5_cliplabels.json
│           └── sub-M708149_ses-20200317_cam-topdown.mp4
└── Test/
    └── SWC-plusmaze/
        └── sub-M235678_ses-20210415/
            ├── Frames/
            │   ├── sub-M235678_ses-20210415_cam-topdown_frame-00500.png
            │   ├── sub-M235678_ses-20210415_cam-topdown_frame-01200.png
            │   ├── sub-M235678_ses-20210415_cam-topdown_frame-04800.png
            │   ├── sub-M235678_ses-20210415_cam-topdown_frame-09100.png
            │   ├── sub-M235678_ses-20210415_cam-topdown_frame-15300.png
            │   └── sub-M235678_ses-20210415_cam-topdown_framelabels.json
            ├── Clips/
            │   ├── sub-M235678_ses-20210415_cam-topdown_start-0500_dur-5.mp4
            │   └── sub-M235678_ses-20210415_cam-topdown_start-0500_dur-5_cliplabels.json
            └── sub-M235678_ses-20210415_cam-topdown.mp4
```
:::

::: {tab-item} Published
```
.
├── Train/
│   └── SWC-plusmaze/
│       └── sub-M708149_ses-20200317/
│           ├── Frames/
│           │   ├── sub-M708149_ses-20200317_cam-topdown_frame-01000.png
│           │   ├── sub-M708149_ses-20200317_cam-topdown_frame-02300.png
│           │   ├── sub-M708149_ses-20200317_cam-topdown_frame-03500.png
│           │   ├── sub-M708149_ses-20200317_cam-topdown_frame-07200.png
│           │   ├── sub-M708149_ses-20200317_cam-topdown_frame-19800.png
│           │   └── sub-M708149_ses-20200317_cam-topdown_framelabels.json
│           ├── Clips/
│           │   ├── sub-M708149_ses-20200317_cam-topdown_start-1000_dur-5.mp4
│           │   └── sub-M708149_ses-20200317_cam-topdown_start-1000_dur-5_cliplabels.json
│           └── sub-M708149_ses-20200317_cam-topdown.mp4
└── Test/
    └── SWC-plusmaze/
        └── sub-M235678_ses-20210415/
            ├── Frames/
            │   ├── sub-M235678_ses-20210415_cam-topdown_frame-00500.png
            │   ├── sub-M235678_ses-20210415_cam-topdown_frame-01200.png
            │   ├── sub-M235678_ses-20210415_cam-topdown_frame-04800.png
            │   ├── sub-M235678_ses-20210415_cam-topdown_frame-09100.png
            │   └── sub-M235678_ses-20210415_cam-topdown_frame-15300.png
            ├── Clips/
            │   ├── sub-M235678_ses-20210415_cam-topdown_start-0500_dur-5.mp4
            │   └── sub-M235678_ses-20210415_cam-topdown_start-0500_dur-5_startlabels.json
            └── sub-M235678_ses-20210415_cam-topdown.mp4
```
:::

::::
