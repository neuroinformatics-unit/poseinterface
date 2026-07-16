[![License](https://img.shields.io/badge/License-BSD_3--Clause-orange.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![CI](https://img.shields.io/github/actions/workflow/status/neuroinformatics-unit/poseinterface/test_and_deploy.yml?label=CI)](https://github.com/neuroinformatics-unit/poseinterface/actions)
[![codecov](https://codecov.io/gh/neuroinformatics-unit/poseinterface/branch/main/graph/badge.svg?token=P8CCH3TI8K)](https://codecov.io/gh/neuroinformatics-unit/poseinterface)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/format.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

# poseinterface

**poseinterface** exists to advance pose estimation and point tracking
applications in animal behaviour videos. The project aims to:

- Build a [**benchmark dataset**](https://poseinterface.neuroinformatics.dev/benchmark-dataset.html)
  with dozens of videos and annotations from multiple institutes,
  open to external contributions.
- Develop a general-purpose **framework** for running pose estimation and
  point tracking tools on benchmark data, and for comparing their outputs
  via evaluation metrics.
- Provide **baseline models** trained using common pose estimation and tracking
  frameworks on the benchmark datasets.

Read the [documentation](https://poseinterface.neuroinformatics.dev/) for more information.

> [!Warning]
> This project is in early stages of development.
> The API is not stable and may change without warning.
> Use with caution.

## Installation

We recommend installing `poseinterface` in a virtual environment, using [uv](https://docs.astral.sh/uv/).

In your working directory, create a new environment and activate it:

```bash
uv venv --python=3.13
source .venv/bin/activate  # On macOS and Linux
.venv\Scripts\activate     # On Windows PowerShell
```

Then, install the package from PyPI:

```bash
uv pip install poseinterface
```

Or directly from the `main` branch on GitHub:

```bash
uv pip install git+https://github.com/neuroinformatics-unit/poseinterface.git@main
```

If you would like to contribute, see the
[contributing guide](https://poseinterface.neuroinformatics.dev/contributing.html),
which includes instructions for setting up a development environment.

## License
⚖️ [BSD 3-Clause](./LICENSE)

## Package template
This package layout and configuration (including pre-commit hooks and GitHub actions) have been copied from the [python-cookiecutter](https://github.com/neuroinformatics-unit/python-cookiecutter) template.
