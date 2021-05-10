from unittest.mock import MagicMock

import pandas as pd
from astropy.coordinates import EarthLocation
from astropy.time import Time
import astropy.units as u

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
            "Epoch (BJD) err": 0.000252,  # made up value
            "Period (days)": 4.617208,
            "Period (days) err": 1e-6,  # made up value
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
            "Epoch (BJD) err": 0.000252,  # made up value
            "Period (days)": 3.212983,
            "Period (days) err": 1e-6,  # made up value
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

    def test_fit_no_airmass_detrending(self):
        # check that transit #79/105 was created
        self.transit1 = Transit.objects.get(target=self.target1, number=79)
        self.transit2 = Transit.objects.get(target=self.target2, number=105)

        light_curve_df1 = pd.read_csv(self.data_file1)
        light_curve_df2 = pd.read_csv(self.data_file2)

        target_extras = list(self.transit1.target.targetextra_set.all())
        tess_transit_fit1 = TessTransitFit(
            light_curve_df1, self.transit1, target_extras
        )
        (
            params1,
            _,
            baseline_model1,
            chi_squared1,
            fit_report1,
        ) = tess_transit_fit1.make_simplest_fit_and_report()

        self.assertAlmostEqual(params1.a, 10.119311669789562, places=2)
        self.assertAlmostEqual(params1.t0, 2459267.45761117, places=2)
        self.assertAlmostEqual(params1.inc, 89.99997454051741, places=2)
        self.assertAlmostEqual(params1.ecc, 0.058767982705156555, places=2)
        self.assertAlmostEqual(params1.w, 36.991004415580655, places=2)
        self.assertAlmostEqual(params1.u[0], 0.8510291929224456, places=2)

        self.assertEqual(baseline_model1, None)

        fit_report1_expected = """Initial batman TransitParams:
{'a': 16.301326571397812,
 'ecc': 0,
 'fp': None,
 'inc': 90,
 'limb_dark': 'linear',
 'per': 4.617208,
 'rp': 0.09902148034556439,
 't0': 2459267.472122768,
 't_secondary': None,
 'u': [0.4],
 'w': 90}

Starting fit without airmass detrending...
   Iteration     Total nfev        Cost      Cost reduction    Step norm     Optimality   
       0              1         3.1254e-02                                    4.49e+00    
       1              3         1.8884e-02      1.24e-02       6.35e+00       2.23e-01    
       2              4         1.8382e-02      5.03e-04       6.51e+00       3.43e-01    
       3              5         1.7115e-02      1.27e-03       4.10e+00       1.71e-01    
       4              6         1.6144e-02      9.72e-04       4.01e+00       1.04e-01    
       5              7         1.5182e-02      9.62e-04       1.27e+00       7.79e-02    
       6              8         1.4572e-02      6.10e-04       1.10e+01       5.23e-02    
       7              9         1.4440e-02      1.33e-04       3.14e+01       6.66e-02    
       8             11         1.4367e-02      7.25e-05       4.87e+00       4.08e-02    
       9             13         1.4340e-02      2.74e-05       1.25e+00       2.62e-02    
      10             14         1.4328e-02      1.18e-05       1.89e-01       1.53e-02    
      11             16         1.4316e-02      1.17e-05       2.58e-01       8.17e-03    
      12             18         1.4312e-02      4.42e-06       1.31e-01       5.00e-03    
      13             20         1.4310e-02      1.73e-06       4.62e-02       3.28e-03    
      14             22         1.4310e-02      5.77e-07       1.41e-02       2.43e-03    
      15             24         1.4309e-02      7.22e-07       2.36e-03       2.21e-03    
      16             26         1.4309e-02      1.92e-07       1.06e-03       2.10e-03    
      17             28         1.4309e-02      7.76e-08       5.04e-04       1.84e-02    
      18             30         1.4309e-02      2.06e-08       9.89e-04       2.04e-03    
      19             31         1.4309e-02      1.53e-08       2.44e-04       2.02e-03    
      20             33         1.4309e-02      2.04e-08       6.02e-05       2.01e-03    
      21             34         1.4308e-02      1.79e-08       1.32e-04       2.01e-03    
      22             37         1.4308e-02      1.84e-09       1.50e-05       2.01e-03    
      23             38         1.4308e-02      4.79e-09       3.30e-05       2.01e-03    
      24             39         1.4308e-02      2.69e-09       6.60e-05       2.01e-03    
      25             40         1.4308e-02      1.44e-09       6.60e-05       2.01e-03    
      26             41         1.4308e-02      1.19e-09       1.65e-05       2.01e-03    
      27             48         1.4308e-02      3.82e-12       3.66e-09       2.01e-03    
`ftol` termination condition is satisfied.
Function evaluations 48, initial cost 3.1254e-02, final cost 1.4308e-02, first-order optimality 2.01e-03.

Fitted parameters and errors: [a, t0, inc, ecc, w, linear_limb_darkening_coeff, constant_factor]: 
[1.01179747e+01 2.45926746e+06 8.99999745e+01 5.95976443e-02
 3.69877052e+01 8.50866276e-01 1.00791931e+00]
[5.28963202e+02 2.15595292e-03 2.52063773e+05 1.30428188e+02
 3.83643543e+04 3.40586537e-01 4.61883582e-04]
Covariance matrix: 
[[ 2.79802069e+05  6.37205396e-01 -1.22159887e+08 -6.89916334e+04
   2.02933099e+07  1.69096245e+02  9.22041433e-02]
 [ 6.37205396e-01  4.64813298e-06 -1.67678815e+02 -1.56967848e-01
   4.61949991e+01  3.49869620e-04  6.59051356e-07]
 [-1.22159887e+08 -1.67678815e+02  6.35361456e+10  3.01400048e+07
  -8.86454058e+09 -8.21544896e+04 -1.40081079e+01]
 [-6.89916334e+04 -1.56967848e-01  3.01400048e+07  1.70115123e+04
  -5.00379264e+06 -4.17140575e+01 -2.27043766e-02]
 [ 2.02933099e+07  4.61949991e+01 -8.86454058e+09 -5.00379264e+06
   1.47182368e+09  1.22695156e+04  6.68179051e+00]
 [ 1.69096245e+02  3.49869620e-04 -8.21544896e+04 -4.17140575e+01
   1.22695156e+04  1.15999189e-01  5.66060075e-05]
 [ 9.22041433e-02  6.59051356e-07 -1.40081079e+01 -2.27043766e-02
   6.68179051e+00  5.66060075e-05  2.13336443e-07]]

Final batman TransitParams:
{'a': 10.117974707155604,
 'ecc': 0.059597644333298096,
 'fp': None,
 'inc': 89.99997454051744,
 'limb_dark': 'linear',
 'per': 4.617208,
 'rp': 0.09902148034556439,
 't0': 2459267.4576291414,
 't_secondary': None,
 'u': [0.8508662757905042],
 'w': 36.98770524766775}
"""
        self.assertEqual(fit_report1, fit_report1_expected, "Fit report 1 ist wrong")

        target_extras = list(self.transit2.target.targetextra_set.all())
        tess_transit_fit2 = TessTransitFit(
            light_curve_df2, self.transit2, target_extras
        )
        (
            params2,
            _,
            baseline_model2,
            chi_squared2,
            fit_report2,
        ) = tess_transit_fit2.make_simplest_fit_and_report()

        self.assertAlmostEqual(params2.a, 17.408156570943518, places=2)
        self.assertAlmostEqual(params2.t0, 2459267.685028074, places=2)
        self.assertAlmostEqual(params2.inc, 89.99999999079209, places=2)
        self.assertAlmostEqual(params2.ecc, 0.0017003124779760928, places=2)
        self.assertAlmostEqual(params2.w, 89.99748700120057, places=2)
        self.assertAlmostEqual(params2.u[0], 0.3999757946325413, places=2)

        self.assertEqual(baseline_model2, None)

        fit_report2_expected = """Initial batman TransitParams:
{'a': 17.408156570943518,
 'ecc': 0,
 'fp': None,
 'inc': 90,
 'limb_dark': 'linear',
 'per': 3.212983,
 'rp': 0.13914247093111606,
 't0': 2459267.6892912616,
 't_secondary': None,
 'u': [0.4],
 'w': 90}

Starting fit without airmass detrending...
   Iteration     Total nfev        Cost      Cost reduction    Step norm     Optimality   
       0              1         2.1469e-03                                    1.05e-01    
       1              6         1.3432e-03      8.04e-04       5.81e-03       3.13e-01    
       2              7         1.0326e-03      3.11e-04       2.10e-03       2.41e-02    
       3             12         1.0320e-03      6.08e-07       3.30e-05       1.94e-02    
       4             13         1.0319e-03      1.67e-07       7.11e-05       1.08e-02    
       5             16         1.0318e-03      9.22e-10       1.10e-06       1.07e-02    
       6             17         1.0318e-03      2.28e-10       2.74e-07       1.06e-02    
       7             18         1.0318e-03      4.09e-11       6.88e-08       1.06e-02    
       8             20         1.0318e-03      6.74e-12       4.30e-09       1.06e-02    
       9             21         1.0318e-03      1.01e-11       1.08e-09       1.06e-02    
`ftol` termination condition is satisfied.
Function evaluations 21, initial cost 2.1469e-03, final cost 1.0318e-03, first-order optimality 1.06e-02.

Fitted parameters and errors: [a, t0, inc, ecc, w, linear_limb_darkening_coeff, constant_factor]: 
[1.74064593e+01 2.45926769e+06 9.00000000e+01 1.70031248e-03
 8.99974870e+01 3.99975795e-01 1.00275695e+00]
[1.20147622e+04 2.03449082e-02 1.39095146e+06 6.93488146e+02
 2.35134607e+02 2.96809616e+00 3.65009311e-04]
Covariance matrix: 
[[ 1.44354511e+08 -1.81847172e+02 -3.25543963e+09 -8.33209383e+06
   2.49600457e+06  2.33197274e+04 -1.81193697e-01]
 [-1.81847172e+02  4.13915288e-04  4.25822158e+03  1.04929883e+01
  -2.21777308e+00 -5.83125036e-02 -3.37190896e-07]
 [-3.25543963e+09  4.25822158e+03  1.93474597e+12  1.87743065e+08
   1.05118838e+07 -6.11416185e+05 -1.65907885e+01]
 [-8.33209383e+06  1.04929883e+01  1.87743065e+08  4.80925808e+05
  -1.44110992e+05 -1.34532418e+03  1.04537095e-02]
 [ 2.49600457e+06 -2.21777308e+00  1.05118838e+07 -1.44110992e+05
   5.52882835e+04  2.10100208e+02 -3.03480112e-03]
 [ 2.33197274e+04 -5.83125036e-02 -6.11416185e+05 -1.34532418e+03
   2.10100208e+02  8.80959484e+00  1.60183634e-05]
 [-1.81193697e-01 -3.37190896e-07 -1.65907885e+01  1.04537095e-02
  -3.03480112e-03  1.60183634e-05  1.33231797e-07]]

Final batman TransitParams:
{'a': 17.40645930754704,
 'ecc': 0.0017003124779760928,
 'fp': None,
 'inc': 89.99999999079209,
 'limb_dark': 'linear',
 'per': 3.212983,
 'rp': 0.13914247093111606,
 't0': 2459267.685028074,
 't_secondary': None,
 'u': [0.3999757946325413],
 'w': 89.99748700120057}
"""
        self.assertEqual(fit_report2, fit_report2_expected, "Fit report 2 is wrong")

    def test_fit_with_airmass_detrending(self):
        # plugin earth location to get airmass detrending
        goe = EarthLocation(lat=51.561 * u.deg, lon=9.944 * u.deg, height=200 * u.m)

        # check that transit #79/105 was created
        self.transit1 = Transit.objects.get(target=self.target1, number=79)
        self.transit2 = Transit.objects.get(target=self.target2, number=105)

        light_curve_df1 = pd.read_csv(self.data_file1)
        light_curve_df2 = pd.read_csv(self.data_file2)

        target_extras = list(self.transit1.target.targetextra_set.all())
        tess_transit_fit1 = TessTransitFit(
            light_curve_df1, self.transit1, target_extras, goe
        )
        (
            params1,
            _,
            baseline_model1,
            chi_squared1,
            fit_report1,
        ) = tess_transit_fit1.make_simplest_fit_and_report()

        # print(params1.__dict__)
        self.assertAlmostEqual(params1.a, 12.138772208272881, places=2)
        self.assertAlmostEqual(params1.t0, 2459267.459902275, places=2)
        self.assertAlmostEqual(params1.inc, 89.99999998204359, places=2)
        self.assertAlmostEqual(params1.ecc, 0.1768564778050927, places=2)
        self.assertAlmostEqual(params1.w, -52.40002580465001, places=2)
        self.assertAlmostEqual(params1.u[0], 0.8143590262786318, places=2)

        self.assertTrue(callable(baseline_model1))
        # print("fitreport1:", fit_report1)
        fit_report1_expected = """Initial batman TransitParams:
{'a': 16.301326571397812,
 'ecc': 0,
 'fp': None,
 'inc': 90,
 'limb_dark': 'linear',
 'per': 4.617208,
 'rp': 0.09902148034556439,
 't0': 2459267.472122768,
 't_secondary': None,
 'u': [0.4],
 'w': 90}

Starting fit with airmass detrending...
   Iteration     Total nfev        Cost      Cost reduction    Step norm     Optimality   
       0              1         2.6244e+03                                    3.01e+03    
       1              2         1.9965e-02      2.62e+03       1.87e+00       6.02e-01    
       2              3         1.8463e-02      1.50e-03       8.44e+00       1.18e-01    
       3              4         1.7250e-02      1.21e-03       1.53e+02       2.06e-01    
       4              5         1.6488e-02      7.63e-04       1.28e+01       2.52e-01    
       5              6         1.5761e-02      7.27e-04       6.57e+00       2.34e-01    
       6              7         1.5143e-02      6.18e-04       2.06e+01       1.74e-01    
       7              9         1.4677e-02      4.66e-04       1.79e+01       8.58e-02    
       8             10         1.4436e-02      2.42e-04       1.85e+01       1.33e-01    
       9             11         1.4275e-02      1.61e-04       8.41e+00       7.40e-02    
      10             12         1.4217e-02      5.76e-05       5.22e+00       6.14e-02    
      11             13         1.4204e-02      1.36e-05       1.39e+00       3.08e-02    
      12             17         1.4204e-02      0.00e+00       0.00e+00       3.08e-02    
`xtol` termination condition is satisfied.
Function evaluations 17, initial cost 2.6244e+03, final cost 1.4204e-02, first-order optimality 3.08e-02.

Fitted parameters and errors: [a, t0, inc, ecc, w, linear_limb_darkening_coeff, m_airmass, b_airmass]: 
[ 1.21387722e+01  2.45926746e+06  9.00000000e+01  1.76856478e-01
 -5.24000258e+01  8.14359026e-01 -1.99982311e-03  1.01043439e+00]
[7.77415774e+02 2.10416470e-03 1.03404337e+06 1.24589341e+02
 1.27167352e+04 1.20956067e-01 1.60562230e-03 2.25021483e-03]
Covariance matrix: 
[[ 6.04375286e+05  8.28904330e-01 -3.96323189e+08  9.68576839e+04
   9.88618415e+06  5.78706934e+01 -4.10054665e-01  6.91113927e-01]
 [ 8.28904330e-01  4.42750909e-06  1.10472685e+02  1.32770915e-01
   1.35488599e+01  1.12982421e-04 -2.13591991e-06  3.28097605e-06]
 [-3.96323189e+08  1.10472685e+02  1.06924570e+12 -6.36010853e+07
  -6.49256815e+09 -7.66559924e+04  2.94206871e+01 -5.80370965e+00]
 [ 9.68576839e+04  1.32770915e-01 -6.36010853e+07  1.55225038e+04
   1.58436942e+06  9.28055844e+00 -6.56991303e-02  1.10731620e-01]
 [ 9.88618415e+06  1.35488599e+01 -6.49256815e+09  1.58436942e+06
   1.61715354e+08  9.47212864e+02 -6.71018774e+00  1.13075132e+01]
 [ 5.78706934e+01  1.12982421e-04 -7.66559924e+04  9.28055844e+00
   9.47212864e+02  1.46303702e-02 -5.11307863e-05  9.65827433e-05]
 [-4.10054665e-01 -2.13591991e-06  2.94206871e+01 -6.56991303e-02
  -6.71018774e+00 -5.11307863e-05  2.57802296e-06 -3.55729479e-06]
 [ 6.91113927e-01  3.28097605e-06 -5.80370965e+00  1.10731620e-01
   1.13075132e+01  9.65827433e-05 -3.55729479e-06  5.06346676e-06]]

Final batman TransitParams:
{'a': 12.138772208272881,
 'ecc': 0.1768564778050927,
 'fp': None,
 'inc': 89.99999998204359,
 'limb_dark': 'linear',
 'per': 4.617208,
 'rp': 0.09902148034556439,
 't0': 2459267.459902275,
 't_secondary': None,
 'u': [0.8143590262786318],
 'w': -52.40002580465001}
"""
        self.assertEqual(fit_report1, fit_report1_expected, "Fit report 1 ist wrong")

        target_extras = list(self.transit2.target.targetextra_set.all())
        tess_transit_fit2 = TessTransitFit(
            light_curve_df2, self.transit2, target_extras, goe
        )
        (
            params2,
            _,
            baseline_model2,
            chi_squared2,
            fit_report2,
        ) = tess_transit_fit2.make_simplest_fit_and_report()

        self.assertAlmostEqual(params2.a, 17.414006908617665, places=2)
        self.assertAlmostEqual(params2.t0, 2459267.688973644, places=2)
        self.assertAlmostEqual(params2.inc, 89.99999999079209, places=2)
        self.assertAlmostEqual(params2.ecc, 0.0003359123544722694, places=2)
        self.assertAlmostEqual(params2.w, 90.13110238025799, places=2)
        self.assertAlmostEqual(params2.u[0], 0.39998852439193955, places=2)

        self.assertTrue(callable(baseline_model2))
        print("fitreport2:", fit_report2)
        fit_report2_expected = """Initial batman TransitParams:
{'a': 17.408156570943518,
 'ecc': 0,
 'fp': None,
 'inc': 90,
 'limb_dark': 'linear',
 'per': 3.212983,
 'rp': 0.13914247093111606,
 't0': 2459267.6892912616,
 't_secondary': None,
 'u': [0.4],
 'w': 90}

Starting fit with airmass detrending...
   Iteration     Total nfev        Cost      Cost reduction    Step norm     Optimality   
       0              1         3.0358e+02                                    3.05e+02    
       1              2         1.0790e-03      3.04e+02       2.66e+00       1.54e-02    
       2              8         1.0790e-03      0.00e+00       0.00e+00       1.54e-02    
`xtol` termination condition is satisfied.
Function evaluations 8, initial cost 3.0358e+02, final cost 1.0790e-03, first-order optimality 1.54e-02.

Fitted parameters and errors: [a, t0, inc, ecc, w, linear_limb_darkening_coeff, m_airmass, b_airmass]: 
[ 1.74140070e+01  2.45926769e+06  9.00000000e+01  3.35916437e-04
  9.01311039e+01  3.99988525e-01 -1.57132350e+00  2.59178112e+00]
[1.55132020e+05 7.39680996e-01 3.14043277e+06 8.95985880e+03
 2.30331456e+05 3.37011090e+01 2.24393600e-01 2.27032122e-01]
Covariance matrix: 
[[ 2.40659438e+10 -9.62247930e+04  1.23838807e+11 -1.38995950e+09
   3.57234706e+10  4.63821153e+06  2.71098315e+03 -2.74107716e+03]
 [-9.62247930e+04  5.47127976e-01 -8.37300280e+05  5.56281650e+03
  -1.44808997e+05 -1.29735005e+01 -6.18539391e-03  6.25442064e-03]
 [ 1.23838807e+11 -8.37300280e+05  9.86231796e+12 -7.16362747e+09
   1.88190939e+11  1.41921690e+07  1.74979985e+04 -1.76921925e+04]
 [-1.38995950e+09  5.56281650e+03 -7.16362747e+09  8.02790696e+07
  -2.06332031e+09 -2.67691164e+05 -1.56342617e+02  1.58078146e+02]
 [ 3.57234706e+10 -1.44808997e+05  1.88190939e+11 -2.06332031e+09
   5.30525796e+10  6.81138997e+06  3.93397849e+03 -3.97765055e+03]
 [ 4.63821153e+06 -1.29735005e+01  1.41921690e+07 -2.67691164e+05
   6.81138997e+06  1.13576475e+03  9.81584606e-01 -9.92474456e-01]
 [ 2.71098315e+03 -6.18539391e-03  1.74979985e+04 -1.56342617e+02
   3.93397849e+03  9.81584606e-01  5.03524879e-02 -5.09444953e-02]
 [-2.74107716e+03  6.25442064e-03 -1.76921925e+04  1.58078146e+02
  -3.97765055e+03 -9.92474456e-01 -5.09444953e-02  5.15435845e-02]]

Final batman TransitParams:
{'a': 17.414006978565727,
 'ecc': 0.00033591643722653505,
 'fp': None,
 'inc': 89.99999999099812,
 'limb_dark': 'linear',
 'per': 3.212983,
 'rp': 0.13914247093111606,
 't0': 2459267.688973648,
 't_secondary': None,
 'u': [0.3999885246775466],
 'w': 90.13110393713954}
"""
        self.assertEqual(fit_report2, fit_report2_expected, "Fit report 2 is wrong")
