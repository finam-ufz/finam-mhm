"""
FINAM mHM module.
"""
from datetime import datetime
import mhm_pybind as mp

from finam.core.sdk import ATimeComponent, Output
from finam.core.interfaces import ComponentStatus
from finam.data.grid import Grid, GridSpec


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
        mp.mhm.init(
            namelist_mhm=namelist_mhm,
            namelist_mhm_param=namelist_mhm_param,
            namelist_mhm_output=namelist_mhm_output,
            namelist_mrm_output=namelist_mrm_output,
            cwd=cwd,
        )
        self._status = ComponentStatus.CREATED

    def initialize(self):
        super().initialize()
        mp.run.prepare()
        mp.run.prepare_domain()
        # set time
        year, month, day, hour = mp.run.current_time()
        self._time = datetime(year=year, month=month, day=day, hour=hour)
        # get grid info
        ncols, nrows, ncells, xll, yll, cell_size, no_data = mp.get.L1_domain_info()
        self.no_data = no_data
        self.gridspec = GridSpec(
            ncols=ncols, nrows=nrows, cell_size=cell_size, xll=xll, yll=yll
        )
        self.outputs["runoff"] = Output()
        self._status = ComponentStatus.INITIALIZED

    def connect(self):
        super().connect()
        runoff = mp.get_variable("L1_total_runoff")
        self._outputs["runoff"].push_data(
            data=Grid(
                spec=self.gridspec,
                no_data=self.no_data,
                data=runoff.filled().reshape(-1),
            ),
            time=self.time,
        )
        self._status = ComponentStatus.CONNECTED

    def validate(self):
        super().validate()
        self._status = ComponentStatus.VALIDATED

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
                spec=self.gridspec,
                no_data=self.no_data,
                data=runoff.filled().reshape(-1),
            ),
            time=self.time,
        )
        self._status = ComponentStatus.UPDATED

    def finalize(self):
        super().finalize()
        mp.run.finalize_domain()
        mp.run.finalize()
        mp.mhm.finalize()
        self._status = ComponentStatus.FINALIZED
