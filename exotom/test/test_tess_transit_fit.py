from unittest.mock import MagicMock

import pandas as pd
from astropy.time import Time

from django.test import TestCase

from exotom.models import Target, Transit
from exotom.transits import calculate_transits_during_next_n_days

from exotom.tess_transit_fit import TessTransitFit


class Test(TestCase):
    def setUp(self) -> None:
        self.data_file1 = "exotom/test/test_tess_transit_fit_data/TOI_1809.01_transit_79_light_curve_best.csv"
        self.data_file2 = "exotom/test/test_tess_transit_fit_data/TOI_1844.01_transit_105_light_curve_best.csv"

        target1_dict = {
            "name": "test_TOI 1809.01",
            "type": "SIDEREAL",
            "ra": 183.3660,
            "dec": 23.0557,
        }
        target1_extra_fields = {
            "Priority Proposal": False,
            "Mag (TESS)": 11.5384,
            "Epoch (BJD)": 2458902.718492,
            "Period (days)": 4.617208,
            "Duration (hours)": 3.588807,
            "Depth (mmag)": 12.207647,
            "Stellar Distance (pc)": 321.084,
            "Stellar Radius (R_Sun)": 1.1136,
            "Planet Radius (R_Earth)": 12.041519,
        }
        self.target1 = Target(**target1_dict)
        self.target1.save(extras=target1_extra_fields)

        target2_dict = {
            "name": "test_TOI 1844.01",
            "type": "SIDEREAL",
            "ra": 209.3886,
            "dec": 43.4933,
        }
        target2_extra_fields = {
            "Priority Proposal": False,
            "Mag (TESS)": 11.7551,
            "Epoch (BJD)": 2458930.329998,
            "Period (days)": 3.212983,
            "Duration (hours)": 2.361831,
            "Depth (mmag)": 25.410942,
            "Stellar Distance (pc)": 142.751,
            "Stellar Radius (R_Sun)": 0.703594,
            "Planet Radius (R_Earth)": 10.690659,
        }
        self.target2 = Target(**target2_dict)
        self.target2.save(extras=target2_extra_fields)

        # create transit object by running calculate_transits_during_next_n_days
        self.test_now = Time("2021-02-21T15:00:00")
        Time.now = MagicMock(return_value=self.test_now)

        calculate_transits_during_next_n_days(self.target1, 1)
        calculate_transits_during_next_n_days(self.target2, 1)

    def test_fit(self):
        # check that transit #79/105 was created
        self.transit1 = Transit.objects.get(target=self.target1, number=79)
        self.transit2 = Transit.objects.get(target=self.target2, number=105)

        light_curve_df1 = pd.read_csv(self.data_file1)
        light_curve_df2 = pd.read_csv(self.data_file2)

        tess_transit_fit1 = TessTransitFit(light_curve_df1, self.transit1)
        params1, c1, _ = tess_transit_fit1.make_simplest_fit_and_report()

        self.assertAlmostEqual(params1.a, 1.31923941e01, places=2)
        self.assertAlmostEqual(params1.per, 4.68757298e00, places=2)
        self.assertAlmostEqual(params1.inc, 8.99998646e01, places=2)
        self.assertAlmostEqual(params1.ecc, 1.39460377e-03, places=2)
        self.assertAlmostEqual(params1.w, 7.48922400e01, places=2)
        self.assertAlmostEqual(c1, 5.55937105e-03, places=2)

        tess_transit_fit2 = TessTransitFit(light_curve_df2, self.transit2)
        params2, c2, _ = tess_transit_fit2.make_simplest_fit_and_report()

        self.assertAlmostEqual(params2.a, 1.71652884e01, places=2)
        self.assertAlmostEqual(params2.per, 3.63653789e00, places=2)
        self.assertAlmostEqual(params2.inc, 8.99999936e01, places=2)
        self.assertAlmostEqual(params2.ecc, 7.72140370e-04, places=2)
        self.assertAlmostEqual(params2.w, 9.75883643e01, places=2)
        self.assertAlmostEqual(c2, 3.09881769e-03, places=2)
