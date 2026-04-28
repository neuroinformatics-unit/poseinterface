(target-contributing)=

# Contributing

`poseinterface` follows the same contribution workflow as `movement`.
See the [corresponding section of the movement contributing guide](https://movement.neuroinformatics.dev/latest/community/contributing.html#contribution-workflow).

## Development Environment

We use [uv](https://docs.astral.sh/uv/) for dependency management. To set up a development environment:

```bash
# Create dev environment with all dependency groups
uv sync --all-groups

# Activate the environment
source .venv/bin/activate  # On macOS and Linux
.venv\Scripts\activate     # On Windows PowerShell

# Set up pre-commit hooks
pre-commit install
```

## Formatting and pre-commit hooks
Running `pre-commit install` will set up [pre-commit hooks](https://pre-commit.com/) to ensure a consistent formatting style. Currently, these include:
* [ruff](https://github.com/astral-sh/ruff) does a number of jobs, including code linting and auto-formatting.
* [mypy](https://mypy.readthedocs.io/en/stable/index.html) as a static type checker.
* [check-manifest](https://github.com/mgedmin/check-manifest) to ensure that the right files are included in the pip package.
* [codespell](https://github.com/codespell-project/codespell) to check for common misspellings.

These will prevent code from being committed if any of these hooks fail.
To run all the hooks before committing:

```sh
pre-commit run  # for staged files
pre-commit run -a  # for all files in the repository
```

Some problems will be automatically fixed by the hooks. In this case, you should
stage the auto-fixed changes and run the hooks again:

```sh
git add .
pre-commit run
```

If a problem cannot be auto-fixed, the corresponding tool will provide
information on what the issue is and how to fix it. For example, `ruff` might
output something like:

```
E501 Line too long (81 > 79)
  --> poseinterface/io.py:83:80
```

This pinpoints the problem to a single code line and a specific [ruff rule](https://docs.astral.sh/ruff/rules/) violation.
Sometimes you may have good reasons to ignore a particular rule for a specific line of code. You can do this by adding an inline comment, e.g. `# noqa: E501`. Replace `E501` with the code of the rule you want to ignore.

For docstrings, we adhere to the [numpydoc](https://numpydoc.readthedocs.io/en/latest/format.html) style.
Make sure to provide docstrings for all public functions, classes, and methods.

## Tests

We use [pytest](https://docs.pytest.org/en/latest/) for testing, aiming for ~100% test coverage where feasible. All new features should be accompanied by tests.

To run tests and check coverage:

```bash
pytest -v --cov=poseinterface --cov-report=xml
```

### Test Data

Test CSV files in `tests/data/` represent two DLC CSV formats:
- `CollectedData_Pranav.csv`: Single-index format (path in one column)
- `CollectedData_Shailaja.csv`: Multi-index format (path split across 3 columns)

Sample benchmark data lives in `tests/data/Train/SWC-plusmaze/sub-M708149_ses-20200317/`
and conforms to the dataset spec (session video excluded from git).


## Documentation

The documentation is hosted via [GitHub pages](https://pages.github.com/) at
[poseinterface.neuroinformatics.dev](target-poseinterface).
Its source files are located in the `docs` folder of this repository.
They are written in either [MyST Markdown](myst-parser:syntax/typography.html) (preferred)
or [reStructuredText](https://docutils.sourceforge.io/rst.html).
The `index.md` file corresponds to the homepage of the documentation website.
Other `.md`  or `.rst` files are linked to the homepage via the `toctree` directive.

We use [Sphinx](sphinx-doc:) and the
[PyData Sphinx Theme](https://pydata-sphinx-theme.readthedocs.io/en/stable/index.html)
to build the source files into HTML output.
This is handled by a GitHub actions workflow:
`.github/workflows/docs_build_and_deploy.yml`.

To build the docs locally:

```bash
cd docs
make clean html
```

On Windows powershell, prepend `.\` to the make command.

You can preview the built docs at `docs/_build/html/index.html`.


### Continuous integration
All pushes and pull requests will be built by [GitHub actions](github-docs:actions).
This will usually include linting, testing and deployment.

A GitHub actions workflow (`.github/workflows/test_and_deploy.yml`) has been set up to run (on each push/PR):
* Linting checks (pre-commit).
* Testing (only if linting checks pass)
* Release to PyPI (only if a git tag is present and if tests pass).

Another workflow (`.github/workflows/docs_build_and_deploy.yml`) is set up to build and deploy the documentation to GitHub pages on each push to `main` and on releases (i.e. when a git tag is present).
