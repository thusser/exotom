import pprint
import sys
from collections import namedtuple
from contextlib import contextmanager
from io import StringIO
from typing import Union

import batman
import pandas as pd
import numpy as np
from astropy.coordinates import EarthLocation, AltAz, SkyCoord
from astropy.time import Time
from scipy import optimize
from scipy.interpolate import interpolate
from tom_targets.models import TargetExtra

from exotom.models import Transit


@contextmanager
def write_stdout_to_stringbfuffer() -> StringIO:
    string_buffer_stdout = StringIO()
    old_stdout = sys.stdout

    try:
        sys.stdout = string_buffer_stdout
        yield string_buffer_stdout
    finally:
        sys.stdout = old_stdout


FitResult = namedtuple(
    "FitResult",
    ["params", "fitted_model", "baseline_model", "chi_squared", "fit_report"],
)


class TessTransitFit:
    def __init__(
        self,
        light_curve_df: pd.DataFrame,
        transit: Transit,
        target_extras: [TargetExtra],
        earth_location: EarthLocation = None,
    ):
        self.light_curve_df = light_curve_df
        self.transit = transit
        self.target_extras: [TargetExtra] = target_extras
        self.earth_location = earth_location

        self.params: batman.TransitParams = self.get_transit_params_object()
        self.constant_factor = 1
        self.m_airmass = -1
        self.b_airmass = 0

    def make_simplest_fit_and_report(self, light_curve_df: pd.DataFrame = None):

        with write_stdout_to_stringbfuffer() as string_buffer_stdout:
            if self.earth_location is not None:
                # with airmass detrending
                (
                    params,
                    fitted_model,
                    baseline_model,
                    chi_squared,
                ) = self.make_simplest_fit_with_airmass_detrending(light_curve_df)
            else:
                # no airmass detrending
                (
                    params,
                    fitted_model,
                    baseline_model,
                    chi_squared,
                ) = self.make_simplest_fit_no_airmass_detrending(light_curve_df)

        fit_report = string_buffer_stdout.getvalue()
        print(fit_report)

        return FitResult(params, fitted_model, baseline_model, chi_squared, fit_report)

    def make_simplest_fit_no_airmass_detrending(
        self, light_curve_df: pd.DataFrame = None
    ):
        if light_curve_df is not None:
            self.light_curve_df = light_curve_df

        fit_a_and_t0_func = (
            self.get_a_t0_and_limb_dark_coeff_fit_function_no_airmass_detrending(
                self.params
            )
        )

        ts, ys = self.get_fit_data()

        p0 = [
            self.params.a,
            self.params.t0,
            self.params.inc,
            self.params.ecc,
            self.params.w,
            self.params.u[0],
            self.constant_factor,
        ]
        bounds = [
            [0, self.params.t0 - self.params.per / 2, 0, 0, -360, 0, -np.inf],
            [np.inf, self.params.t0 + self.params.per / 2, 90, 1, 360, np.inf, np.inf],
        ]

        print(f"Initial batman TransitParams:")
        pprint.pprint(self.params.__dict__)
        print("\nStarting fit without airmass detrending...")

        popt, pcov = optimize.curve_fit(
            fit_a_and_t0_func,
            ts,
            ys,
            p0=p0,
            bounds=bounds,
            method="trf",
            verbose=2,
            xtol=None,
        )
        perr = np.sqrt(np.diag(pcov))
        print(
            f"\nFitted parameters and errors: [a, t0, inc, ecc, w, linear_limb_darkening_coeff, constant_factor]: \n{popt}\n{perr}"
        )
        print(f"Covariance matrix: \n{pcov}")

        self.params.a = popt[0]
        self.params.t0 = popt[1]
        self.params.inc = popt[2]
        self.params.ecc = popt[3]
        self.params.w = popt[4]
        self.params.u = [popt[5]]
        self.constant_factor = popt[6]

        print(f"\nFinal batman TransitParams:")
        pprint.pprint(self.params.__dict__)

        def fitted_model(times):
            return fit_a_and_t0_func(times, *popt)

        baseline_model = None

        chi_squared = np.var(ys - fitted_model(ts))

        return self.params, fitted_model, baseline_model, chi_squared

    def get_a_t0_and_limb_dark_coeff_fit_function_no_airmass_detrending(self, params):
        def fit_a_and_t0_func(
            ts, a, t0, inc, ecc, w, linear_limb_darkening_coeff, constant_factor
        ):
            params.a = a
            params.t0 = t0
            params.inc = inc
            params.ecc = ecc
            params.w = w
            params.u = [linear_limb_darkening_coeff]
            model = batman.TransitModel(params, ts)
            flux = model.light_curve(params) * constant_factor
            return flux

        return fit_a_and_t0_func

    def make_simplest_fit_with_airmass_detrending(
        self, light_curve_df: pd.DataFrame = None
    ):
        if light_curve_df is not None:
            self.light_curve_df = light_curve_df

        ts, ys = self.get_fit_data()

        fit_a_and_t0_func = (
            self.get_a_t0_and_limb_dark_coeff_fit_function_with_airmass_detrending(
                self.params, ts
            )
        )

        p0 = [
            self.params.a,
            self.params.t0,
            self.params.inc,
            self.params.ecc,
            self.params.w,
            self.params.u[0],
            self.m_airmass,
            self.b_airmass,
        ]
        bounds = [
            [0, self.params.t0 - self.params.per / 2, 0, 0, -360, 0, -np.inf, -np.inf],
            [
                np.inf,
                self.params.t0 + self.params.per / 2,
                90,
                1,
                360,
                np.inf,
                np.inf,
                np.inf,
            ],
        ]

        print(f"Initial batman TransitParams:")
        pprint.pprint(self.params.__dict__)
        print("\nStarting fit with airmass detrending...")

        popt, pcov = optimize.curve_fit(
            fit_a_and_t0_func,
            ts,
            ys,
            p0=p0,
            bounds=bounds,
            method="trf",
            verbose=2,
        )
        perr = np.sqrt(np.diag(pcov))
        print(
            f"\nFitted parameters and errors: [a, t0, inc, ecc, w, linear_limb_darkening_coeff, m_airmass, b_airmass]: \n{popt}\n{perr}"
        )
        print(f"Covariance matrix: \n{pcov}")

        self.params.a = popt[0]
        self.params.t0 = popt[1]
        self.params.inc = popt[2]
        self.params.ecc = popt[3]
        self.params.w = popt[4]
        self.params.u = [popt[5]]
        self.m_airmass = popt[6]
        self.b_airmass = popt[7]

        print(f"\nFinal batman TransitParams:")
        pprint.pprint(self.params.__dict__)

        def fitted_model(times):
            return fit_a_and_t0_func(times, *popt)

        def baseline_model(times):
            airmass_function = self.get_airmass_function(ts)
            return self.m_airmass * airmass_function(times) + self.b_airmass

        chi_squared = np.var(ys - fitted_model(ts))

        return self.params, fitted_model, baseline_model, chi_squared

    def get_fit_data(self):
        ts = np.array(self.light_curve_df["time"])
        ys = self.get_target_relative_lightcurve()
        return ts, ys

    def get_target_relative_lightcurve(self):
        if "target_rel" in self.light_curve_df.columns:
            return np.array(
                self.light_curve_df["target_rel"]
                / self.light_curve_df["target_rel"].mean()
            )

        ref_star_columns = self.get_ref_star_columns(self.light_curve_df.columns)
        target_rel = self.light_curve_df["target"] / self.light_curve_df[
            ref_star_columns
        ].sum(axis="columns")
        target_rel_normed = target_rel / target_rel.mean()

        return np.array(target_rel_normed)

    def get_ref_star_columns(self, columns):
        ref_star_columns = list(
            filter(
                lambda col: str(col).isdigit() or type(col) == int,
                columns,
            )
        )
        return ref_star_columns

    def get_a_t0_and_limb_dark_coeff_fit_function_with_airmass_detrending(
        self, params, times
    ):
        def fit_a_and_t0_func(
            ts, a, t0, inc, ecc, w, linear_limb_darkening_coeff, m_airmass, b_airmass
        ):
            params.a = a
            params.t0 = t0
            params.inc = inc
            params.ecc = ecc
            params.w = w
            params.u = [linear_limb_darkening_coeff]
            model = batman.TransitModel(params, ts)
            airmass_function = self.get_airmass_function(times)
            flux = model.light_curve(params) * (
                m_airmass * airmass_function(ts) + b_airmass
            )
            return flux

        return fit_a_and_t0_func

    def get_transit_params_object(self):
        params: batman.TransitParams = batman.TransitParams()
        params.t0 = Time(self.transit.mid).jd
        params.per = self.get_target_extra(key="Period (days)").float_value
        # convert to solar radii
        PLANET_RADIUS_DEFAULT = 2.0
        planet_radius_in_earth_radii = self.get_target_extra(
            key="Planet Radius (R_Earth)"
        ).float_value
        planet_radius_in_solar_radii = (
            planet_radius_in_earth_radii
            if planet_radius_in_earth_radii
            else PLANET_RADIUS_DEFAULT
        ) / 109.2
        DEFAULT_STELLAR_RADIUS = 2.0
        stellar_radius = self.get_target_extra(key="Stellar Radius (R_Sun)").float_value
        stellar_radius_in_solar_radii = (
            stellar_radius if stellar_radius else DEFAULT_STELLAR_RADIUS
        )
        planet_radius_in_stellar_radii = (
            planet_radius_in_solar_radii / stellar_radius_in_solar_radii
        )
        params.rp = planet_radius_in_stellar_radii

        orbit_radius_in_stellar_radii = self.estimate_orbit_radius()
        params.a = orbit_radius_in_stellar_radii

        params.inc = 90
        params.ecc = 0
        params.w = 90
        params.limb_dark = "linear"
        params.u = [0.4]

        return params

    def estimate_orbit_radius(self):
        try:
            # constants
            grav_constant = 6.7e-11
            abs_mag_sun = 4.83
            mass_sun = 2e30
            radius_sun_in_m = 7e8

            # system parameters
            apparent_magnitude = self.get_target_extra(key="Mag (TESS)").float_value
            distance = self.get_target_extra(key="Stellar Distance (pc)").float_value
            period_in_s = (
                self.get_target_extra(key="Period (days)").float_value * 24 * 60 * 60
            )
            DEFAULT_STELLAR_RADIUS = 0.5
            stellar_radius = self.get_target_extra(
                key="Stellar Radius (R_Sun)"
            ).float_value
            radius_star_in_sun_radii = (
                stellar_radius if stellar_radius else DEFAULT_STELLAR_RADIUS
            )

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
        except:
            orbit_radius_in_stellar_radii = 20

        return orbit_radius_in_stellar_radii

    def get_airmass_function(self, times: np.array):
        astropy_times = Time(times, format="jd")
        airmass = self.get_airmass(astropy_times)
        airmass_func = interpolate.interp1d(times, airmass, kind="linear")
        return airmass_func

    def get_airmass(self, times):
        frame = AltAz(obstime=times, location=self.earth_location)
        target_altaz = SkyCoord(
            self.transit.target.ra, self.transit.target.dec, unit="deg"
        ).transform_to(frame)
        airmass = target_altaz.secz
        return airmass

    def get_target_extra(self, key):
        for target_extra in self.target_extras:
            if target_extra.key == key:
                return target_extra
