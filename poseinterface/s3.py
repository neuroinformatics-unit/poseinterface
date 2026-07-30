"""S3 utilities for poseinterface.

Note
----
All functions in this module create a new boto3 Session and S3 client on
each invocation. For operations that call these functions repeatedly (e.g.,
copying many files), this may result in multiple client creations. This is
acceptable for most use cases but may be inefficient for high-frequency
operations.
"""

import json
import logging
import re
from typing import Callable

import boto3
from botocore.exceptions import ClientError


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Parse an S3 URI into bucket and key components.

    Parameters
    ----------
    s3_uri
        S3 URI in the format ``s3://bucket-name/path/to/file``.

    Returns
    -------
    tuple[str, str]
        Tuple of (bucket_name, key).

    Raises
    ------
    ValueError
        If the S3 URI format is invalid.
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError(
            f"Invalid S3 URI format. Expected 's3://bucket/key', got {s3_uri}"
        )

    uri_parts = s3_uri[5:].split("/", 1)
    if len(uri_parts) != 2:
        raise ValueError(
            f"Invalid S3 URI format. Expected 's3://bucket/key', got {s3_uri}"
        )

    return uri_parts[0], uri_parts[1]


def download_json_from_s3(
    bucket_name: str, key: str, aws_profile: str | None = None
) -> dict:
    """Download and parse a JSON file from S3.

    Parameters
    ----------
    bucket_name
        Name of the S3 bucket.
    key
        S3 object key (path within the bucket).
    aws_profile
        Optional AWS profile name to use for authentication.

    Returns
    -------
    dict
        Parsed JSON content.

    Raises
    ------
    FileNotFoundError
        If the file does not exist on S3.
    ClientError
        If there are other S3 access issues.
    """
    session = boto3.Session(profile_name=aws_profile)
    s3_client = session.client("s3")

    try:
        logging.info(f"Downloading s3://{bucket_name}/{key}")
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "NoSuchKey":
            raise FileNotFoundError(
                f"File not found on S3: s3://{bucket_name}/{key}"
            ) from e
        logging.error(
            "Failed to download from s3://%s/%s (S3 error: %s)",
            bucket_name,
            key,
            error_code,
        )
        raise


def upload_json_to_s3(
    data: dict,
    bucket_name: str,
    key: str,
    aws_profile: str | None = None,
) -> None:
    """Upload a JSON object to S3.

    Parameters
    ----------
    data
        Dictionary to serialize and upload.
    bucket_name
        Name of the S3 bucket.
    key
        S3 object key (path within the bucket).
    aws_profile
        Optional AWS profile name to use for authentication.

    Raises
    ------
    ClientError
        If there are S3 access issues.
    """
    session = boto3.Session(profile_name=aws_profile)
    s3_client = session.client("s3")

    logging.info(f"Uploading to s3://{bucket_name}/{key}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=json.dumps(data),
        ContentType="application/json",
    )


def list_s3_objects(
    bucket_name: str,
    prefix: str = "",
    aws_profile: str | None = None,
) -> list[dict]:
    """List all objects in an S3 bucket with a given prefix.

    Parameters
    ----------
    bucket_name
        Name of the S3 bucket.
    prefix
        S3 prefix (folder path) to list objects from.
    aws_profile
        Optional AWS profile name to use for authentication.

    Returns
    -------
    list[dict]
        List of objects with 'Key' and 'Size' fields.

    Raises
    ------
    ClientError
        If there are S3 access issues.
    """
    session = boto3.Session(profile_name=aws_profile)
    s3_client = session.client("s3")

    objects = []
    paginator = s3_client.get_paginator("list_objects_v2")

    try:
        for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
            if "Contents" in page:
                objects.extend(page["Contents"])
    except ClientError as e:
        logging.error(
            "Failed to list objects in s3://%s/%s: %s",
            bucket_name,
            prefix,
            e,
        )
        raise

    return objects


