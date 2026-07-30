from unittest.mock import MagicMock, patch

import pytest

from poseinterface.s3 import (
    copy_s3_folder,
    copy_s3_object,
    create_filename_exclude_filter,
    delete_s3_objects,
    list_s3_objects,
    parse_s3_uri,
)


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


# ---------------------------------------------------------------------------
# list_s3_objects
# ---------------------------------------------------------------------------


def test_list_s3_objects():
    """Test listing S3 objects returns all objects from paginated results."""
    mock_s3_client = MagicMock()
    mock_paginator = MagicMock()

    # Simulate paginated results
    mock_paginator.paginate.return_value = [
        {"Contents": [{"Key": "prefix/file1.txt", "Size": 100}]},
        {"Contents": [{"Key": "prefix/file2.txt", "Size": 200}]},
        {},  # Empty page
    ]

    mock_s3_client.get_paginator.return_value = mock_paginator

    with patch("poseinterface.s3.boto3.Session") as mock_session:
        mock_session.return_value.client.return_value = mock_s3_client

        result = list_s3_objects("test-bucket", "prefix/", "test-profile")

    assert len(result) == 2
    assert result[0]["Key"] == "prefix/file1.txt"
    assert result[0]["Size"] == 100
    assert result[1]["Key"] == "prefix/file2.txt"
    assert result[1]["Size"] == 200

    mock_session.assert_called_once_with(profile_name="test-profile")
    mock_s3_client.get_paginator.assert_called_once_with("list_objects_v2")
    mock_paginator.paginate.assert_called_once_with(
        Bucket="test-bucket", Prefix="prefix/"
    )


def test_list_s3_objects_empty():
    """Test listing S3 objects when no objects exist."""
    mock_s3_client = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [{}]  # No Contents key
    mock_s3_client.get_paginator.return_value = mock_paginator

    with patch("poseinterface.s3.boto3.Session") as mock_session:
        mock_session.return_value.client.return_value = mock_s3_client

        result = list_s3_objects("test-bucket", "prefix/")

    assert result == []


# ---------------------------------------------------------------------------
# copy_s3_object
# ---------------------------------------------------------------------------


def test_copy_s3_object():
    """Test copying a single S3 object."""
    mock_s3_client = MagicMock()

    with patch("poseinterface.s3.boto3.Session") as mock_session:
        mock_session.return_value.client.return_value = mock_s3_client

        copy_s3_object(
            "source-bucket",
            "source/key.txt",
            "dest-bucket",
            "dest/key.txt",
            "test-profile",
        )

    mock_session.assert_called_once_with(profile_name="test-profile")
    mock_s3_client.copy_object.assert_called_once_with(
        CopySource={"Bucket": "source-bucket", "Key": "source/key.txt"},
        Bucket="dest-bucket",
        Key="dest/key.txt",
    )


# ---------------------------------------------------------------------------
# delete_s3_objects
# ---------------------------------------------------------------------------


def test_delete_s3_objects():
    """Test deleting multiple S3 objects."""
    mock_s3_client = MagicMock()

    with patch("poseinterface.s3.boto3.Session") as mock_session:
        mock_session.return_value.client.return_value = mock_s3_client

        keys = ["file1.txt", "file2.txt", "file3.txt"]
        delete_s3_objects("test-bucket", keys, "test-profile")

    mock_session.assert_called_once_with(profile_name="test-profile")
    mock_s3_client.delete_objects.assert_called_once_with(
        Bucket="test-bucket",
        Delete={
            "Objects": [
                {"Key": "file1.txt"},
                {"Key": "file2.txt"},
                {"Key": "file3.txt"},
            ]
        },
    )


def test_delete_s3_objects_empty_list():
    """Test deleting with an empty list does nothing."""
    mock_s3_client = MagicMock()

    with patch("poseinterface.s3.boto3.Session") as mock_session:
        mock_session.return_value.client.return_value = mock_s3_client

        delete_s3_objects("test-bucket", [])

    mock_s3_client.delete_objects.assert_not_called()


def test_delete_s3_objects_batching():
    """Test deleting more than 1000 objects uses batching."""
    mock_s3_client = MagicMock()

    with patch("poseinterface.s3.boto3.Session") as mock_session:
        mock_session.return_value.client.return_value = mock_s3_client

        # Create 1500 keys to test batching
        keys = [f"file{i}.txt" for i in range(1500)]
        delete_s3_objects("test-bucket", keys)

    # Should be called twice: once for first 1000, once for remaining 500
    assert mock_s3_client.delete_objects.call_count == 2

    # Check first batch has 1000 items
    first_call_objects = mock_s3_client.delete_objects.call_args_list[0][1][
        "Delete"
    ]["Objects"]
    assert len(first_call_objects) == 1000

    # Check second batch has 500 items
    second_call_objects = mock_s3_client.delete_objects.call_args_list[1][1][
        "Delete"
    ]["Objects"]
    assert len(second_call_objects) == 500


