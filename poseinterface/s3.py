"""S3 utilities for poseinterface."""

import json
import logging

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
