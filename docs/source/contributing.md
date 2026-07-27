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

These hooks also run automatically on every pull request via
[pre-commit.ci](https://pre-commit.ci/) (except `mypy`, which is skipped there
but still runs locally and in the test workflow). If a hook auto-fixes
something, the bot will push the fix to your branch, so remember to pull before
continuing to work.

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


## Continuous integration
All pushes and pull requests will be built by [GitHub actions](github-docs:actions).
This will usually include linting, testing and deployment.

A GitHub actions workflow (`.github/workflows/test_and_deploy.yml`) has been set up to run (on each push/PR):
* Linting checks (pre-commit).
* Testing (only if linting checks pass)
* Release to PyPI (only if a git tag is present and if tests pass).
  Release tags must follow the `vX.Y.Z` format, e.g. `v0.1.0`.

Another workflow (`.github/workflows/docs_build_and_deploy.yml`) is set up to build and deploy the documentation to GitHub pages on each push to `main` and on releases (i.e. when a git tag is present).

## Contributing clip sampling strategies

The module {mod}`poseinterface.clips` is organised around three layers:

* **Core clip extraction**: two main functions:
    - {func}`~poseinterface.clips.extract_single_clip` writes a single ``.mp4`` clip (and its ``_cliplabels.json`` if a sibling ``*_videolabels.json`` exists).
    - {func}`~poseinterface.clips.extract_clips`
 applies the single clip extraction over a list of start frames.

* **Start-frame generators**: pure functions that return a ``list[int]`` of start frames given video-level parameters. They know nothing about I/O. See for example: `_uniform_start_frames`.

* **Strategy wrappers**: thin public functions that pair a start-frame generator with {func}`~poseinterface.clips.extract_clips`.  These are the entry points wired to the CLI. See for example: {func}`~poseinterface.clips.extract_clips_uniform`.

### Adding a new sampling strategy
1. Write a start-frame generator ``_<name>_start_frames(...)``
   that accepts whatever parameters the strategy needs and returns a list
   of integer start frames.  It must validate its own inputs and raise
   ``ValueError`` on bad input.
2. Write a wrapper ``extract_clips_<name>(video_path, duration, ...)``
   that calls your generator, then passes the result to {func}`~poseinterface.clips.extract_clips`.
3. Register the strategy in ``parse_args`` by adding ``"<name>"`` to
   the ``choices`` list of ``--sampling``, and a corresponding
   ``--<parameter>`` argument.
4. Dispatch to ``extract_clips_<name>`` in ``main``, following the
   pattern of the existing ``"uniform"`` branch.
