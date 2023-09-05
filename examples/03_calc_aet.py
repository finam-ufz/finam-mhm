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
# netcdf writing files
writer = fm_nc.NetCdfTimedWriter(
    path=here / "aet.nc",
    inputs={
        "AET_L01": fm_nc.Layer(var="AET_L01", xyz=("x", "y")),
        "AET_L02": fm_nc.Layer(var="AET_L02", xyz=("x", "y")),
        "AET": fm_nc.Layer(var="AET", xyz=("x", "y")),
    },
    time_var="time",
    step=day,
)

composition = fm.Composition([mhm, writer])
composition.initialize()

mhm.outputs["L1_AET_L01"] >> fm.adapters.AvgOverTime() >> writer.inputs["AET_L01"]
mhm.outputs["L1_AET_L02"] >> fm.adapters.AvgOverTime() >> writer.inputs["AET_L02"]
mhm.outputs["L1_AET"] >> fm.adapters.AvgOverTime() >> writer.inputs["AET"]

composition.run(end_time=datetime(1994, 1, 1))
