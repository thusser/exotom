import pprint
import sys
from collections import namedtuple
from io import StringIO

import batman
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from astropy.time import Time
from scipy import optimize

from exotom.models import Transit

FitResult = namedtuple("FitResult", ["params", "constant_offset", "fit_report"])


class TessTransitFit:
    def __init__(self, light_curve_df: pd.DataFrame, transit: Transit):
        self.light_curve_df = light_curve_df
        self.transit = transit

    def make_simplest_fit(self):
        params: batman.TransitParams = self.get_transit_params_object()

        fit_a_and_per_func = self.get_a_and_per_fit_function(params)

        ts = np.array(self.light_curve_df["time"])
        ys = np.array(
            self.light_curve_df["target_rel"] / self.light_curve_df["target_rel"].mean()
        )
        constant_offset = 0
        p0 = [params.a, params.per, params.inc, params.ecc, params.w, constant_offset]
        bounds = [[0, 0, 0, 0, -360, -np.inf], [np.inf, np.inf, 90, 1, 360, np.inf]]

        old_std = sys.stdout
        string_buffer_stdout = StringIO()
        sys.stdout = string_buffer_stdout

        print(f"Initial batman TransitParams:")
        pprint.pprint(params.__dict__)

        print("\nStarting fit...")
        popt, pcov = optimize.curve_fit(
            fit_a_and_per_func, ts, ys, p0=p0, bounds=bounds, method="trf", verbose=2
        )

        print(f"\nFitted parameters: [a, per, inc, ecc, w, constant_offset]: \n{popt}")
        print(f"Covariance matrix: \n{pcov}")

        # plt.ion()
        # plt.figure()
        # plt.title(f"Relative Normalized Light")
        # plt.scatter(
        #     self.light_curve_df['time'],
        #     self.light_curve_df["target_rel"] / self.light_curve_df["target_rel"].mean(),
        #     marker="x",
        #     linewidth=1,
        # )
        # plt.plot(ts, fit_a_and_per_func(ts, *p0), color='orange')
        # plt.plot(ts, fit_a_and_per_func(ts, *popt), color='red')
        # plt.pause(100)

        params.a = popt[0]
        params.per = popt[1]
        params.inc = popt[2]
        params.ecc = popt[3]
        params.w = popt[4]
        constant_offset = popt[5]
        print(f"\nFinal batman TransitParams:")
        pprint.pprint(params.__dict__)

        sys.stdout = old_std
        fit_report = string_buffer_stdout.getvalue()
        print(fit_report)

        return FitResult(params, constant_offset, fit_report)

    def get_a_and_per_fit_function(self, params):
        def fit_a_and_per_func(ts, a, per, inc, ecc, w, c):
            params.a = a
            params.per = per
            params.inc = inc
            params.ecc = ecc
            params.w = w
            model = batman.TransitModel(params, ts)
            flux = model.light_curve(params) + c
            return flux

        return fit_a_and_per_func

    def plot_default_parameters(self):

        params = self.get_transit_params_object()
        # ts = np.array(self.light_curve_df.index, dtype='float')
        start = self.light_curve_df["time"][0]
        end = self.light_curve_df["time"][len(self.light_curve_df.index) - 1]
        print(start, end)
        ts = np.linspace(start, end, 10000)
        model1 = batman.TransitModel(params, ts)
        flux1 = model1.light_curve(params)

        params2 = params
        params2.a = params.a * 2
        model2 = batman.TransitModel(params, ts)
        flux2 = model2.light_curve(params)

        plt.ion()
        plt.figure()
        plt.title(f"Relative Normalized")
        plt.scatter(
            self.light_curve_df["Unnamed: 0"],
            self.light_curve_df["target_rel"]
            / self.light_curve_df["target_rel"].mean(),
            marker="x",
            linewidth=1,
        )
        plt.plot(ts, flux1, color="orange")
        plt.plot(ts, flux2, color="red")
        plt.pause(100)
        # plt.savefig(tmpfile.name, format="jpg")

    def get_transit_params_object(self):

        target_extras = self.transit.target.targetextra_set

        params: batman.TransitParams = batman.TransitParams()
        params.t0 = Time(self.transit.mid).jd
        params.per = target_extras.get(key="Period (days)").float_value
        # convert to solar radii
        planet_radius_in_solar_radii = (
            target_extras.get(key="Planet Radius (R_Earth)").float_value / 109.2
        )
        planet_radius_in_stellar_radii = (
            planet_radius_in_solar_radii
            / target_extras.get(key="Stellar Radius (R_Sun)").float_value
        )
        params.rp = planet_radius_in_stellar_radii

        orbit_radius_in_stellar_radii = self.estimate_orbit_radius(target_extras)
        params.a = orbit_radius_in_stellar_radii

        params.inc = 90
        params.ecc = 0
        params.w = 90
        params.limb_dark = "uniform"
        params.u = []

        return params

    def estimate_orbit_radius(self, target_extras):
        # constants
        grav_constant = 6.7e-11
        abs_mag_sun = 4.83
        mass_sun = 2e30
        radius_sun_in_m = 7e8

        # system parameters
        apparent_magnitude = target_extras.get(key="Mag (TESS)").float_value
        distance = target_extras.get(key="Stellar Distance (pc)").float_value
        period_in_s = target_extras.get(key="Period (days)").float_value * 24 * 60 * 60
        radius_star_in_sun_radii = target_extras.get(
            key="Stellar Radius (R_Sun)"
        ).float_value

        # calculation
        absolute_magnitude = apparent_magnitude - 5 * (np.log10(distance) - 1)
        L_divided_by_L_sun = np.power(10, 0.4 * (abs_mag_sun - absolute_magnitude))
        # mass-luminosity relation which only holds for main sequence stars!
        mass = mass_sun * np.power(L_divided_by_L_sun, 0.25)
        # kepler 3
        orbit_radius = np.power(
            mass * grav_constant * period_in_s ** 2 / (4 * np.pi), 1 / 3
        )

        # convert to stellar radii
        orbit_radius_in_sun_radii = orbit_radius / radius_sun_in_m
        orbit_radius_in_stellar_radii = (
            orbit_radius_in_sun_radii / radius_star_in_sun_radii
        )

        return orbit_radius_in_stellar_radii
