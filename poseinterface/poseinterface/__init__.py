from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("poseinterface")
except PackageNotFoundError:
    # package is not installed
    pass
