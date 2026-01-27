"""Pytest fixtures for poseinterface tests."""

import shutil
from pathlib import Path
from typing import Literal, TypedDict

import pytest


class DLCTestFile(TypedDict):
    """Type definition for DLC test file configuration."""

    csv: str
    video_folder: str
    frames: list[str]


DATA_DIR = Path(__file__).parent / "data"

# CSV files and their corresponding video folder names and frame filenames
# "pranav" uses single-index format (path in one column)
# "shailaja" uses multi-index format (path split across 3 columns)
DLC_TEST_FILES: dict[str, DLCTestFile] = {
    "pranav": {
        "csv": "CollectedData_Pranav.csv",
        "video_folder": "m4s1",
        "frames": [
            "img0000.png",
            "img0001.png",
            "img0002.png",
            "img0003.png",
            "img0004.png",
        ],
    },
    "shailaja": {
        "csv": "CollectedData_Shailaja.csv",
        "video_folder": "1052533639_530862_20200924.face",
        "frames": [
            "img006825.png",
            "img020465.png",
            "img028360.png",
            "img053600.png",
            "img081960.png",
        ],
    },
}

# CSV location options for DLC project structure
CSVLocation = Literal["video_folder", "project_root"]


def create_dummy_png(path: Path) -> None:
    """Create a minimal valid PNG file (1x1 transparent pixel)."""
    # Minimal PNG: 1x1 transparent pixel
    # fmt: off
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    # fmt: on
    path.write_bytes(png_bytes)


def create_dlc_project(
    tmp_path: Path,
    test_file_key: str,
    csv_location: CSVLocation = "video_folder",
) -> Path:
    """Create a mock DLC project structure with a CSV and dummy frame images.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory to create the project in.
    test_file_key : str
        Key from DLC_TEST_FILES ("pranav" or "shailaja").
    csv_location : CSVLocation
        Where to place the CSV file:
        - "video_folder": in labeled-data/<video_folder>/ (same as frames)
        - "project_root": in the project root directory (tmp_path)

    Returns
    -------
    Path
        Path to the CSV file within the mock DLC project.
    """
    config = DLC_TEST_FILES[test_file_key]

    # Create labeled-data/<video_folder>/ structure
    video_dir = tmp_path / "labeled-data" / config["video_folder"]
    video_dir.mkdir(parents=True)

    # Copy CSV to the appropriate location
    src_csv = DATA_DIR / config["csv"]
    if csv_location == "video_folder":
        dst_csv = video_dir / config["csv"]
    else:  # project_root
        dst_csv = tmp_path / config["csv"]
    shutil.copy(src_csv, dst_csv)

    # Create dummy PNG files for each frame
    for frame in config["frames"]:
        create_dummy_png(video_dir / frame)

    return dst_csv


@pytest.fixture
def dlc_single_index_in_video_folder(tmp_path: Path) -> Path:
    """Mock DLC project: single-index CSV in video folder (same as frames)."""
    return create_dlc_project(tmp_path, "pranav", csv_location="video_folder")


@pytest.fixture
def dlc_single_index_in_project_root(tmp_path: Path) -> Path:
    """Mock DLC project: single-index CSV in project root."""
    return create_dlc_project(tmp_path, "pranav", csv_location="project_root")


@pytest.fixture
def dlc_multi_index_in_video_folder(tmp_path: Path) -> Path:
    """Mock DLC project: multi-index CSV in video folder (same as frames)."""
    return create_dlc_project(
        tmp_path, "shailaja", csv_location="video_folder"
    )


@pytest.fixture
def dlc_multi_index_in_project_root(tmp_path: Path) -> Path:
    """Mock DLC project: multi-index CSV in project root."""
    return create_dlc_project(
        tmp_path, "shailaja", csv_location="project_root"
    )
