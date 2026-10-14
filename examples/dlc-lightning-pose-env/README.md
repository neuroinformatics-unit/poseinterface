# DeepLabCut + Lightning Pose environment

One Python 3.11 environment, managed with [uv](https://docs.astral.sh/uv/),
containing **DeepLabCut 3.0.2** and **Lightning Pose 2.4.2** with no
dependency conflicts. `uv.lock` pins every package, so everyone gets the
identical environment.

Works on Linux with an NVIDIA GPU (full functionality), Apple Silicon Macs
(CPU/MPS; Lightning Pose reads video with OpenCV instead of DALI), and
Windows via WSL2.

## Install

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # or: brew install uv
uv sync --frozen --no-install-project
uv run python smoke_test.py                       # prints versions, ends with OK
```

System libraries for video I/O: Linux `apt install ffmpeg libgl1 libglib2.0-0`,
macOS `brew install ffmpeg`.

## Files

| File | Purpose |
|---|---|
| `pyproject.toml` | dependencies and the OpenCV override |
| `uv.lock` | exact pinned versions (156 packages) |
| `.python-version` | Python 3.11 |
| `smoke_test.py` | imports both tools in one interpreter, checks GPU and OpenCV |

## Notes

- **OpenCV**: the dependency tree asks for three OpenCV builds
  (`opencv-python`, `opencv-contrib-python`, `opencv-python-headless`) that
  all install the same `cv2` and overwrite each other. `[tool.uv]
  override-dependencies` removes them; `opencv-contrib-python-headless` is
  the single build used (all modules, no GUI).
- **NVIDIA DALI** (Lightning Pose's GPU video reader) exists only for Linux
  x86_64; elsewhere Lightning Pose falls back to OpenCV. Semi-supervised
  (video-loss) training still needs Linux + CUDA.
