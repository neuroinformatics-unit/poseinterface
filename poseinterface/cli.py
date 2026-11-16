"""Command-line interface for poseinterface.

Usage::

    uvx "poseinterface[cotracker3]" infer --tool cotracker3 \
        --video <video> --startlabels <startlabels.json> [tool options]

``infer`` only parses ``--tool``; all remaining arguments are forwarded to
the tool's own ``parse_args``, so each tool defines its own options. Tool
modules are imported lazily, so tool-specific dependencies (e.g. ``torch``)
are only needed when that tool is used. They are installed through the
tool's optional-dependency set (``poseinterface[<tool>]``).
"""

import argparse
import importlib
import sys

from poseinterface.tools import TOOLS


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``poseinterface`` command."""
    parser = argparse.ArgumentParser(prog="poseinterface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add "infer" command
    infer_parser = subparsers.add_parser(
        "infer",
        help="Run a point tracker on a clip.",
        add_help=False,  # forward help to the tool parser
    )
    infer_parser.add_argument("--tool", choices=list(TOOLS), required=True)
    infer_parser.set_defaults(func=infer)

    # Parse ``--tool``; everything else is left for the tool's parser
    args, tool_argv = parser.parse_known_args(argv)
    args.func(args, tool_argv)


def infer(args: argparse.Namespace, tool_argv: list[str]) -> None:
    """Import the selected tool and run it with the forwarded arguments."""
    tool_spec = TOOLS[args.tool]

    try:
        tool_module = importlib.import_module(tool_spec.module)
    except ModuleNotFoundError as err:
        # err.name = name of the module that err-ed
        if err.name is None or err.name.startswith("poseinterface"):
            raise

        # For the rest: we assume that  extra not installed
        extra = tool_spec.extra or args.tool
        sys.exit(
            f"poseinterface: tool '{args.tool}' needs '{err.name}', "
            "which is not installed.\n"
            f"Install the tool's dependencies with:\n"
            f'    uvx "poseinterface[{extra}]" infer --tool {args.tool} ...\n'
            f"or:\n"
            f'    pip install "poseinterface[{extra}]"'
        )

    tool_module.main(tool_module.parse_args(tool_argv))


if __name__ == "__main__":
    main(sys.argv[1:])
