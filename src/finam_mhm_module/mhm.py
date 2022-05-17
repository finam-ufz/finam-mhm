"""
FINAM mHM module.
"""
from datetime import datetime

import mhm_pybind as mp
import numpy as np
from finam.core.interfaces import ComponentStatus
from finam.core.sdk import ATimeComponent, Input, Output
from finam.data.grid import Grid, GridSpec
from finam.tools.cwd_helper import execute_in_cwd


class Mhm(ATimeComponent):
    OUTPUT_NAMES = [
        "L0_GRIDDED_LAI",
        "L1_FSEALED",
        "L1_FNOTSEALED",
        "L1_INTER",
        "L1_SNOWPACK",
        "L1_SEALSTW",
        "L1_UNSATSTW",
        "L1_SATSTW",
        "L1_NEUTRONS",
        "L1_PET_CALC",
        "L1_AETCANOPY",
        "L1_AETSEALED",
        "L1_TOTAL_RUNOFF",
        "L1_RUNOFFSEAL",
        "L1_FASTRUNOFF",
        "L1_SLOWRUNOFF",
        "L1_BASEFLOW",
        "L1_PERCOL",
        "L1_PREEFFECT",
        "L1_SOILMOIST_VOL_ALL",
        "L11_QMOD",
        "L11_QOUT",
        "L11_QTIN",
        "L11_QTR",
    ]

    def __init__(
        self,
        namelist_mhm="mhm.nml",
        namelist_mhm_param="mhm_parameter.nml",
        namelist_mhm_output="mhm_outputs.nml",
        namelist_mrm_output="mrm_outputs.nml",
        cwd=".",
        input_names=None,
    ):
        self.INPUT_NAMES = [] if input_names is None else list(input_names)
        super(Mhm, self).__init__()
        self.namelist_mhm = namelist_mhm
        self.namelist_mhm_param = namelist_mhm_param
        self.namelist_mhm_output = namelist_mhm_output
        self.namelist_mrm_output = namelist_mrm_output
        self.cwd = cwd  # needed for @execute_in_cwd
        self._status = ComponentStatus.CREATED

    @execute_in_cwd
    def initialize(self):
        super().initialize()
        mp.mhm.init(
            namelist_mhm=self.namelist_mhm,
            namelist_mhm_param=self.namelist_mhm_param,
            namelist_mhm_output=self.namelist_mhm_output,
            namelist_mrm_output=self.namelist_mrm_output,
            cwd=".",
        )
        mp.run.prepare()
        mp.run.prepare_domain()
        # set time
        year, month, day, hour = mp.run.current_time()
        hour = max(hour, 0)  # fix for first time step
        self._time = datetime(year=year, month=month, day=day, hour=hour)
        self.gridspec = {}
        # get grid info l0 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mp.get.l0_domain_info()
        self.no_data = no_data
        self.gridspec["L0"] = GridSpec(
            ncols=ncols, nrows=nrows, cell_size=cell_size, xll=xll, yll=yll
        )
        # get grid info l1 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mp.get.l1_domain_info()
        self.gridspec["L1"] = GridSpec(
            ncols=ncols, nrows=nrows, cell_size=cell_size, xll=xll, yll=yll
        )
        # get grid info l11 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mp.get.l11_domain_info()
        self.gridspec["L11"] = GridSpec(
            ncols=ncols, nrows=nrows, cell_size=cell_size, xll=xll, yll=yll
        )
        # get grid info l2 (swap rows/cols to get "ij" indexing)
        nrows, ncols, __, xll, yll, cell_size, no_data = mp.get.l2_domain_info()
        self.gridspec["L2"] = GridSpec(
            ncols=ncols, nrows=nrows, cell_size=cell_size, xll=xll, yll=yll
        )
        for var in self.OUTPUT_NAMES:
            self.outputs[var] = Output()
        for var in self.INPUT_NAMES:
            self.inputs[var] = Input()

        self._status = ComponentStatus.INITIALIZED

    def connect(self):
        super().connect()
        for var in self.OUTPUT_NAMES:
            if not self.outputs[var].has_targets:
                continue
            self.outputs[var].push_data(
                data=Grid(
                    spec=self.gridspec[var.split("_")[0]],
                    no_data=self.no_data,
                    # flip upside down to use lower-left corner as origin
                    data=np.flipud(
                        mp.get_variable(var, indexing="ij").filled()
                    ).reshape(-1),
                ),
                time=self.time,
            )
        self._status = ComponentStatus.CONNECTED

    def validate(self):
        super().validate()
        # TODO: add checks if connected outputs are compatible with process selection
        self._status = ComponentStatus.VALIDATED

    @execute_in_cwd
    def update(self):
        super().update()

        # Don't run further than mHM can
        if mp.run.finished():
            return
        mp.run.do_time_step()
        mp.run.write_output()  # do we want this here?
        # update time
        year, month, day, hour = mp.run.current_time()
        self._time = datetime(year=year, month=month, day=day, hour=hour)
        # push outputs
        for var in self.OUTPUT_NAMES:
            if not self.outputs[var].has_targets:
                continue
            self.outputs[var].push_data(
                data=Grid(
                    spec=self.gridspec[var.split("_")[0]],
                    no_data=self.no_data,
                    # flip upside down to use lower-left corner as origin
                    data=np.flipud(
                        mp.get_variable(var, indexing="ij").filled()
                    ).reshape(-1),
                ),
                time=self.time,
            )
        self._status = ComponentStatus.UPDATED

    @execute_in_cwd
    def finalize(self):
        super().finalize()
        mp.run.finalize_domain()
        mp.run.finalize()
        mp.mhm.finalize()
        self._status = ComponentStatus.FINALIZED
