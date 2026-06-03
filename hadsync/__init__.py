from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("hadsync")
except PackageNotFoundError:
    __version__ = "unknown"
