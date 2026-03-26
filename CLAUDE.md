# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**poseinterface** is a framework for benchmarking pose estimation and point tracking methods on animal behaviour videos. It's developed collaboratively by NIU (at SWC), IBL, and AIND. The project aims to provide benchmark datasets, tools for running and comparing pose estimation methods, and baseline models. Currently the main functionality is converting DLC annotations to COCO JSON format.

## Build, Test, and Lint Commands

```bash
# Create dev environment with uv
uv sync --all-extras

# Run tests with coverage
uv run pytest -v --cov=poseinterface --cov-report=xml

# Run tests across Python versions (3.11, 3.12, 3.13)
tox

# Linting and formatting (ruff)
uv run ruff check --config=pyproject.toml
uv run ruff format --config=pyproject.toml

# Type checking
uv run mypy poseinterface
# Run all pre-commit hooks
uv run pre-commit run --all-files

# Build documentation
cd docs && make clean html
```

## Architecture

The package has a single core module (`poseinterface/io.py`) with one main public function:

### `annotations_to_coco()`
- Converts pose annotation files (any format supported by sleap-io) to COCO JSON
- Supports custom image filenames and visibility encoding (ternary/binary)

### Internal Flow
1. Load annotations via sleap-io
2. Validate labeled frames exist and refer to a single video
3. Convert to COCO format via sleap-io
4. Save as JSON

### Key Dependencies
- **sleap-io**: Core library for loading/saving pose annotations (DLC, SLEAP, NWB, COCO)

## Code Style

- Line length: 79 characters
- Ruff rules: E (pycodestyle), F (Pyflakes), I (isort)
- Type hints expected (mypy enforced)
- Python version: 3.11+

## Documentation Structure

The docs site (`docs/source/`) uses Sphinx with pydata theme and MyST markdown:
- `about.md` — landing page with toctree linking to `mission.md`, `team.md`, `license.md`, `code-of-conduct.md`
- `benchmark_dataset.md` — benchmark dataset spec
- `auto_examples/` — sphinx-gallery examples
- `api_index.rst` — API reference

Copyright and authorship: "The poseinterface developers" (start year 2025).

## Benchmark Dataset Structure

The expected folder structure and file naming conventions for benchmark datasets are documented in `docs/source/benchmark_dataset.md`. Key points:

- Folder hierarchy: `Train/Test` > `<ProjectName>` > `sub-<subjectID>_ses-<sessionID>/`
- The main video file is called the **session video**
- Filenames use key-value pairs (`key-value`) separated by underscores; values must be strictly alphanumeric
- Label files use COCO keypoints JSON with additional constraints (see spec for frame vs clip label differences)
- Annotation/category IDs are 1-indexed (following sleap-io's `save_coco`)

## Test Data

Test CSV files in `tests/data/` represent two DLC CSV formats:
- `CollectedData_Pranav.csv`: Single-index format (path in one column)
- `CollectedData_Shailaja.csv`: Multi-index format (path split across 3 columns)

Sample benchmark data lives in `tests/data/Train/SWC-plusmaze/sub-M708149_ses-20200317/` and conforms to the dataset spec (session video excluded from git).
