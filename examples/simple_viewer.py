"""
Simple coupling setup using live view modules.
"""
from datetime import datetime, timedelta

import numpy as np
from finam.adapters import base, time
from finam.core.schedule import Composition
from finam.modules.visual import time_series
from matplotlib import pyplot as plt

from finam_mhm_module import Mhm


def grid_select(grid):
    col, row = 3, 5
    return grid[col * 9 + row]


plot = time_series.TimeSeriesView(
    start=datetime(1990, 1, 1),
    step=timedelta(days=1),
    inputs=["Runoff"],
    intervals=[1],
)

mhm = Mhm(cwd="../../MHM/mhm")

composition = Composition([mhm, plot])
composition.initialize()

grid_value = mhm.outputs["L1_TOTAL_RUNOFF"] >> base.GridToValue(func=grid_select)
grid_value >> time.LinearInterpolation() >> plot.inputs["Runoff"]

composition.run(datetime(1992, 1, 1))
plt.show()
