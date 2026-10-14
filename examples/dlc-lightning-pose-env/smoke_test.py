"""Quick sanity check: both pose tools import in one interpreter and see the GPU."""

from importlib.metadata import distributions

import cv2
import deeplabcut
import lightning
import lightning_pose
import numpy
import torch

cv_pkgs = sorted(
    d.metadata["Name"]
    for d in distributions()
    if d.metadata["Name"].lower().startswith("opencv")
)

print(
    "torch          ", torch.__version__, "| cuda:", torch.cuda.is_available()
)
print("lightning      ", lightning.__version__)
print("numpy          ", numpy.__version__)
print("opencv         ", cv2.__version__, "| installed:", ", ".join(cv_pkgs))
print("deeplabcut     ", deeplabcut.__version__)
print("lightning_pose ", getattr(lightning_pose, "__version__", "ok"))

assert cv_pkgs == ["opencv-contrib-python-headless"], (
    f"expected only opencv-contrib-python-headless, got {cv_pkgs}"
)
print("OK")
