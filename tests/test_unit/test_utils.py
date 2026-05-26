import pytest

from poseinterface.utils import tree


class TestTree:
    """Tests for the tree function that generates
    a string representation of a directory structure."""

    def test_empty_directory(self, tmp_path):
        """Test tree of an empty directory."""
        result = tree(tmp_path)
        assert result.startswith(tmp_path.name + "/")
        assert "0 directories" in result

    def test_files_and_directories(self, tmp_path):
        """Test tree with a mix of files and directories."""
        (tmp_path / "a_dir").mkdir()
        (tmp_path / "b_file.txt").touch()

        result = tree(tmp_path)
        assert "a_dir/" in result
        assert "b_file.txt" in result
        assert "b_file.txt/" not in result
        assert "1 directories" in result
        assert "1 files" in result


    def test_level_limits_depth(self, tmp_path):
        """Test that level limits the depth of the tree."""
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)

        result_shallow = tree(tmp_path, level=1)
        result_deep = tree(tmp_path, level=3)

        # level=1 shows "a/" but not "b/"
        assert "a/" in result_shallow
        assert "b/" not in result_shallow
        # level=3 shows all
        assert "c/" in result_deep

    @pytest.mark.parametrize(
        "tree_kwargs, expected_present, expected_absent",
        [
            (
                {"limit_to_directories": True},
                ["subdir/", ".hidden_dir/"],
                ["visible.txt", ".hidden_file"],
            ),
            (
                {"exclude_hidden": True},
                ["subdir/", "visible.txt"],
                [".hidden_dir", ".hidden_file"],
            ),
        ],
    )
    def test_filtering_options(
        self, tmp_path, tree_kwargs, expected_present, expected_absent
    ):
        """Test that filtering options include/exclude entries."""
        (tmp_path / "subdir").mkdir()
        (tmp_path / "visible.txt").touch()
        (tmp_path / ".hidden_dir").mkdir()
        (tmp_path / ".hidden_file").touch()

        result = tree(tmp_path, **tree_kwargs)
        for name in expected_present:
            assert name in result
        for name in expected_absent:
            assert name not in result

    def test_length_limit(self, tmp_path):
        """Test that output is truncated at length_limit."""
        for i in range(20):
            (tmp_path / f"file_{i:02d}.txt").touch()

        result = tree(tmp_path, length_limit=5)
        assert "length_limit" in result
        assert "5" in result

    def test_sorted_output(self, tmp_path):
        """Test that entries are sorted alphabetically."""
        (tmp_path / "cherry.txt").touch()
        (tmp_path / "apple.txt").touch()
        (tmp_path / "banana.txt").touch()

        result = tree(tmp_path)
        lines = result.split("\n")
        content_lines = [
            line
            for line in lines
            if any(f in line for f in ["apple", "banana", "cherry"])
        ]
        names = [line.split("── ")[-1] for line in content_lines]
        assert names == ["apple.txt", "banana.txt", "cherry.txt"]
