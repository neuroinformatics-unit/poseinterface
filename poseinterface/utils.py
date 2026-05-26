"""General utility functions for ``poseinterface``."""

from collections.abc import Iterator
from itertools import islice
from pathlib import Path


def tree(
    dir_path: Path,
    *,
    level: int = -1,
    limit_to_directories: bool = False,
    exclude_hidden: bool = False,
    length_limit: int = 1000,
) -> str:
    """Return a visual tree structure of a directory as a string.

    Parameters
    ----------
    dir_path
        Path to the root directory.
    level
        Maximum depth to display. ``-1`` means no limit. Default is ``-1``.
    limit_to_directories
        If ``True``, only directories are shown. Default is ``False``.
    exclude_hidden
        If ``True``, files and directories starting with ``.`` are excluded.
        Default is ``False``.
    length_limit
        Maximum number of lines to include before truncating.
        Default is ``1000``.

    Returns
    -------
    str
        Tree representation of the directory structure, including a
        summary line with the count of directories and files.

    Notes
    -----
    Based on https://stackoverflow.com/a/59109706 by Aaron Hall, modified
    by community (see post 'Timeline' for change history).
    Retrieved 2026-03-27. License: CC BY-SA 4.0.

    Examples
    --------
    >>> from pathlib import Path
    >>> from poseinterface.utils import tree
    >>> print(tree(Path(".")))
    """
    space = "    "
    branch = "│   "
    tee = "├── "
    last = "└── "

    dir_path = Path(dir_path)
    files = 0
    directories = 0

    def _inner(
        dir_path: Path, prefix: str = "", level: int = -1
    ) -> Iterator[str]:
        nonlocal files, directories
        if not level:
            return
        contents = [
            d
            for d in sorted(dir_path.iterdir(), key=lambda d: d.name)
            if not (exclude_hidden and d.name.startswith("."))
        ]
        if limit_to_directories:
            contents = [d for d in contents if d.is_dir()]
        last_index = len(contents) - 1
        for index, path in enumerate(contents):
            pointer = last if index == last_index else tee
            if path.is_dir():
                yield prefix + pointer + path.name + "/"
                directories += 1
                extension = branch if pointer == tee else space
                yield from _inner(
                    path, prefix=prefix + extension, level=level - 1
                )
            elif not limit_to_directories:
                yield prefix + pointer + path.name
                files += 1

    lines: list[str] = [dir_path.name + "/"]
    iterator = _inner(dir_path, level=level)
    for line in islice(iterator, length_limit):
        lines.append(line)
    if next(iterator, None):
        lines.append(f"... length_limit, {length_limit}, reached, counted:")
    summary = f"\n{directories} directories"
    if files:
        summary += f", {files} files"
    lines.append(summary)
    return "\n".join(lines)
