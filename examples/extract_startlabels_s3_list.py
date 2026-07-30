#!/usr/bin/env python3
"""Script to extract startlabels from multiple cliplabels files listed in a text file.

This script reads a text file containing S3 URIs to *_cliplabels.json files
(one per line) and processes each one to create corresponding *_startlabels.json
files.

Examples
--------
Process all files in a list:
    python extract_startlabels_s3_list.py cliplabels_list.txt

With AWS profile:
    python extract_startlabels_s3_list.py cliplabels_list.txt --profile my-profile

With verbose logging:
    python extract_startlabels_s3_list.py cliplabels_list.txt -v

Example input file (cliplabels_list.txt):
    s3://bucket/data/video1_cliplabels.json
    s3://bucket/data/video2_cliplabels.json
    s3://bucket/data/video3_cliplabels.json
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
        description="Extract startlabels from multiple cliplabels files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "input_file",
        help=(
            "Path to text file containing S3 URIs of *_cliplabels.json "
            "files (one per line)"
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

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help=(
            "Continue processing remaining files if one fails "
            "(default: stop on first error)"
        ),
    )

    return parser.parse_args()


def read_s3_uris(file_path: str) -> list[str]:
    """Read S3 URIs from a text file.

    Parameters
    ----------
    file_path
        Path to text file containing S3 URIs (one per line).

    Returns
    -------
    list[str]
        List of S3 URIs with empty lines and comments removed.
    """
    uris = []
    with open(file_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Basic validation
            if not line.startswith("s3://"):
                logging.warning(
                    f"Line {line_num}: Skipping invalid S3 URI: {line}"
                )
                continue
            uris.append(line)
    return uris


def main() -> int:
    """Main entry point for the script."""
    args = parse_args()
    setup_logging(args.verbose)

    # Read input file
    try:
        s3_uris = read_s3_uris(args.input_file)
    except FileNotFoundError:
        logging.error(f"Input file not found: {args.input_file}")
        return 1
    except Exception as e:
        logging.error(f"Error reading input file: {e}")
        return 1

    if not s3_uris:
        logging.error("No valid S3 URIs found in input file")
        return 1

    # Log operation details
    logging.info("=" * 60)
    logging.info("Batch Extract Start Labels from Cliplabels")
    logging.info("=" * 60)
    logging.info(f"Input file: {args.input_file}")
    logging.info(f"Total files to process: {len(s3_uris)}")
    if args.profile:
        logging.info(f"AWS Profile: {args.profile}")
    if args.continue_on_error:
        logging.info("Mode: Continue on error")
    logging.info("=" * 60)

    # Process each URI
    success_count = 0
    failed_uris = []

    for i, s3_uri in enumerate(s3_uris, 1):
        logging.info(f"\n[{i}/{len(s3_uris)}] Processing: {s3_uri}")

        try:
            output_uri = extract_startlabels_s3(
                s3_cliplabels_uri=s3_uri,
                aws_profile=args.profile,
            )
            logging.info(f"  ✓ Success: {output_uri}")
            success_count += 1

        except Exception as e:
            logging.error(f"  ✗ Failed: {e}")
            failed_uris.append((s3_uri, str(e)))

            if not args.continue_on_error:
                logging.error(
                    "\nStopping due to error. "
                    "Use --continue-on-error to process remaining files."
                )
                break

    # Summary
    logging.info("\n" + "=" * 60)
    logging.info("Processing Complete")
    logging.info("=" * 60)
    logging.info(f"Total processed: {i}/{len(s3_uris)}")
    logging.info(f"Successful: {success_count}")
    logging.info(f"Failed: {len(failed_uris)}")

    if failed_uris:
        logging.info("\nFailed files:")
        for uri, error in failed_uris:
            logging.info(f"  - {uri}")
            logging.info(f"    Error: {error}")

    logging.info("=" * 60)

    # Return appropriate exit code
    if failed_uris and not args.continue_on_error:
        return 1
    elif failed_uris:
        return 2  # Partial success
    else:
        return 0  # Complete success


if __name__ == "__main__":
    sys.exit(main())
