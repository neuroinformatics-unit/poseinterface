#!/usr/bin/env python3
"""Script to extract first frame labels from cliplabels.json files on S3.

This script reads a *_cliplabels.json file from S3 and creates a corresponding
*_startlabels.json file containing only the labels for the first frame (frame
with id=0).

Examples
--------
Extract with automatic output naming:
    python extract_startlabels.py s3://bucket/path/video_cliplabels.json

Specify custom output location:
    python extract_startlabels.py s3://bucket/path/video_cliplabels.json \\
        s3://bucket/output/video_startlabels.json

Use specific AWS profile:
    python extract_startlabels.py s3://bucket/path/video_cliplabels.json \\
        --profile my-profile
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path to import poseinterface
sys.path.insert(0, str(Path(__file__).parent.parent))

from poseinterface.clips import extract_startlabels_s3


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the script."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract first frame labels from cliplabels.json on S3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "input",
        help="Input S3 URI for *_cliplabels.json file (e.g., s3://bucket/path/video_cliplabels.json)",
    )

    parser.add_argument(
        "output",
        nargs="?",
        help=(
            "Output S3 URI for *_startlabels.json file (optional). "
            "If not provided, automatically derived from input by replacing "
            "_cliplabels.json with _startlabels.json"
        ),
    )

    parser.add_argument(
        "--profile",
        help="AWS profile name to use for authentication",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point for the script."""
    args = parse_args()
    setup_logging(args.verbose)

    # Log operation details
    logging.info("=" * 60)
    logging.info("Extract Start Labels from Cliplabels")
    logging.info("=" * 60)
    logging.info(f"Input:  {args.input}")

    if args.output:
        logging.info(f"Output: {args.output}")
    else:
        logging.info("Output: (auto-generated from input)")

    if args.profile:
        logging.info(f"AWS Profile: {args.profile}")

    logging.info("=" * 60)

    # Perform the extraction
    try:
        output_uri = extract_startlabels_s3(
            s3_cliplabels_uri=args.input,
            output_uri=args.output,
            aws_profile=args.profile,
        )

        logging.info("=" * 60)
        logging.info("✓ Extraction completed successfully!")
        logging.info(f"  Output written to: {output_uri}")
        logging.info("=" * 60)
        return 0

    except ValueError as e:
        logging.error(f"Validation error: {e}")
        return 1

    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        return 1

    except KeyboardInterrupt:
        logging.warning("\nOperation interrupted by user")
        return 130

    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
