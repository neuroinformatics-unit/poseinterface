import subprocess


def test_smoke():
    """Smoke test to check entry point."""
    result = subprocess.run(["extract-clips", "--help"])
    assert result.returncode == 0
