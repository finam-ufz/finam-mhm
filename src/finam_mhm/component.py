"""
FINAM mHM module.
"""

from datetime import datetime, timedelta
from pathlib import Path

import f90nml
import finam as fm
import mhm

from .constants import (
    HOURS_TO_TIMESTEP,
    INPUT_UNITS,
    MRM_OUTPUT_META,
    OUTPUT_CALC,
    OUTPUT_CALC_HORIZON,
    OUTPUT_CALC_HORIZONS_META,
    OUTPUT_CALC_META,
    OUTPUT_HORIZONS_META,
    OUTPUT_META,
)


def _horizon_name(name, horizon):
    return name + "_L" + str(horizon).zfill(2)


def _get_grid_name(var):
    grid_name = var.split("_")[0]
    return "L1" if grid_name == "METEO" else grid_name


def _get_var_name(var):
    return "_".join(var.split("_")[1:])


def _get_meteo_inputs(inputs):
    return {
        _get_var_name(var).lower(): var for var in inputs if var.startswith("METEO")
    }


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
        self.masks = {}
        self.no_data = None
        self.number_of_horizons = None
        self.config = f90nml.read(Path(cwd) / namelist_mhm).todict()
        # check mrm case
        case = self.config.get("processselection", {}).get("processcase", [])
        mrm_set = case[7] if len(case) >= 8 else None
        self.mrm_active = mrm_set is not None and mrm_set > 0
        self.OUTPUT_NAMES = None
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

    def _next_time(self):
        """Next pull time."""
        return self.time + self.step

    @property
    def horizons(self):
        """Iterator for all horizons starting at 1."""
        return range(1, self.number_of_horizons + 1)

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
        self.number_of_horizons = mhm.get.number_of_horizons()
        # prepare outputs
        self.OUTPUT_NAMES = list(OUTPUT_META)
        if self.mrm_active:
            self.OUTPUT_NAMES += list(MRM_OUTPUT_META)
        self.OUTPUT_NAMES += [
            _horizon_name(var, horizon)
            for var in OUTPUT_HORIZONS_META
            for horizon in self.horizons
        ]
        self.OUTPUT_NAMES += list(OUTPUT_CALC_META)
        self.OUTPUT_NAMES += [
            _horizon_name(var, horizon)
            for var in OUTPUT_CALC_HORIZONS_META
            for horizon in self.horizons
        ]
        # get start time
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
        self.masks["L0"] = mhm.get_mask("L0")
        # get grid info l1 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mhm.get.l1_domain_info()
        self.gridspec["L1"] = fm.EsriGrid(
            ncols=ncols, nrows=nrows, cellsize=cell_size, xllcorner=xll, yllcorner=yll
        )
        self.masks["L1"] = mhm.get_mask("L1")
        if self.mrm_active:
            # get grid info l11 (swap rows/cols to get "ij" indexing)
            nrows, ncols, __, xll, yll, cell_size, no_data = mhm.get.l11_domain_info()
            self.gridspec["L11"] = fm.EsriGrid(
                ncols=ncols,
                nrows=nrows,
                cellsize=cell_size,
                xllcorner=xll,
                yllcorner=yll,
            )
            self.masks["L11"] = mhm.get_mask("L11")
        # get grid info l2 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mhm.get.l2_domain_info()
        self.gridspec["L2"] = fm.EsriGrid(
            ncols=ncols, nrows=nrows, cellsize=cell_size, xllcorner=xll, yllcorner=yll
        )
        self.masks["L2"] = mhm.get_mask("L2")
        for var, meta in OUTPUT_META.items():
            grid_name = _get_grid_name(var)
            self.outputs.add(
                name=var,
                time=self.time,
                grid=self.gridspec[grid_name],
                missing_value=self.no_data,
                _FillValue=self.no_data,
                mask=self.masks[grid_name],
                **meta,
            )
        if self.mrm_active:
            for var, meta in MRM_OUTPUT_META.items():
                grid_name = _get_grid_name(var)
                self.outputs.add(
                    name=var,
                    time=self.time,
                    grid=self.gridspec[grid_name],
                    missing_value=self.no_data,
                    _FillValue=self.no_data,
                    mask=self.masks[grid_name],
                    **meta,
                )
        for var, meta in OUTPUT_CALC_META.items():
            grid_name = _get_grid_name(var)
            self.outputs.add(
                name=var,
                time=self.time,
                grid=self.gridspec[grid_name],
                missing_value=self.no_data,
                _FillValue=self.no_data,
                mask=self.masks[grid_name],
                **meta,
            )
        for var, meta in OUTPUT_HORIZONS_META.items():
            grid_name = _get_grid_name(var)
            for horizon in self.horizons:
                # add horizon number to long name
                n_meta = {
                    att: val.format(n=horizon) if att == "long_name" else val
                    for att, val in meta.items()
                }
                self.outputs.add(
                    name=_horizon_name(var, horizon),
                    time=self.time,
                    grid=self.gridspec[grid_name],
                    missing_value=self.no_data,
                    _FillValue=self.no_data,
                    mask=self.masks[grid_name],
                    **n_meta,
                )
        for var, meta in OUTPUT_CALC_HORIZONS_META.items():
            grid_name = _get_grid_name(var)
            for horizon in self.horizons:
                # add horizon number to long name
                n_meta = {
                    att: val.format(n=horizon) if att == "long_name" else val
                    for att, val in meta.items()
                }
                self.outputs.add(
                    name=_horizon_name(var, horizon),
                    time=self.time,
                    grid=self.gridspec[grid_name],
                    missing_value=self.no_data,
                    _FillValue=self.no_data,
                    mask=self.masks[grid_name],
                    **n_meta,
                )
        for var in self.INPUT_NAMES:
            grid_name = _get_grid_name(var)
            self.inputs.add(
                name=var,
                time=self.time,
                grid=None if self.ignore_input_grid else self.gridspec[grid_name],
                missing_value=self.no_data,
                _FillValue=self.no_data,
                mask=None if self.ignore_input_grid else self.masks[grid_name],
                units=INPUT_UNITS[var].format(
                    ts=HOURS_TO_TIMESTEP[self.meteo_timestep]
                ),
            )
        self.create_connector()

    def _connect(self, start_time):
        push_data = {var: mhm.get_variable(var) for var in OUTPUT_META}
        if self.mrm_active:
            push_data.update({var: mhm.get_variable(var) for var in MRM_OUTPUT_META})
        push_data.update({var: func() for var, func in OUTPUT_CALC.items()})
        push_data.update(
            {
                _horizon_name(var, horizon): mhm.get_variable(var, index=horizon)
                for var in OUTPUT_HORIZONS_META
                for horizon in self.horizons
            }
        )
        push_data.update(
            {
                _horizon_name(var, horizon): func(horizon)
                for var, func in OUTPUT_CALC_HORIZON.items()
                for horizon in self.horizons
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
                    var: self.inputs[name].pull_data(self.next_time)[0].magnitude
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
        if self.mrm_active:
            for var in MRM_OUTPUT_META:
                if not self.outputs[var].has_targets:
                    continue
                self.outputs[var].push_data(
                    data=mhm.get_variable(var),
                    time=self.time,
                )
        for var, func in OUTPUT_CALC.items():
            if not self.outputs[var].has_targets:
                continue
            self.outputs[var].push_data(
                data=func(),
                time=self.time,
            )
        for var in OUTPUT_HORIZONS_META:
            for horizon in self.horizons:
                name = _horizon_name(var, horizon)
                if not self.outputs[name].has_targets:
                    continue
                self.outputs[name].push_data(
                    data=mhm.get_variable(var, index=horizon),
                    time=self.time,
                )
        for var, func in OUTPUT_CALC_HORIZON.items():
            for horizon in self.horizons:
                name = _horizon_name(var, horizon)
                if not self.outputs[name].has_targets:
                    continue
                self.outputs[name].push_data(
                    data=func(horizon),
                    time=self.time,
                )
        if mhm.run.finished():
            self.status = fm.ComponentStatus.FINISHED

    @fm.tools.execute_in_cwd
    def _finalize(self):
        mhm.run.finalize_domain()
        mhm.run.finalize()
        mhm.model.finalize()