def test_delete_s3_objects_partial_failure():
    """Test that partial deletion failures raise RuntimeError."""
    mock_s3_client = MagicMock()

    # Simulate partial failure response
    mock_s3_client.delete_objects.return_value = {
        "Deleted": [{"Key": "file1.txt"}],
        "Errors": [
            {
                "Key": "file2.txt",
                "Code": "AccessDenied",
                "Message": "Access Denied",
            },
            {
                "Key": "file3.txt",
                "Code": "NoSuchKey",
                "Message": "The specified key does not exist.",
            },
        ],
    }

    with patch("poseinterface.s3.boto3.Session") as mock_session:
        mock_session.return_value.client.return_value = mock_s3_client

        keys = ["file1.txt", "file2.txt", "file3.txt"]

        with pytest.raises(RuntimeError, match="Failed to delete 2 objects"):
            delete_s3_objects("test-bucket", keys)


# ---------------------------------------------------------------------------
# copy_s3_folder
# ---------------------------------------------------------------------------


def test_copy_s3_folder_success():
    """Test successful folder copy."""
    mock_objects = [
        {"Key": "source/file1.txt", "Size": 100},
        {"Key": "source/file2.txt", "Size": 200},
        {"Key": "source/subdir/file3.txt", "Size": 300},
    ]

    with (
        patch("poseinterface.s3.list_s3_objects", return_value=mock_objects),
        patch("poseinterface.s3.copy_s3_object") as mock_copy,
    ):
        copied_keys, success = copy_s3_folder(
            "source-bucket",
            "source",
            "dest-bucket",
            "dest",
            aws_profile="test-profile",
        )

    assert success is True
    assert len(copied_keys) == 3
    assert copied_keys == [
        "dest/file1.txt",
        "dest/file2.txt",
        "dest/subdir/file3.txt",
    ]

    # Verify all files were copied
    assert mock_copy.call_count == 3
    mock_copy.assert_any_call(
        "source-bucket",
        "source/file1.txt",
        "dest-bucket",
        "dest/file1.txt",
        "test-profile",
    )
    mock_copy.assert_any_call(
        "source-bucket",
        "source/file2.txt",
        "dest-bucket",
        "dest/file2.txt",
        "test-profile",
    )
    mock_copy.assert_any_call(
        "source-bucket",
        "source/subdir/file3.txt",
        "dest-bucket",
        "dest/subdir/file3.txt",
        "test-profile",
    )


def test_copy_s3_folder_with_filter():
    """Test folder copy with exclusion filter."""
    mock_objects = [
        {"Key": "source/file1.txt", "Size": 100},
        {"Key": "source/file2.log", "Size": 200},
        {"Key": "source/temp_data.txt", "Size": 300},
        {"Key": "source/data.txt", "Size": 400},
    ]

    # Filter out .log files and temp_* files
    exclude_filter = create_filename_exclude_filter(["*.log", "temp_*"])

    with (
        patch("poseinterface.s3.list_s3_objects", return_value=mock_objects),
        patch("poseinterface.s3.copy_s3_object") as mock_copy,
    ):
        copied_keys, success = copy_s3_folder(
            "source-bucket",
            "source",
            "dest-bucket",
            "dest",
            exclude_filter=exclude_filter,
        )

    assert success is True
    assert len(copied_keys) == 2
    assert copied_keys == ["dest/file1.txt", "dest/data.txt"]


def test_copy_s3_folder_with_path_filter():
    """Test folder copy with path-based exclusion filter."""
    mock_objects = [
        {"Key": "source/Train/sample.json", "Size": 100},
        {"Key": "source/Test/sample.json", "Size": 100},
        {"Key": "source/Train/data.json", "Size": 200},
        {"Key": "source/Test/data.json", "Size": 200},
    ]

    # Filter out Test directory
    exclude_filter = create_filename_exclude_filter(["Test/*"])

    with (
        patch("poseinterface.s3.list_s3_objects", return_value=mock_objects),
        patch("poseinterface.s3.copy_s3_object") as mock_copy,
    ):
        copied_keys, success = copy_s3_folder(
            "source-bucket",
            "source",
            "dest-bucket",
            "dest",
            exclude_filter=exclude_filter,
        )

    assert success is True
    assert len(copied_keys) == 2
    assert copied_keys == ["dest/Train/sample.json", "dest/Train/data.json"]


def test_copy_s3_folder_rollback_on_failure():
    """Test folder copy rolls back on failure."""
    mock_objects = [
        {"Key": "source/file1.txt", "Size": 100},
        {"Key": "source/file2.txt", "Size": 200},
        {"Key": "source/file3.txt", "Size": 300},
    ]

    # Make the second copy fail
    def copy_side_effect(src_bucket, src_key, dst_bucket, dst_key, profile):
        if src_key == "source/file2.txt":
            raise Exception("Copy failed")

    with (
        patch("poseinterface.s3.list_s3_objects", return_value=mock_objects),
        patch(
            "poseinterface.s3.copy_s3_object", side_effect=copy_side_effect
        ) as mock_copy,
        patch("poseinterface.s3.delete_s3_objects") as mock_delete,
        pytest.raises(Exception, match="Copy failed"),
    ):
        copy_s3_folder(
            "source-bucket",
            "source",
            "dest-bucket",
            "dest",
        )

    # Should have tried to copy 2 files before failing
    assert mock_copy.call_count == 2

    # Should have rolled back by deleting the first copied file
    mock_delete.assert_called_once_with(
        "dest-bucket", ["dest/file1.txt"], None
    )