def copy_s3_object(
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
    aws_profile: str | None = None,
) -> None:
    """Copy a single object from one S3 location to another.

    Note
    ----
    This function uses the S3 copy_object API which has a 5GB file size
    limit. For objects larger than 5GB, use multipart copy instead.

    Parameters
    ----------
    source_bucket
        Source S3 bucket name.
    source_key
        Source S3 object key.
    dest_bucket
        Destination S3 bucket name.
    dest_key
        Destination S3 object key.
    aws_profile
        Optional AWS profile name to use for authentication.

    Raises
    ------
    ClientError
        If there are S3 access issues.
    """
    session = boto3.Session(profile_name=aws_profile)
    s3_client = session.client("s3")

    copy_source = {"Bucket": source_bucket, "Key": source_key}

    try:
        logging.info(
            f"Copying s3://{source_bucket}/{source_key} to "
            f"s3://{dest_bucket}/{dest_key}"
        )
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=dest_bucket,
            Key=dest_key,
        )
    except ClientError as e:
        logging.error(
            "Failed to copy s3://%s/%s to s3://%s/%s: %s",
            source_bucket,
            source_key,
            dest_bucket,
            dest_key,
            e,
        )
        raise


def delete_s3_objects(
    bucket_name: str,
    keys: list[str],
    aws_profile: str | None = None,
) -> None:
    """Delete multiple objects from S3.

    Parameters
    ----------
    bucket_name
        Name of the S3 bucket.
    keys
        List of S3 object keys to delete.
    aws_profile
        Optional AWS profile name to use for authentication.

    Raises
    ------
    ClientError
        If there are S3 access issues.
    RuntimeError
        If some objects fail to delete (partial failure).
    """
    if not keys:
        return

    session = boto3.Session(profile_name=aws_profile)
    s3_client = session.client("s3")

    # Delete in batches of 1000 (S3 limit)
    batch_size = 1000
    for i in range(0, len(keys), batch_size):
        batch = keys[i:i + batch_size]
        objects_to_delete = [{"Key": key} for key in batch]

        try:
            logging.info(f"Deleting {len(batch)} objects from s3://{bucket_name}")
            response = s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={"Objects": objects_to_delete},
            )

            # Check for partial failures
            if "Errors" in response and response["Errors"]:
                failed_keys = [error["Key"] for error in response["Errors"]]
                error_messages = [
                    f"{error['Key']}: {error['Code']} - {error['Message']}"
                    for error in response["Errors"]
                ]
                logging.error(
                    "Failed to delete %d/%d objects from s3://%s: %s",
                    len(failed_keys),
                    len(batch),
                    bucket_name,
                    "; ".join(error_messages),
                )
                raise RuntimeError(
                    f"Failed to delete {len(failed_keys)} objects: {failed_keys}"
                )
        except ClientError as e:
            logging.error(
                "Failed to delete objects from s3://%s: %s",
                bucket_name,
                e,
            )
            raise


