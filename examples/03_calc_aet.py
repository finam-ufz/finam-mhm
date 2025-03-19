"""
Simple coupling setup using live view modules.
"""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

import finam as fm
import finam_netcdf as fm_nc
from mhm import download_test

import finam_mhm as fm_mhm

here = Path(__file__).parent
test_domain = here / "test_domain"
shutil.rmtree(test_domain, ignore_errors=True)
download_test(path=test_domain)

mhm = fm_mhm.MHM(cwd=test_domain)
writer = fm_nc.NetCdfTimedWriter(
    path=here / "aet.nc",
    inputs=["AET_L01", "AET_L02", "AET"],
    step=timedelta(days=1),
)

composition = fm.Composition([mhm, writer])

mhm.outputs["L1_AET_L01"] >> fm.adapters.AvgOverTime() >> writer.inputs["AET_L01"]
mhm.outputs["L1_AET_L02"] >> fm.adapters.AvgOverTime() >> writer.inputs["AET_L02"]
mhm.outputs["L1_AET"] >> fm.adapters.AvgOverTime() >> writer.inputs["AET"]

composition.run(end_time=datetime(1994, 1, 1))
