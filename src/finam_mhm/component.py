"""
FINAM mHM module.
"""
# pylint: disable=R1735
from datetime import datetime, timedelta

import finam as fm
import mhm

OUTPUT_META = {
    "L0_GRIDDED_LAI": dict(units="1", long_name="leaf area index"),
    "L1_FSEALED": dict(units="1", long_name="Fraction of sealed area"),
    "L1_FNOTSEALED": dict(units="1", long_name="Fraction of unsealed area"),
    "L1_INTER": dict(units="mm / h", long_name="Interception"),
    "L1_SNOWPACK": dict(units="mm / h", long_name="Snowpack"),
    "L1_SEALSTW": dict(
        units="mm / h", long_name="Retention storage of impervious areas"
    ),
    "L1_UNSATSTW": dict(units="mm / h", long_name="upper soil storage"),
    "L1_SATSTW": dict(units="mm / h", long_name="groundwater storage"),
    "L1_NEUTRONS": dict(units="mm / h", long_name="Ground Albedo Neutrons"),
    "L1_PET_CALC": dict(units="mm / h", long_name="potential evapotranspiration"),
    "L1_AETCANOPY": dict(
        units="mm / h", long_name="Real evaporation intensity from canopy"
    ),
    "L1_AETSEALED": dict(
        units="mm / h", long_name="Real evap. from free water surfaces"
    ),
    "L1_TOTAL_RUNOFF": dict(units="m^3 / h", long_name="Generated runoff"),
    "L1_RUNOFFSEAL": dict(
        units="mm / h", long_name="Direct runoff from impervious areas"
    ),
    "L1_FASTRUNOFF": dict(units="mm / h", long_name="Fast runoff component"),
    "L1_SLOWRUNOFF": dict(units="mm / h", long_name="Slow runoff component"),
    "L1_BASEFLOW": dict(units="mm / h", long_name="Baseflow"),
    "L1_PERCOL": dict(units="mm / h", long_name="Percolation"),
    "L1_PREEFFECT": dict(units="mm / h", long_name="Effective precip. depth"),
    "L1_SOILMOIST_VOL_ALL": dict(
        units="1", long_name="average soil moisture over all layers"
    ),
    "L11_QMOD": dict(units="m^3 / s", long_name="Simulated discharge"),
    "L11_QOUT": dict(units="m^3 / s", long_name="Total outflow from cells"),
}
"""dict: meta information about available outputs in mHM."""

OUTPUT_HORIZONS_META = {
    "L1_SOILMOIST": dict(units="mm", long_name="soil water content of soil layer"),
    "L1_SOILMOIST_VOL": dict(
        units="mm / mm", long_name="volumetric soil moisture of soil layer"
    ),
    "L1_SOILMOISTSAT": dict(
        units="mm", long_name="Saturation soil moisture for each horizon"
    ),
    "L1_AETSOIL": dict(units="mm / h", long_name="Actual ET from soil layers"),
    "L1_INFILSOIL": dict(
        units="mm / h", long_name="Infiltration intensity each soil horizon"
    ),
}
"""dict: meta information about available outputs per horizon in mHM."""

INPUT_UNITS = {
    "L0_GRIDDED_LAI": "1",
    "METEO_PRE": "mm / {ts}",
    "METEO_TEMP": "degC",
    "METEO_PET": "mm / {ts}",
    "METEO_TMIN": "degC",
    "METEO_TMAX": "degC",
    "METEO_NETRAD": "W m-2",
    "METEO_ABSVAPPRESS": "Pa",
    "METEO_WINDSPEED": "m s-1",
    "METEO_SSRD": "W m-2",
    "METEO_STRD": "W m-2",
    "METEO_TANN": "degC",
}
"""dict: units of the available inputs in mHM."""

HOURS_TO_TIMESTEP = {1: "h", 24: "d"}
"""dict: timestep string from hours."""


def _get_grid_name(var):
    grid_name = var.split("_")[0]
    return "L1" if grid_name == "METEO" else grid_name


def _get_var_name(var):
    return "_".join(var.split("_")[1:])


def _get_meteo_inputs(inputs):
    return {
        _get_var_name(var).lower(): var for var in inputs if var.startswith("METEO")
    }


def _horizon_name(name, horizon):
    return name + "_L" + str(horizon).zfill(2)