def test_copy_s3_folder_adds_trailing_slashes():
    """Test that copy_s3_folder adds trailing slashes to prefixes."""
    mock_objects = [
        {"Key": "source/file.txt", "Size": 100},
    ]

    with (
        patch(
            "poseinterface.s3.list_s3_objects", return_value=mock_objects
        ) as mock_list,
        patch("poseinterface.s3.copy_s3_object"),
    ):
        copy_s3_folder(
            "source-bucket",
            "source",  # No trailing slash
            "dest-bucket",
            "dest",  # No trailing slash
        )

    # Should call list with trailing slash
    mock_list.assert_called_once_with("source-bucket", "source/", None)


def test_copy_s3_folder_skips_folder_markers():
    """Test that folder markers (keys ending with /) are skipped."""
    mock_objects = [
        {"Key": "source/", "Size": 0},  # Folder marker
        {"Key": "source/file.txt", "Size": 100},
    ]

    with (
        patch("poseinterface.s3.list_s3_objects", return_value=mock_objects),
        patch("poseinterface.s3.copy_s3_object") as mock_copy,
    ):
        copied_keys, success = copy_s3_folder(
            "source-bucket",
            "source",
            "dest-bucket",
            "dest",
        )

    # Should only copy the file, not the folder marker
    assert len(copied_keys) == 1
    assert mock_copy.call_count == 1


# ---------------------------------------------------------------------------
# create_filename_exclude_filter
# ---------------------------------------------------------------------------


def test_create_filename_exclude_filter_glob_patterns():
    """Test filter with glob patterns."""
    filter_fn = create_filename_exclude_filter(
        ["*.log", "temp_*", "debug.txt"]
    )

    # Should be excluded
    assert filter_fn("test.log") is True
    assert filter_fn("error.log") is True
    assert filter_fn("temp_data.json") is True
    assert filter_fn("temp_file.txt") is True
    assert filter_fn("debug.txt") is True

    # Should not be excluded
    assert filter_fn("data.json") is False
    assert filter_fn("logfile.txt") is False
    assert filter_fn("temporary.txt") is False


def test_create_filename_exclude_filter_path_patterns():
    """Test filter with path patterns."""
    filter_fn = create_filename_exclude_filter(
        ["Test/*", "Debug/*.log", "Train/sample.json"]
    )

    # Should be excluded
    assert filter_fn("Test/sample.json") is True
    assert filter_fn("Test/data.txt") is True
    assert filter_fn("Debug/error.log") is True
    assert filter_fn("Train/sample.json") is True

    # Should not be excluded
    assert filter_fn("Train/data.json") is False
    assert filter_fn("Production/sample.json") is False
    assert filter_fn("Debug/data.txt") is False


def test_create_filename_exclude_filter_wildcard_in_path():
    """Test filter with wildcards in the middle of paths."""
    filter_fn = create_filename_exclude_filter(["*/temp/*", "*/sample.json"])

    # Should be excluded
    assert filter_fn("data/temp/file.txt") is True
    assert filter_fn("src/temp/debug.log") is True
    assert filter_fn("Train/sample.json") is True
    assert filter_fn("Test/sample.json") is True

    # Should not be excluded
    assert filter_fn("data/file.txt") is False
    assert filter_fn("temp/file.txt") is False
    assert filter_fn("sample.json") is False


def test_create_filename_exclude_filter_regex():
    """Test filter with regex patterns."""
    filter_fn = create_filename_exclude_filter(
        [r"regex:^test_.*\.py$", "regex:\\d+"]
    )

    # Should be excluded
    assert filter_fn("test_file.py") is True
    assert filter_fn("test_something.py") is True
    assert filter_fn("123") is True
    assert filter_fn("456file") is True

    # Should not be excluded
    assert filter_fn("test_file.txt") is False
    assert filter_fn("file.py") is False
    assert filter_fn("abc") is False


def test_create_filename_exclude_filter_question_mark():
    """Test filter with ? wildcard."""
    filter_fn = create_filename_exclude_filter(["file?.txt", "test_??.log"])

    # Should be excluded
    assert filter_fn("file1.txt") is True
    assert filter_fn("fileA.txt") is True
    assert filter_fn("test_01.log") is True
    assert filter_fn("test_AB.log") is True

    # Should not be excluded
    assert filter_fn("file.txt") is False
    assert filter_fn("file12.txt") is False
    assert filter_fn("test_1.log") is False
    assert filter_fn("test_001.log") is False


def test_create_filename_exclude_filter_empty():
    """Test filter with no patterns excludes nothing."""
    filter_fn = create_filename_exclude_filter([])

    assert filter_fn("any_file.txt") is False
    assert filter_fn("test.log") is False
