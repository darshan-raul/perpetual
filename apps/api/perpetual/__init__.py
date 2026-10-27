"""Perpetual: AWS disaster-recovery readiness for whole stacks."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("perpetual")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.0.0"

__all__ = ["__version__"]
