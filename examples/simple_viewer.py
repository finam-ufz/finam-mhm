"""
Simple coupling setup using live view modules.
"""
from datetime import datetime, timedelta

import finam as fm
import finam_mhm as fm_mhm
import finam_plot as fm_plt
import finam_netcdf as fm_nc

start_date = datetime(1990, 1, 1)
day = timedelta(days=1)

mhm = fm_mhm.MHM(cwd="../../MHM/mhm/test_domain")
runoff_viewer = fm_plt.ImagePlot(vmin=0.0, vmax=650)

# netcdf writing files
writer = fm_nc.NetCdfTimedWriter(
    path="qmod.nc",
    inputs={"QMOD": fm_nc.Layer(var="QMOD", xyz=("x", "y"))},
    time_var="time",
    start=start_date,
    step=day,
)

composition = fm.Composition([mhm, writer, runoff_viewer])
composition.initialize()

mhm.outputs["L11_QMOD"] >> writer.inputs["QMOD"]
mhm.outputs["L11_QMOD"] >> runoff_viewer.inputs["Grid"]

composition.run(end_time=datetime(1992, 1, 1))
