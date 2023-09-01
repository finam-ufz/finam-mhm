"""
Simple coupling setup using live view modules.
"""
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import finam as fm
import finam_netcdf as fm_nc
import finam_plot as fm_plt
from mhm import download_test

import finam_mhm as fm_mhm

start_date = datetime(1990, 1, 1)
day = timedelta(days=1)
here = Path(__file__).parent
test_domain = here / "test_domain"
shutil.rmtree(test_domain, ignore_errors=True)

download_test(path=test_domain)
mhm = fm_mhm.MHM(cwd=test_domain)
runoff_viewer = fm_plt.ImagePlot(vmin=0.0, vmax=650, update_interval=24)
# netcdf writing files
writer = fm_nc.NetCdfTimedWriter(
    path=here / "qmod.nc",
    inputs={"QMOD": fm_nc.Layer(var="QMOD", xyz=("x", "y"))},
    time_var="time",
    start=start_date,
    step=day,
)

composition = fm.Composition([mhm, writer, runoff_viewer])
composition.initialize()

mhm.outputs["L11_QMOD"] >> writer.inputs["QMOD"]
mhm.outputs["L11_QMOD"] >> runoff_viewer.inputs["Grid"]

composition.run(end_time=datetime(1991, 1, 1))
