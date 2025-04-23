"""
mHM FINAM component.

.. toctree::
   :hidden:

   self

Component
=========

.. autosummary::
   :toctree: api

    MHM

Subpackages
===========

.. autosummary::
   :toctree: api

   constants

IO-Infos
========

.. currentmodule:: finam_mhm.constants

.. autosummary::

    OUTPUT_META
    OUTPUT_HORIZONS_META
    OUTPUT_CALC_META
    OUTPUT_CALC_HORIZONS_META
    MRM_OUTPUT_META
    INPUT_UNITS

"""

from . import constants
from .component import MHM
from .constants import (
    INPUT_UNITS,
    MRM_OUTPUT_META,
    OUTPUT_CALC_HORIZONS_META,
    OUTPUT_CALC_META,
    OUTPUT_HORIZONS_META,
    OUTPUT_META,
)

try:
    from ._version import __version__
except ModuleNotFoundError:  # pragma: no cover
    # package is not installed
    __version__ = "0.0.0.dev0"

__all__ = ["constants"]
__all__ += ["MHM"]
__all__ += [
    "INPUT_UNITS",
    "MRM_OUTPUT_META",
    "OUTPUT_CALC_HORIZONS_META",
    "OUTPUT_CALC_META",
    "OUTPUT_HORIZONS_META",
    "OUTPUT_META",
]