class MHM(fm.TimeComponent):
    """
    mHM FINAM compoment.

    Parameters
    ----------
    namelist_mhm : str, optional
        path to mHM configuration namelist, by default "mhm.nml"
    namelist_mhm_param : str, optional
        path to mHM parameter namelist, by default "mhm_parameter.nml"
    namelist_mhm_output : str, optional
        path to mHM output namelist, by default "mhm_outputs.nml"
    namelist_mrm_output : str, optional
        path to mRM output namelist, by default "mrm_outputs.nml"
    cwd : str, optional
        desired working directory, by default "."
    input_names : list of str, optional
        Names of input variables coupled via FINAM, by default None
    meteo_timestep : int, optional
        meteo coupling time-step in hours (1 or 24), by default None
    ignore_input_grid : bool, optional
        use any input grid without checking compatibility, by default False

    Raises
    ------
    ValueError
        If a given input name is invalid.
    ValueError
        If the given meteo time-step is invalid
    """

    def __init__(
        self,
        namelist_mhm="mhm.nml",
        namelist_mhm_param="mhm_parameter.nml",
        namelist_mhm_output="mhm_outputs.nml",
        namelist_mrm_output="mrm_outputs.nml",
        cwd=".",
        input_names=None,
        meteo_timestep=None,
        ignore_input_grid=False,
    ):
        super().__init__()
        self.gridspec = {}
        self.no_data = None
        self.horizons = None

        self.OUTPUT_NAMES = list(OUTPUT_META)
        self.INPUT_NAMES = (
            [] if input_names is None else [n.upper() for n in input_names]
        )
        for in_name in self.INPUT_NAMES:
            if in_name not in INPUT_UNITS:
                msg = f"mHM: input '{in_name}' is not available."
                raise ValueError(msg)
        self.namelist_mhm = namelist_mhm
        self.namelist_mhm_param = namelist_mhm_param
        self.namelist_mhm_output = namelist_mhm_output
        self.namelist_mrm_output = namelist_mrm_output
        self.cwd = cwd  # needed for @fm.tools.execute_in_cwd
        # mHM always has hourly stepping
        self.step = timedelta(hours=1)
        self.meteo_timestep = meteo_timestep
        self.meteo_inputs = _get_meteo_inputs(self.INPUT_NAMES)
        self.ignore_input_grid = ignore_input_grid

        if self.meteo_inputs and self.meteo_timestep not in HOURS_TO_TIMESTEP:
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
        self.horizons = mhm.get.number_of_horizons()
        self.OUTPUT_NAMES += [
            _horizon_name(var, horizon)
            for var in OUTPUT_HORIZONS_META
            for horizon in range(1, self.horizons)
        ]
        # set time
        year, month, day, hour = mhm.run.current_time()
        self.time = datetime(year=year, month=month, day=max(day, 0), hour=max(hour, 0))
        # first time step compensate by negative values in mHM
        if day < 0 or hour < 0:
            self.time += timedelta(days=min(day, 0), hours=min(hour, 0))

        # store Grid specifications
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
        for var in OUTPUT_META:
            grid_name = _get_grid_name(var)
            self.outputs.add(
                name=var,
                time=self.time,
                grid=self.gridspec[grid_name],
                missing_value=self.no_data,
                _FillValue=self.no_data,
                **OUTPUT_META[var],
            )
        for var in OUTPUT_HORIZONS_META:
            grid_name = _get_grid_name(var)
            for horizon in range(1, self.horizons + 1):
                self.outputs.add(
                    name=_horizon_name(var, horizon),
                    time=self.time,
                    grid=self.gridspec[grid_name],
                    missing_value=self.no_data,
                    _FillValue=self.no_data,
                    **OUTPUT_HORIZONS_META[var],
                )
        for var in self.INPUT_NAMES:
            grid_name = _get_grid_name(var)
            self.inputs.add(
                name=var,
                time=self.time,
                grid=None if self.ignore_input_grid else self.gridspec[grid_name],
                missing_value=self.no_data,
                _FillValue=self.no_data,
                units=INPUT_UNITS[var].format(
                    ts=HOURS_TO_TIMESTEP[self.meteo_timestep]
                ),
            )
        self.create_connector()

    def _connect(self, start_time):
        push_data = {var: mhm.get_variable(var) for var in OUTPUT_META}
        push_data.update(
            {
                _horizon_name(var, horizon): mhm.get_variable(var, index=horizon)
                for var in OUTPUT_HORIZONS_META
                for horizon in range(1, self.horizons + 1)
            }
        )
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
                    var: self.inputs[name].pull_data(self.time)[0].magnitude
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
        for var in OUTPUT_META:
            if not self.outputs[var].has_targets:
                continue
            self.outputs[var].push_data(
                data=mhm.get_variable(var),
                time=self.time,
            )
        for var in OUTPUT_HORIZONS_META:
            for horizon in range(1, self.horizons + 1):
                name = _horizon_name(var, horizon)
                if not self.outputs[name].has_targets:
                    continue
                self.outputs[name].push_data(
                    data=mhm.get_variable(var, index=horizon),
                    time=self.time,
                )

    @fm.tools.execute_in_cwd
    def _finalize(self):
        mhm.run.finalize_domain()
        mhm.run.finalize()
        mhm.model.finalize()
