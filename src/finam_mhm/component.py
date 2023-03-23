"""
FINAM mHM module.
"""
from datetime import datetime, timedelta

import numpy as np
import finam as fm
import mhm

OUTPUT_META = {
    "L0_GRIDDED_LAI": dict(unit="1", long_name="leaf area index"),
    "L1_FSEALED": dict(unit="1", long_name="Fraction of sealed area"),
    "L1_FNOTSEALED": dict(unit="1", long_name="Fraction of unsealed area"),
    "L1_INTER": dict(unit="mm / h", long_name="Interception"),
    "L1_SNOWPACK": dict(unit="mm / h", long_name="Snowpack"),
    "L1_SEALSTW": dict(
        unit="mm / h", long_name="Retention storage of impervious areas"
    ),
    "L1_UNSATSTW": dict(unit="mm / h", long_name="upper soil storage"),
    "L1_SATSTW": dict(unit="mm / h", long_name="groundwater storage"),
    "L1_NEUTRONS": dict(unit="mm / h", long_name="Ground Albedo Neutrons"),
    "L1_PET_CALC": dict(unit="mm / h", long_name="potential evapotranspiration"),
    "L1_AETCANOPY": dict(
        unit="mm / h", long_name="Real evaporation intensity from canopy"
    ),
    "L1_AETSEALED": dict(
        unit="mm / h", long_name="Real evap. from free water surfaces"
    ),
    "L1_TOTAL_RUNOFF": dict(unit="m^3 / h", long_name="Generated runoff"),
    "L1_RUNOFFSEAL": dict(
        unit="mm / h", long_name="Direct runoff from impervious areas"
    ),
    "L1_FASTRUNOFF": dict(unit="mm / h", long_name="Fast runoff component"),
    "L1_SLOWRUNOFF": dict(unit="mm / h", long_name="Slow runoff component"),
    "L1_BASEFLOW": dict(unit="mm / h", long_name="Baseflow"),
    "L1_PERCOL": dict(unit="mm / h", long_name="Percolation"),
    "L1_PREEFFECT": dict(unit="mm / h", long_name="Effective precip. depth"),
    "L1_SOILMOIST_VOL_ALL": dict(
        unit="1", long_name="average soil moisture over all layers"
    ),
    "L11_QMOD": dict(unit="m^3 / s", long_name="Simulated discharge"),
    "L11_QOUT": dict(unit="m^3 / s", long_name="Total outflow from cells"),
}
"""dict: meta information about available outputs in mHM."""

INPUT_META = {
    "L0_GRIDDED_LAI": dict(unit="1", long_name="leaf area index"),
}
"""dict: meta information about available inputs in mHM."""


class MHM(fm.TimeComponent):
    def __init__(
        self,
        namelist_mhm="mhm.nml",
        namelist_mhm_param="mhm_parameter.nml",
        namelist_mhm_output="mhm_outputs.nml",
        namelist_mrm_output="mrm_outputs.nml",
        cwd=".",
        input_names=None,
    ):
        super().__init__()
        self.OUTPUT_NAMES = list(OUTPUT_META)
        self.INPUT_NAMES = (
            [] if input_names is None else [n.upper() for n in input_names]
        )
        for in_name in self.INPUT_NAMES:
            if in_name not in INPUT_META:
                raise ValueError(f"mHM: input '{in_name}' is not available.")
        self.namelist_mhm = namelist_mhm
        self.namelist_mhm_param = namelist_mhm_param
        self.namelist_mhm_output = namelist_mhm_output
        self.namelist_mrm_output = namelist_mrm_output
        self.cwd = cwd  # needed for @fm.tools.execute_in_cwd
        # mHM always has hourly stepping
        self.step = timedelta(hours=1)

    @property
    def next_time(self):
        """Next pull time."""
        return self.time + self.step

    def _get(self, var):
        value = mhm.get_variable(var)
        value.fill_value = np.nan
        return value.filled()

    @fm.tools.execute_in_cwd
    def _initialize(self):
        # only show errors
        mhm.model.set_verbosity(level=1)
        # init
        mhm.model.init(
            namelist_mhm=self.namelist_mhm,
            namelist_mhm_param=self.namelist_mhm_param,
            namelist_mhm_output=self.namelist_mhm_output,
            namelist_mrm_output=self.namelist_mrm_output,
            cwd=".",
        )
        # disable file output of mHM
        mhm.model.disable_output()
        mhm.run.prepare()
        # only one domain possible
        mhm.run.prepare_domain()
        # set time
        year, month, day, hour = mhm.run.current_time()
        self.time = datetime(year=year, month=month, day=max(day, 0), hour=max(hour, 0))
        # first time step compensate by negative values in mHM
        if day < 0 or hour < 0:
            self.time += timedelta(days=min(day, 0), hours=min(hour, 0))

        # store Grid specifications
        self.gridspec = {}
        # get grid info l0 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mhm.get.l0_domain_info()
        self.no_data = no_data
        self.gridspec["L0"] = fm.EsriGrid(
            ncols=ncols, nrows=nrows, cellsize=cell_size, xllcorner=xll, yllcorner=yll
        )
        # get grid info l1 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mhm.get.l1_domain_info()
        self.gridspec["L1"] = fm.EsriGrid(
            ncols=ncols, nrows=nrows, cellsize=cell_size, xllcorner=xll, yllcorner=yll
        )
        # get grid info l11 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mhm.get.l11_domain_info()
        self.gridspec["L11"] = fm.EsriGrid(
            ncols=ncols, nrows=nrows, cellsize=cell_size, xllcorner=xll, yllcorner=yll
        )
        print(self.gridspec["L11"].nrows)
        print(self.gridspec["L11"].ncols)
        print(self.gridspec["L11"].axes_names)
        # get grid info l2 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mhm.get.l2_domain_info()
        self.gridspec["L2"] = fm.EsriGrid(
            ncols=ncols, nrows=nrows, cellsize=cell_size, xllcorner=xll, yllcorner=yll
        )
        for var in self.OUTPUT_NAMES:
            grid_name = var.split("_")[0]
            self.outputs.add(name=var, time=self.time, grid=self.gridspec[grid_name], **OUTPUT_META[var])
        for var in self.INPUT_NAMES:
            grid_name = var.split("_")[0]
            self.inputs.add(name=var, time=self.time, grid=self.gridspec[grid_name], **INPUT_META[var])
        self.create_connector()

    def _connect(self, start_time):
        push_data = {var: self._get(var) for var in self.OUTPUT_NAMES}
        self.try_connect(start_time=start_time, push_data=push_data)

    @fm.tools.execute_in_cwd
    def _update(self):
        # Don't run further than mHM can
        if mhm.run.finished():
            return
        mhm.run.do_time_step()
        # update time
        year, month, day, hour = mhm.run.current_time()
        self.time = datetime(year=year, month=month, day=day, hour=hour)
        # push outputs
        for var in self.OUTPUT_NAMES:
            if not self.outputs[var].has_targets:
                continue
            self.outputs[var].push_data(
                data=self._get(var),
                time=self.time,
            )

    @fm.tools.execute_in_cwd
    def _finalize(self):
        with fm.tools.LogCStdOutStdErr(self.logger):
            mhm.run.finalize_domain()
            mhm.run.finalize()
            mhm.model.finalize()
