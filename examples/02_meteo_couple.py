"""
Meteo coupling setup.
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
download_test(path=test_domain, domain=1)

start_date = datetime(1990, 1, 1)
end_date = datetime(1991, 1, 1)

pre_reader = fm_nc.NetCdfReader(test_domain / "input" / "meteo" / "pre" / "pre.nc")

mhm = fm_mhm.MHM(
    cwd=test_domain,
    input_names=["METEO_PRE"],
    meteo_timestep=24,
    ignore_input_grid=True,
)
# netcdf writing files
writer = fm_nc.NetCdfTimedWriter(
    path=here / "qmod_couple.nc",
    inputs={"QMOD": fm_nc.Layer(var="QMOD", xyz=("x", "y"))},
    time_var="time",
    step=timedelta(days=1),
)

composition = fm.Composition([pre_reader, mhm, writer])
composition.initialize()

pre_reader["pre"] >> mhm.inputs["METEO_PRE"]
mhm.outputs["L11_QMOD"] >> writer.inputs["QMOD"]

composition.run(start_time=start_date, end_time=end_date)
