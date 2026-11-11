"""Command-line interface for poseinterface.

Usage::

    poseinterface infer --tool cotracker3 --video <video> \
        --startlabels <startlabels.json> [tool options]

``infer`` only parses ``--tool``; all remaining arguments are forwarded to
the tool's own ``parse_args``, so each tool defines its own options. Tool
modules are imported lazily, so tool-specific dependencies (e.g. ``torch``)
are only needed when that tool is used.
"""

import argparse
import importlib
import sys

# Tool name -> module defining ``parse_args(args)`` and ``main(args)``.
TOOLS = {
    "cotracker3": "poseinterface.tools.cotracker3.infer",
}


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``poseinterface`` command."""
    parser = argparse.ArgumentParser(prog="poseinterface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add_help=False so ``--help`` is forwarded to the tool's parser
    infer_parser = subparsers.add_parser(
        "infer",
        help="Run a point tracker on a clip.",
        add_help=False,
    )
    infer_parser.add_argument("--tool", choices=list(TOOLS), required=True)

    args, tool_argv = parser.parse_known_args(argv)

    if args.command == "infer":
        tool = importlib.import_module(TOOLS[args.tool])
        tool.main(tool.parse_args(tool_argv))


if __name__ == "__main__":
    main(sys.argv[1:])