def copy_s3_folder(
    source_bucket: str,
    source_prefix: str,
    dest_bucket: str,
    dest_prefix: str,
    exclude_filter: Callable[[str], bool] | None = None,
    aws_profile: str | None = None,
) -> tuple[list[str], bool]:
    """Copy a folder from one S3 location to another with optional filtering.

    This function tracks all copied files and supports rollback if the copy fails.

    Parameters
    ----------
    source_bucket
        Source S3 bucket name.
    source_prefix
        Source S3 prefix (folder path).
    dest_bucket
        Destination S3 bucket name.
    dest_prefix
        Destination S3 prefix (folder path).
    exclude_filter
        Optional callable that takes a relative path (from source_prefix) and
        returns True if the file should be excluded from the copy.
    aws_profile
        Optional AWS profile name to use for authentication.

    Returns
    -------
    tuple[list[str], bool]
        Tuple of (copied_keys, success). copied_keys contains all destination keys
        that were successfully copied. success is always True when the function
        returns normally (failures raise exceptions).

    Raises
    ------
    ClientError
        If there are S3 access issues during listing.
    """
    # Ensure prefixes end with / if they're not empty
    if source_prefix and not source_prefix.endswith("/"):
        source_prefix += "/"
    if dest_prefix and not dest_prefix.endswith("/"):
        dest_prefix += "/"

    # List all objects in source
    logging.info(f"Listing objects in s3://{source_bucket}/{source_prefix}")
    source_objects = list_s3_objects(source_bucket, source_prefix, aws_profile)

    # Filter objects
    objects_to_copy = []
    for obj in source_objects:
        source_key = obj["Key"]
        # Skip if it's just the prefix itself (folder marker)
        if source_key == source_prefix:
            continue

        # Get the relative path for filtering
        relative_path = source_key[len(source_prefix):]

        # Apply filter if provided
        if exclude_filter and exclude_filter(relative_path):
            logging.info(f"Skipping {relative_path} (filtered)")
            continue

        objects_to_copy.append(source_key)

    logging.info(
        f"Found {len(objects_to_copy)} objects to copy "
        f"(filtered from {len(source_objects)})"
    )

    # Track copied keys for potential rollback
    copied_keys = []
    success = True

    try:
        for source_key in objects_to_copy:
            # Compute destination key by replacing prefix
            relative_path = source_key[len(source_prefix):]
            dest_key = dest_prefix + relative_path

            copy_s3_object(
                source_bucket,
                source_key,
                dest_bucket,
                dest_key,
                aws_profile,
            )
            copied_keys.append(dest_key)

        logging.info(f"Successfully copied {len(copied_keys)} objects")

    except Exception as e:
        logging.error(f"Copy failed: {e}")
        success = False

        # Rollback: delete all partially copied objects
        if copied_keys:
            logging.warning(
                f"Rolling back: deleting {len(copied_keys)} partially copied objects"
            )
            try:
                delete_s3_objects(dest_bucket, copied_keys, aws_profile)
                logging.info("Rollback completed successfully")
            except Exception as rollback_error:
                logging.error(f"Rollback failed: {rollback_error}")
                logging.error(
                    f"Manual cleanup required for keys: {copied_keys}"
                )

        raise

    return copied_keys, success


def create_filename_exclude_filter(patterns: list[str]) -> Callable[[str], bool]:
    """Create a filter function that excludes files matching given patterns.

    Supports both exact matches and regex patterns. Works with both filenames
    and relative paths (including subdirectories).

    Parameters
    ----------
    patterns
        List of patterns to exclude. Can be:
        - Exact paths/filenames (e.g., "temp.txt", "Test/sample.json")
        - Glob-style patterns (e.g., "*.log", "temp_*", "Test/*", "*/sample.json")
        - Regex patterns (must start with "regex:")

    Returns
    -------
    Callable[[str], bool]
        Function that takes a relative path and returns True if it should be excluded.

    Examples
    --------
    >>> filter_fn = create_filename_exclude_filter(["*.log", "temp_*", "Test/*"])
    >>> filter_fn("test.log")  # True - excluded
    >>> filter_fn("temp_data.json")  # True - excluded
    >>> filter_fn("Test/sample.json")  # True - excluded (in Test directory)
    >>> filter_fn("Train/sample.json")  # False - not excluded
    >>> filter_fn("data.json")  # False - not excluded
    """

    def matches_pattern(path: str, pattern: str) -> bool:
        """Check if path matches a single pattern."""
        # Regex pattern
        if pattern.startswith("regex:"):
            regex_pattern = pattern[6:]
            return bool(re.match(regex_pattern, path))

        # Glob-style pattern - convert to regex
        # Escape special regex chars except * and ?
        regex = re.escape(pattern)
        regex = regex.replace(r"\*", ".*")
        regex = regex.replace(r"\?", ".")
        regex = f"^{regex}$"

        return bool(re.match(regex, path))

    def exclude_filter(path: str) -> bool:
        """Return True if path should be excluded."""
        return any(matches_pattern(path, pattern) for pattern in patterns)

    return exclude_filter
