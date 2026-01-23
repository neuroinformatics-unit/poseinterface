"""Pytest fixtures for poseinterface tests."""

import shutil
from pathlib import Path
from typing import TypedDict

import pytest


class DLCTestFile(TypedDict):
    """Type definition for DLC test file configuration."""

    csv: str
    video_folder: str
    frames: list[str]


DATA_DIR = Path(__file__).parent / "data"

# CSV files and their corresponding video folder names and frame filenames
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
    "loukia": {
        "csv": "CollectedData_Loukia.csv",
        "video_folder": "M708149_EPM_20200317_165049331-converted",
        "frames": [
            "img00000.png",
            "img00583.png",
            "img02343.png",
            "img02533.png",
            "img02549.png",
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


def create_dlc_project(tmp_path: Path, test_file_key: str) -> Path:
    """Create a mock DLC project structure with a CSV and dummy frame images.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory to create the project in.
    test_file_key : str
        Key from DLC_TEST_FILES ("pranav", "loukia", or "shailaja").

    Returns
    -------
    Path
        Path to the CSV file within the mock DLC project.
    """
    config = DLC_TEST_FILES[test_file_key]

    # Create labeled-data/<video_folder>/ structure
    video_dir = tmp_path / "labeled-data" / config["video_folder"]
    video_dir.mkdir(parents=True)

    # Copy CSV to video folder
    src_csv = DATA_DIR / config["csv"]
    dst_csv = video_dir / config["csv"]
    shutil.copy(src_csv, dst_csv)

    # Create dummy PNG files for each frame
    for frame in config["frames"]:
        create_dummy_png(video_dir / frame)

    return dst_csv


@pytest.fixture
def dlc_project_pranav(tmp_path: Path) -> Path:
    """Mock DLC project with Pranav CSV (slashes, no empty columns)."""
    return create_dlc_project(tmp_path, "pranav")


@pytest.fixture
def dlc_project_loukia(tmp_path: Path) -> Path:
    """Mock DLC project with Loukia CSV (slashes, empty columns)."""
    return create_dlc_project(tmp_path, "loukia")


@pytest.fixture
def dlc_project_shailaja(tmp_path: Path) -> Path:
    """Mock DLC project with Shailaja CSV (commas, empty columns)."""
    return create_dlc_project(tmp_path, "shailaja")
