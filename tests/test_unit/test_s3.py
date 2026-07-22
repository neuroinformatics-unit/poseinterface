import pytest

from poseinterface.s3 import parse_s3_uri


def test_parse_s3_uri():
    """Test a valid S3 URI is split into bucket and key."""
    bucket, key = parse_s3_uri("s3://my-bucket/path/to/file_cliplabels.json")
    assert bucket == "my-bucket"
    assert key == "path/to/file_cliplabels.json"


@pytest.mark.parametrize(
    "uri",
    [
        "my-bucket/path/to/file.json",  # missing s3:// scheme
        "s3://my-bucket",  # missing key
    ],
)
def test_parse_s3_uri_invalid(uri):
    """Test malformed S3 URIs raise ValueError."""
    with pytest.raises(ValueError, match="Invalid S3 URI format"):
        parse_s3_uri(uri)
