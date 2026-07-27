(target-installation)=
# Installation

## Create a virtual environment

We recommend installing `poseinterface` in a virtual environment.
The instructions below use [uv](https://docs.astral.sh/uv/), but feel free to use any virtual-environment tool you are familiar with, including [conda](https://docs.conda.io/).

In your working directory, create and activate a new environment:

```sh
uv venv --python=3.13
source .venv/bin/activate  # On macOS and Linux
.venv\Scripts\activate     # On Windows PowerShell
```

## Install the package

With your environment activated, install the latest release of `poseinterface` from PyPI:

```sh
uv pip install poseinterface
```

Or, to get the latest development version from the `main` branch on GitHub:

```sh
uv pip install git+https://github.com/neuroinformatics-unit/poseinterface.git@main
```

`uv` may be omitted from these commands if it is not available;
`pip install ...` works in any standard virtual environment.

## Update the package

To update to the latest release:

```sh
uv pip install -U poseinterface
```

:::{admonition} For developers
:class: tip

If you would like to contribute to `poseinterface`, see the
[contributing guide](target-contributing) for developer setup instructions
and coding guidelines.
:::
