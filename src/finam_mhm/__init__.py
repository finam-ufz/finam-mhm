"""
mHM FINAM component.

.. toctree::
   :hidden:

   self

Component
=========

.. autosummary::
   :toctree: generated

    MHM
"""
from .component import MHM

try:
    from ._version import __version__
except ModuleNotFoundError:  # pragma: no cover
    # package is not installed
    __version__ = "0.0.0.dev0"

__all__ = ["MHM"]
