"""
FINAM mHM module.
"""
from datetime import datetime

import mhm_pybind as mp
from finam.core.interfaces import ComponentStatus
from finam.core.sdk import ATimeComponent, Input, Output
from finam.data.grid import Grid, GridSpec
from finam.tools.cwd_helper import execute_in_cwd


class Mhm(ATimeComponent):
    def __init__(
        self,
        namelist_mhm="mhm.nml",
        namelist_mhm_param="mhm_parameter.nml",
        namelist_mhm_output="mhm_outputs.nml",
        namelist_mrm_output="mrm_outputs.nml",
        cwd=".",
    ):
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
        # print("time", year, month, day, hour)
        hour = max(hour, 0)  # fix for first time step
        self._time = datetime(year=year, month=month, day=day, hour=hour)
        # get grid info l0
        ncols, nrows, __, xll, yll, cell_size, no_data = mp.get.l0_domain_info()
        self.no_data = no_data
        self.gridspec_l0 = GridSpec(
            ncols=ncols, nrows=nrows, cell_size=cell_size, xll=xll, yll=yll
        )
        # get grid info l1
        ncols, nrows, __, xll, yll, cell_size, no_data = mp.get.l1_domain_info()
        self.gridspec_l1 = GridSpec(
            ncols=ncols, nrows=nrows, cell_size=cell_size, xll=xll, yll=yll
        )
        # get grid info l11
        ncols, nrows, __, xll, yll, cell_size, no_data = mp.get.l11_domain_info()
        self.gridspec_l11 = GridSpec(
            ncols=ncols, nrows=nrows, cell_size=cell_size, xll=xll, yll=yll
        )
        # get grid info l2
        ncols, nrows, __, xll, yll, cell_size, no_data = mp.get.l2_domain_info()
        self.gridspec_l2 = GridSpec(
            ncols=ncols, nrows=nrows, cell_size=cell_size, xll=xll, yll=yll
        )
        self.outputs["runoff"] = Output()
        # self.inputs["LAI"] = Input()

        self._status = ComponentStatus.INITIALIZED

    def connect(self):
        super().connect()
        runoff = mp.get_variable("L1_total_runoff")
        self._outputs["runoff"].push_data(
            data=Grid(
                spec=self.gridspec_l1,
                no_data=self.no_data,
                data=runoff.filled().reshape(-1),
            ),
            time=self.time,
        )
        self._status = ComponentStatus.CONNECTED

    def validate(self):
        super().validate()
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
        runoff = mp.get_variable("L1_total_runoff")
        self._outputs["runoff"].push_data(
            data=Grid(
                spec=self.gridspec_l1,
                no_data=self.no_data,
                data=runoff.filled().reshape(-1),
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
