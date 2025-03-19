import os
import shutil
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import finam as fm
import mhm
import numpy as np
from numpy.testing import assert_allclose

import finam_mhm as fm_mhm


def str2date(dtstr):
    return datetime.fromisoformat(dtstr)


class TestMHM(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.here = Path(__file__).parent
        os.chdir(self.here)
        self.test_domain = self.here / "test_domain"
        mhm.download_test(path=self.test_domain)

    def tearDown(self):
        # move out of test-domain directory after each test
        os.chdir(self.here)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.test_domain)

    def test_run(self):
        start_date = datetime(1990, 1, 1)
        end_date = datetime(1991, 1, 1)

        mhm = fm_mhm.MHM(cwd=self.test_domain)
        csv = fm.components.CsvWriter(
            path=self.here / "runoff_out.csv",
            inputs=["Runoff"],
            time_column="Time",
            separator=",",
            start=start_date,
            step=timedelta(hours=1),
        )

        composition = fm.Composition([mhm, csv])

        (
            mhm.outputs["L1_TOTAL_RUNOFF"]
            >> fm.adapters.GridToValue(func=lambda x: x[0, 8, 4])
            >> csv["Runoff"]
        )

        composition.run(start_time=start_date, end_time=end_date)

        ref = np.genfromtxt(
            self.here / "test_files/ref_runoff.csv",
            names=True,
            converters={0: str2date},
            delimiter=",",
            dtype=None,
            encoding="utf-8",
        )
        ref = np.array([i[1] for i in ref])
        out = np.genfromtxt(
            self.here / "runoff_out.csv",
            names=True,
            converters={0: str2date},
            delimiter=",",
            dtype=None,
            encoding="utf-8",
        )
        out = np.array([i[1] for i in out])

        assert_allclose(ref, out)


if __name__ == "__main__":
    unittest.main()
