from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, kw_only=True)
class Input:
    flag: str  # "--model"
    kind: Literal["file", "dir"] #
    suffixes: frozenset[str] = frozenset() # allowed file extensions, empty = any
    hint: str = ""  # shown in the GUI and in error messages


@dataclass(frozen=True, kw_only=True)
class Tool:
    module: str  # imported only inside the tool's env
    kind: Literal["point-tracker", "pose-estimator"]
    inputs: tuple[Input,...]
    label: str = ""  # GUI display name
    extra: str = ""  # pyproject extra, defaults to the tool name in cli.py:infer


VIDEO = Input(
    flag="--video",
    kind="file",
    suffixes=frozenset(".mp4"),
    hint="the video to run on",
)
STARTLABELS = Input(
    flag="--startlabels",
    kind="file",
    suffixes=frozenset(".json"),
)
TOOLS = {
    "cotracker3": Tool(
        module="poseinterface.tools.cotracker3.infer",
        kind="point-tracker",
        inputs=(VIDEO, STARTLABELS),
        label="CoTracker3",
    ),
}
