"""
Simple coupling setup using live view modules.
"""
from datetime import timedelta, datetime

import numpy as np

from finam.adapters import time, base
from finam.core.schedule import Composition
from finam.modules.visual import time_series
from finam_mhm_module import Mhm


def grid_select(grid):
    return grid.get(col=3, row=5)


plot = time_series.TimeSeriesView(
    start=datetime(1990, 1, 1),
    step=timedelta(days=1),
    inputs=["Linear (1)"],
    intervals=[1],
)

mhm = Mhm(cwd="../../MHM/mhm")

composition = Composition([mhm, plot])
composition.initialize()

grid_value = mhm.outputs["runoff"] >> base.GridToValue(func=grid_select)
grid_value >> time.LinearInterpolation() >> plot.inputs["Linear (1)"]

composition.run(datetime(1991, 1, 1))
