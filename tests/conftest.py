"""Pytest fixtures for poseinterface tests."""

import shutil
from pathlib import Path
from typing import Literal, TypedDict

import pytest
from PIL import Image

# Path to the directory containing the test data
TEST_DATA_DIR = Path(__file__).parent / "data"


class DLCTestFile(TypedDict):
    """Type definition for DLC test file configuration."""

    csv: str
    video_folder: str
    frames: list[str]


# Structure of DLC project files for testing
# the single-index project has the path in one column
# the multi-index project has the path split across 3 columns
DLC_TEST_PROJECT_FILES: dict[str, DLCTestFile] = {
    "single-index": {
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
    "multi-index": {
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


def create_dummy_frame(path: Path) -> None:
    """Create a minimal valid PNG file (1x1 transparent pixel)."""
    img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    img.save(path, "PNG")


def create_dlc_project(
    tmp_path: Path,
    dlc_csv_file_type: Literal["single-index", "multi-index"],
    csv_location: Literal["video_folder", "project_root"] = "video_folder",
) -> Path:
    """Create a mock DLC project structure with a CSV and dummy frame images.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory to create the project in.
    dlc_csv_file_type : str
        Type of DLC CSV file to create. Valid values are "single-index"
        or "multi-index". In the single-index case, the image path is fitted
        in one column. In the multi-index case, the image path is split across
        columns.
    csv_location : Literal["video_folder", "project_root"]
        Where to place the CSV file:
        - "video_folder": in labeled-data/<video_folder>/ (same as frames)
        - "project_root": in the project root directory (tmp_path)

    Returns
    -------
    Path
        Path to the CSV file within the mock DLC project.
    """
    project_structure = DLC_TEST_PROJECT_FILES[dlc_csv_file_type]

    # Create video folder under temporary pytest directory
    video_dir = tmp_path / "labeled-data" / project_structure["video_folder"]
    video_dir.mkdir(parents=True)

    # Copy CSV from the source (tests/data) to the appropriate location
    source_csv_path = TEST_DATA_DIR / project_structure["csv"]
    if csv_location == "video_folder":
        csv_path_in_project = video_dir / project_structure["csv"]
    else:  # project_root
        csv_path_in_project = tmp_path / project_structure["csv"]
    shutil.copy(source_csv_path, csv_path_in_project)

    # Create dummy PNG files for each frame
    for frame in project_structure["frames"]:
        create_dummy_frame(video_dir / frame)

    return csv_path_in_project


@pytest.fixture(scope="session")
def dlc_single_index_in_video_folder(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Mock DLC project: single-index CSV in video folder (same as frames)."""
    return create_dlc_project(
        tmp_path_factory.mktemp("dlc_single_video"),
        "single-index",
        csv_location="video_folder",
    )


@pytest.fixture(scope="session")
def dlc_single_index_in_project_root(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Mock DLC project: single-index CSV in project root."""
    return create_dlc_project(
        tmp_path_factory.mktemp("dlc_single_root"),
        "single-index",
        csv_location="project_root",
    )


@pytest.fixture(scope="session")
def dlc_multi_index_in_video_folder(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Mock DLC project: multi-index CSV in video folder (same as frames)."""
    return create_dlc_project(
        tmp_path_factory.mktemp("dlc_multi_video"),
        "multi-index",
        csv_location="video_folder",
    )


@pytest.fixture(scope="session")
def dlc_multi_index_in_project_root(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Mock DLC project: multi-index CSV in project root."""
    return create_dlc_project(
        tmp_path_factory.mktemp("dlc_multi_root"),
        "multi-index",
        csv_location="project_root",
    )
