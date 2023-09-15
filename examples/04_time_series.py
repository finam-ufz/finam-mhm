"""
CSV output of single cell runoff.
"""
import datetime as dt
import shutil
from pathlib import Path

import finam as fm
import finam_plot as fm_plt
from mhm import download_test

import finam_mhm as fm_mhm

here = Path(__file__).parent
test_domain = here / "test_domain"
shutil.rmtree(test_domain, ignore_errors=True)
download_test(path=test_domain)

mhm = fm_mhm.MHM(cwd=test_domain)
plot = fm_plt.TimeSeriesPlot(inputs=["Runoff"], update_interval=24)
csv = fm.modules.CsvWriter(
    path=here / "runoff.csv",
    inputs=["Runoff"],
    time_column="Time",
    separator=",",
    start=dt.datetime(1990, 1, 1),
    step=dt.timedelta(hours=1),
)

composition = fm.Composition([mhm, plot, csv])
composition.initialize()

value = mhm.outputs["L1_TOTAL_RUNOFF"] >> fm.adapters.GridToValue(
    func=lambda x: x[0, 8, 4]
)
value >> plot.inputs["Runoff"]
value >> fm.adapters.AvgOverTime() >> csv["Runoff"]

composition.run(end_time=dt.datetime(1991, 1, 1))
