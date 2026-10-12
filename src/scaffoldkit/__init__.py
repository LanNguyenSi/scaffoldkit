"""ScaffoldKit - AI-aided project scaffolding tool."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("scaffoldkit")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
