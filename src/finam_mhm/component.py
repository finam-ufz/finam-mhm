"""
FINAM mHM module.
"""
from datetime import datetime, timedelta

import finam as fm
import mhm
import numpy as np

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
    "METEO_PRE": dict(unit="mm", long_name="precipitation"),
    "METEO_TEMP": dict(unit="degC", long_name="mean air temperature"),
    "METEO_PET": dict(unit="mm", long_name="potential evapotranspiration"),
    "METEO_TMIN": dict(unit="degC", long_name="minimum daily temperature"),
    "METEO_TMAX": dict(unit="degC", long_name="maximum daily temperature"),
    "METEO_NETRAD": dict(unit="W m-2", long_name="net radiation"),
    "METEO_ABSVAPPRESS": dict(unit="Pa", long_name="vapour pressure"),
    "METEO_WINDSPEED": dict(unit="m s-1", long_name="mean wind speed"),
    "METEO_SSRD": dict(unit="W m-2", long_name="solar short wave radiation downward"),
    "METEO_STRD": dict(unit="W m-2", long_name="surface thermal radiation downward"),
    "METEO_TANN": dict(unit="degC", long_name="annual mean air temperature"),
}
"""dict: meta information about available inputs in mHM."""


def _get_grid_name(var):
    grid_name = var.split("_")[0]
    return "L1" if grid_name == "METEO" else grid_name


def _get_var_name(var):
    return "_".join(var.split("_")[1:])


def _get_meteo_inputs(inputs):
    {_get_var_name(var).lower(): var for var in inputs if var.startswith("METEO")}


class MHM(fm.TimeComponent):
    def __init__(
        self,
        namelist_mhm="mhm.nml",
        namelist_mhm_param="mhm_parameter.nml",
        namelist_mhm_output="mhm_outputs.nml",
        namelist_mrm_output="mrm_outputs.nml",
        cwd=".",
        input_names=None,
        meteo_time_step=None,
    ):
        super().__init__()
        self.OUTPUT_NAMES = list(OUTPUT_META)
        self.INPUT_NAMES = (
            [] if input_names is None else [n.upper() for n in input_names]
        )
        for in_name in self.INPUT_NAMES:
            if in_name not in INPUT_META:
                msg = f"mHM: input '{in_name}' is not available."
                raise ValueError(msg)
        self.namelist_mhm = namelist_mhm
        self.namelist_mhm_param = namelist_mhm_param
        self.namelist_mhm_output = namelist_mhm_output
        self.namelist_mrm_output = namelist_mrm_output
        self.cwd = cwd  # needed for @fm.tools.execute_in_cwd
        # mHM always has hourly stepping
        self.step = timedelta(hours=1)
        self.meteo_timestep = meteo_time_step
        self.meteo_inputs = _get_meteo_inputs(self.INPUT_NAMES)

        if self.meteo_inputs and self.meteo_timestep not in [1, 24]:
            msg = (
                "mHM: found meteo inputs but meteo time-step not valid, "
                f"got {self.meteo_timestep}"
            )
            raise ValueError(msg)

    @property
    def next_time(self):
        """Next pull time."""
        return self.time + self.step

    @fm.tools.execute_in_cwd
    def _initialize(self):
        # only show errors
        mhm.model.set_verbosity(level=1)
        # configure coupling
        if self.meteo_inputs:
            kwargs = {f"meteo_expect_{var}": True for var in self.meteo_inputs}
            kwargs["couple_case"] = 1
            kwargs["meteo_timestep"] = self.meteo_timestep
            mhm.model.config_coupling(**kwargs)
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
        # get grid info l2 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mhm.get.l2_domain_info()
        self.gridspec["L2"] = fm.EsriGrid(
            ncols=ncols, nrows=nrows, cellsize=cell_size, xllcorner=xll, yllcorner=yll
        )
        for var in self.OUTPUT_NAMES:
            grid_name = _get_grid_name(var)
            self.outputs.add(
                name=var,
                time=self.time,
                grid=self.gridspec[grid_name],
                missing_value=self.no_data,
                **OUTPUT_META[var],
            )
        for var in self.INPUT_NAMES:
            grid_name = _get_grid_name(var)
            self.inputs.add(
                name=var,
                time=self.time,
                grid=self.gridspec[grid_name],
                missing_value=self.no_data,
                **INPUT_META[var],
            )
        self.create_connector()

    def _connect(self, start_time):
        push_data = {var: self._get(var) for var in self.OUTPUT_NAMES}
        self.try_connect(start_time=start_time, push_data=push_data)

    @fm.tools.execute_in_cwd
    def _update(self):
        # Don't run further than mHM can
        if mhm.run.finished():
            return
        # set meteo data
        if self.meteo_inputs:
            # every hour or every 24 hours
            if self.time.hour % self.meteo_timestep == 0:
                kwargs = {
                    var: self.inputs[name].pull_data(self.time)
                    for var, name in self.meteo_inputs.items()
                }
                kwargs["time"] = self.time
                mhm.set_meteo(**kwargs)
        # run mhm
        mhm.run.do_time_step()
        # update time
        year, month, day, hour = mhm.run.current_time()
        self.time = datetime(year=year, month=month, day=day, hour=hour)
        # push outputs
        for var in self.OUTPUT_NAMES:
            if not self.outputs[var].has_targets:
                continue
            self.outputs[var].push_data(
                data=mhm.get_variable(var),
                time=self.time,
            )

    @fm.tools.execute_in_cwd
    def _finalize(self):
        mhm.run.finalize_domain()
        mhm.run.finalize()
        mhm.model.finalize()
