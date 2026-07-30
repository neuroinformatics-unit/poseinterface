#!/usr/bin/env python3
"""Script to copy S3 folders with file filtering and rollback support.

This script copies a folder from one S3 location to another, with support for:
- Excluding files based on filename patterns
- Automatic rollback if the copy fails partway through
- Progress tracking and logging

Examples
--------
Copy entire folder:
    python copy_s3_folder.py s3://source-bucket/data/ s3://dest-bucket/backup/

Copy with file pattern exclusions:
    python copy_s3_folder.py s3://source-bucket/data/ s3://dest-bucket/backup/ \\
        --exclude "*.log" --exclude "temp_*" --exclude "debug.txt"

Copy excluding specific subdirectories:
    python copy_s3_folder.py s3://source-bucket/data/ s3://dest-bucket/backup/ \\
        --exclude "Test/*" --exclude "*/temp/*"

Copy excluding specific files in specific directories:
    python copy_s3_folder.py s3://source-bucket/data/ s3://dest-bucket/backup/ \\
        --exclude "Test/sample.json" --exclude "Debug/*.log"

Use specific AWS profile:
    python copy_s3_folder.py s3://source-bucket/data/ s3://dest-bucket/backup/ \\
        --profile my-profile
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path to import poseinterface
sys.path.insert(0, str(Path(__file__).parent.parent))

from poseinterface.s3 import (
    copy_s3_folder,
    create_filename_exclude_filter,
    parse_s3_uri,
)


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
        description="Copy S3 folders with file filtering and rollback support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "source",
        help="Source S3 URI (e.g., s3://bucket/prefix/)",
    )

    parser.add_argument(
        "destination",
        help="Destination S3 URI (e.g., s3://bucket/prefix/)",
    )

    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help=(
            "Path or filename pattern to exclude (can be specified multiple times). "
            "Supports glob patterns (*.log, Test/*, */sample.json) and regex (regex:^test.*)"
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
        "--dry-run",
        action="store_true",
        help="Show what would be copied without actually copying",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point for the script."""
    args = parse_args()
    setup_logging(args.verbose)

    # Parse S3 URIs
    try:
        source_bucket, source_prefix = parse_s3_uri(args.source)
        dest_bucket, dest_prefix = parse_s3_uri(args.destination)
    except ValueError as e:
        logging.error(f"Invalid S3 URI: {e}")
        return 1

    # Log operation details
    logging.info("=" * 60)
    logging.info("S3 Folder Copy Operation")
    logging.info("=" * 60)
    logging.info(f"Source:      s3://{source_bucket}/{source_prefix}")
    logging.info(f"Destination: s3://{dest_bucket}/{dest_prefix}")

    if args.exclude:
        logging.info(f"Exclusions:  {', '.join(args.exclude)}")

    if args.profile:
        logging.info(f"AWS Profile: {args.profile}")

    if args.dry_run:
        logging.info("Mode:        DRY RUN (no actual copying)")

    logging.info("=" * 60)

    # Create exclude filter if patterns provided
    exclude_filter = None
    if args.exclude:
        exclude_filter = create_filename_exclude_filter(args.exclude)

    # Perform the copy
    try:
        if args.dry_run:
            logging.info("Dry run mode - would perform copy operation here")
            logging.info("No files were actually copied")
            return 0

        copied_keys, success = copy_s3_folder(
            source_bucket=source_bucket,
            source_prefix=source_prefix,
            dest_bucket=dest_bucket,
            dest_prefix=dest_prefix,
            exclude_filter=exclude_filter,
            aws_profile=args.profile,
        )

        if success:
            logging.info("=" * 60)
            logging.info("✓ Copy completed successfully!")
            logging.info(f"  Total files copied: {len(copied_keys)}")
            logging.info("=" * 60)
            return 0
        else:
            logging.error("Copy failed - changes were rolled back")
            return 1

    except KeyboardInterrupt:
        logging.warning("\nOperation interrupted by user")
        logging.warning("Rollback should have been triggered automatically")
        return 130

    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
