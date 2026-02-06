# Benchmark project structure

This page describes the expected folder structure and file naming conventions for pose estimation benchmark datasets.

:::{note}
We mark requirements with italicised *keywords* that should be interpreted as described by the [Network Working Group](https://www.ietf.org/rfc/rfc2119.txt). In decreasing order of requirement, these are: *must*, *should*, and *may*.
:::

## Overview

A benchmark dataset is organised into a `Train` and a `Test` split. Each split contains one or more **projects** (i.e. datasets contributed by different groups). Each project contains one or more **sessions**. A session centres on a single source video file, from which **frames** (individually sampled images) and optionally **clips** (short video segments) are extracted. In the `Train` split, frames and clips are accompanied by keypoint annotations.

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
The `Test` split follows the same structure as `Train`, but label files (`framelabels.json` and `cliplabels.json`) *must* not be included. Labels for the `Test` split are withheld so that they can be used to score submissions in benchmarking competitions.
:::

### Train / Test

* The top level *must* contain a `Train` and a `Test` folder.
* Each split *must* contain at least one project folder.

### Project

* Each project *must* have exactly one project-level folder within a given split.
* The project folder name *should* be descriptive and without spaces (e.g. `SWC-EPM`, `IBL-headfixed`, `AIND-openfield`).

### Session

* Each session *must* have exactly one session-level folder within a project.
* Session folder names *must* be formatted as `sub-<subjectID>_ses-<sessionID>`.
* `<subjectID>` and `<sessionID>` *must* be strictly alphanumeric (i.e. only `A-Z`, `a-z`, `0-9`).
* A session folder *must* contain exactly one full video file at its root.
* A session folder *must* contain a `Frames` folder.
* A session folder *may* contain a `Clips` folder.

:::{admonition} Examples
:class: tip

* valid: `sub-M708149_ses-20200317`, `sub-001_ses-01`
* invalid:
  * `mouse-M708149_ses-20200317`: the first key should be `sub`.
  * `sub-M708149_20200317`: missing the `ses` key.
  * `sub-M70_8149_ses-20200317`: underscores are not allowed within values (ambiguous parsing).
  * `sub-M70-8149_ses-2020-03-17`: hyphens are not allowed within values.
:::

### Full video

* Full video files *should* be in MP4 format (H.264 codec, yuv420p pixel format).
* Full video filenames *must* follow the pattern: `sub-<subjectID>_ses-<sessionID>_cam-<camID>.mp4`.

### Frames

The `Frames` folder contains individually sampled images and their annotations. Frames *must* be extracted from the session's source video.

* Frame images *must* be in PNG format.
* Frame image filenames *must* follow the pattern: `sub-<subjectID>_ses-<sessionID>_cam-<camID>_frame-<frameID>.png`.
* `<frameID>` *must* be the 0-based index of the frame in the source video.
* `<frameID>` *must* be zero-padded to a consistent width (e.g. `01000`, `01001`). The padded width *should* be the same across all frame files within a session.
* In the `Train` split, a single label file *must* be provided per camera view, named `sub-<subjectID>_ses-<sessionID>_cam-<camID>_framelabels.json`. See [Label format](#label-format) for details.

### Clips

A session *may* include a `Clips` folder containing short video segments and their annotations. Clips *must* be extracted from the session's source video.

* Clip videos *must* be in MP4 format (H.264 codec, yuv420p pixel format).
* Clip filenames *must* follow the pattern: `sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>.mp4`.
* `<frameID>` in the `start` field *must* be the 0-based index of the first frame of the clip in the source video, zero-padded to a consistent width.
* `<nFrames>` in the `dur` field *must* be the duration of the clip in number of frames.
* In the `Train` split, a single label file *must* be provided per clip, named `sub-<subjectID>_ses-<sessionID>_cam-<camID>_start-<frameID>_dur-<nFrames>_cliplabels.json`. See [Label format](#label-format) for details.

## File naming

All filenames follow a key-value pair convention, similar to the [BIDS standard](https://bids-specification.readthedocs.io/en/stable/02-common-principles.html) and [NeuroBlueprint](https://neuroblueprint.neuroinformatics.dev/latest/specification.html).

* Filenames *must* consist of key-value pairs separated by underscores, with keys and values separated by hyphens. A filename *may* end with an additional suffix (not a key-value pair) before the extension, e.g. for label files:
  ```
  <key>-<value>_<key>-<value>.<extension>
  <key>-<value>_<key>-<value>_<suffix>.<extension>
  ```
* The following keys are used:

| Key     | Description                                    | Example         |
|---------|------------------------------------------------|-----------------|
| `sub`   | Subject identifier                             | `sub-M708149`   |
| `ses`   | Session identifier                             | `ses-20200317`  |
| `cam`   | Camera identifier                              | `cam-topdown`   |
| `frame` | 0-based frame index in the source video        | `frame-01000`   |
| `start` | 0-based frame index of the first frame of a clip | `start-01000` |
| `dur`   | Clip duration in number of frames              | `dur-5`         |

* The keys `sub`, `ses`, and `cam` *must* appear in every filename, in that order.
* Key values *must* be strictly alphanumeric (i.e. only `A-Z`, `a-z`, `0-9`). Since underscores separate key-value pairs and hyphens separate keys from values, neither character is allowed within values.
* Filenames *must* not contain spaces.

## Label format

Annotations *must* be stored in [COCO keypoints format](https://cocodataset.org/#format-data). Each label file is a JSON file with `images`, `annotations`, and `categories` fields.

### Frame labels (`framelabels.json`)

* There *must* be one `framelabels.json` per camera view within the `Frames` folder (in the `Train` split only).
* Each entry in the `images` array *must* have an `id` equal to the integer frame index in the source video (matching the `<frameID>` in the corresponding image filename).
* Each entry in the `images` array *must* have a `file_name` matching the corresponding frame image filename.

### Clip labels (`cliplabels.json`)

* There *must* be one `cliplabels.json` per clip (in the `Train` split only).
* Clip labels follow the same COCO keypoints format as frame labels. The frames within a clip are consecutive.

### Visibility encoding

* Keypoint visibility *must* use ternary encoding:
  * `0`: not labelled
  * `1`: labelled but not visible (occluded)
  * `2`: labelled and visible

## Video format

* All video files (full videos and clips) *should* be encoded as MP4 with the H.264 codec and yuv420p pixel format.
* Contributors *should* re-encode their videos to this format before submission (see [SLEAP documentation](https://sleap.ai/help.html#does-my-data-need-to-be-in-a-particular-format) for guidance).

## Example

Below is a concrete example based on a real contributed session:

```
Train/
└── SWC-EPM/
    └── sub-M708149_ses-20200317/
        ├── Frames/
        │   ├── sub-M708149_ses-20200317_cam-topdown_frame-01000.png
        │   ├── sub-M708149_ses-20200317_cam-topdown_frame-01001.png
        │   ├── sub-M708149_ses-20200317_cam-topdown_frame-01002.png
        │   ├── sub-M708149_ses-20200317_cam-topdown_frame-01003.png
        │   ├── sub-M708149_ses-20200317_cam-topdown_frame-01004.png
        │   └── sub-M708149_ses-20200317_cam-topdown_framelabels.json
        ├── Clips/
        │   ├── sub-M708149_ses-20200317_cam-topdown_start-01000_dur-5.mp4
        │   └── sub-M708149_ses-20200317_cam-topdown_start-01000_dur-5_cliplabels.json
        └── sub-M708149_ses-20200317_cam-topdown.mp4
```
