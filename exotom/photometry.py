import numpy as np
from astropy.coordinates import SkyCoord, AltAz, EarthLocation
import astropy.units as u

import matplotlib.pyplot as plt
import pandas as pd
import copy
from typing import Union

from astropy.time import Time
from scipy.interpolate import interpolate
from scipy.optimize import curve_fit

MAX_SEPARATION_TO_CATALOG_IN_DEG = 5 / 3600


class TransitLightCurveExtractor:
    def __init__(
        self,
        image_catalogs: [],
        target_coord: SkyCoord,
        one_image_for_plot: np.ndarray = None,
        max_allowed_pixel_value: float = 5e4,
        max_allowed_source_ellipticity: float = 0.4,
        min_allowed_source_fwhm: float = 2.5,
    ):

        self.target_coord = target_coord
        self.lce = LightCurvesExtractor(
            image_catalogs,
            target_coord,
            one_image_for_plot,
            max_allowed_pixel_value,
            max_allowed_source_ellipticity,
            min_allowed_source_fwhm,
        )
        self.light_curves_df: Union[pd.DataFrame, None] = None
        # self.filtered_light_curves_with_target_rel_light_curve_df: Union[pd.DataFrame, None] = None

    def get_all_light_curves_dataframe(
        self,
        flux_column_name: str = "flux",
        use_only_n_brightest_ref_sources: int = None,
        force_recalculate: bool = False,
    ):
        if self.light_curves_df is None or force_recalculate:
            self.light_curves_df = self.lce.get_target_and_ref_stars_light_curves_df(
                flux_column_name, use_only_n_brightest_ref_sources
            )
        return self.light_curves_df

    def get_best_relative_transit_light_curve_dataframe(self) -> pd.DataFrame:
        """Filter out ref stars that are noisy from light_curves_df.
        :returns pd.DataFrame that contains the lightcurves of good reference stars and target
        and relative light curve of target
        """
        light_curves_df = copy.deepcopy(self.get_all_light_curves_dataframe())

        filtered_light_curves = self.filter_noisy_light_curves(light_curves_df)

        filtered_light_curves_with_target_rel_light_curve_df = filtered_light_curves
        filtered_light_curves_with_target_rel_light_curve_df[
            "target_rel"
        ] = filtered_light_curves["target"] / filtered_light_curves[
            filter(lambda col: col != "target", filtered_light_curves.columns)
        ].sum(
            axis="columns"
        )

        print(
            f"Columns of final best relative transit light curve dataframe: "
            f"{list(filtered_light_curves_with_target_rel_light_curve_df.columns)}"
        )
        return filtered_light_curves_with_target_rel_light_curve_df

    def filter_noisy_light_curves(
        self, light_curves_df, max_detrended_normed_std: float = 0.01
    ):
        """Filters out light curves of ref sources that are noisy. For that it detrends the normed light curves
        with a linear function of the airmass. Ref sources with detrended normed light curves with standard
        deviation > max_detrended_normed_std are removed.

        :param cmp_light_curves:
        :param max_detrended_normed_std:
        :return: filtered light curves
        """
        # times = Time(light_curves_df.index, format="jd")
        # times, airmass = self.get_airmass(times)
        # airmass_func = interpolate.interp1d(times, airmass, kind="linear")

        ref_star_columns = [
            col for col in light_curves_df.columns if col not in ["target"]
        ]
        target_lc_normed = light_curves_df["target"] / light_curves_df["target"].mean()
        relative_light_curves_stds = {}
        for col in ref_star_columns:
            cmp_lc = light_curves_df[col]
            cmp_lc_normed = cmp_lc / cmp_lc.mean()
            # print(cmp_lc.mean(), cmp_lc, cmp_lc_normed, )
            # def fit_func(time, m, b):
            #     return m * airmass_func(time) + b
            #
            # popt, pcov = curve_fit(fit_func, times, cmp_lc_normed, p0=[-0.1, 1])

            cmp_rel_lc = target_lc_normed / cmp_lc_normed

            rel_lc_std = cmp_rel_lc.std()

            relative_light_curves_stds[col] = rel_lc_std

        # kappa sigma clip on the standard deviation of relative lightcurves
        kappa = 0.5
        avg = np.mean(list(relative_light_curves_stds.values()))
        std = np.std(list(relative_light_curves_stds.values()))

        remove_columns = [
            col
            for col, col_std in relative_light_curves_stds.items()
            if col_std > avg + kappa * std
        ]
        print(
            f"Removing ref stars {remove_columns} because relative_light_curves_stds > avg + {kappa} * sigma."
        )
        light_curves_df.drop(columns=remove_columns, inplace=True)
        return light_curves_df

    def get_airmass(self, times):
        goe = EarthLocation(lat=51.561 * u.deg, lon=9.944 * u.deg, height=390 * u.m)
        frame = AltAz(obstime=times, location=goe)
        target_altaz = self.target_coord.transform_to(frame)
        airmass = target_altaz.secz
        return times.plot_date, airmass


class LightCurvesExtractor:
    """ Extracts all potential ref star and the target light curves from catalogs of transit images."""

    def __init__(
        self,
        image_catalogs: [],
        target_coord: SkyCoord,
        one_image_for_plot: np.ndarray = None,
        max_allowed_pixel_value: float = 5e4,
        max_allowed_source_ellipticity: float = 0.4,
        min_allowed_source_fwhm: float = 2.5,
    ):
        self.full_image_catalogs: [pd.DataFrame] = self.filter_out_incomplete_catalogs(
            image_catalogs
        )
        self.target_coord: SkyCoord = target_coord

        self.one_image_for_plot = one_image_for_plot

        # filters sources by following criteria
        self.max_allowed_pixel_value = max_allowed_pixel_value
        self.max_allowed_source_ellipticity = max_allowed_source_ellipticity
        self.min_allowed_source_fwhm = min_allowed_source_fwhm

        self.ref_catalog: Union[pd.DataFrame, None] = None
        self.target_id: Union[int, None] = None
        self.matched_image_catalogs_with_target: Union[list, None] = None

    def get_target_and_ref_stars_light_curves_df(
        self,
        flux_column_name: str = "flux",
        use_only_n_brightest_ref_sources: int = None,
    ) -> pd.DataFrame:

        self.build_and_match_ref_source_catalog(
            use_only_n_brightest_ref_sources, flux_column_name
        )

        target_light_curve = self.extract_light_curves(
            self.matched_image_catalogs_with_target, [self.target_id], flux_column_name
        )[self.target_id]

        # remove target form comparison stars
        cmp_ids = list(self.ref_catalog["id"])
        cmp_ids.remove(self.target_id)
        # get comparison stars light curves
        cmp_light_curves = self.extract_light_curves(
            self.matched_image_catalogs_with_target,
            cmp_ids,
            flux_column_name,
            verbose=True,
        )

        light_curve_df = cmp_light_curves
        light_curve_df["target"] = target_light_curve
        return light_curve_df

    def build_and_match_ref_source_catalog(
        self,
        use_only_n_brightest_ref_sources,
        flux_column_name: str,
        force_rebuild=False,
    ):
        if (
            self.ref_catalog is not None
            and self.target_id is not None
            and self.matched_image_catalogs_with_target is not None
        ) and not force_rebuild:
            # ref source catalog already built
            print("Not matching, since matched catalog was found.")
            return

        ref_catalog, ref_catalog_coords = self.get_ref_catalog_from_catalog(
            self.full_image_catalogs[0]
        )
        self.target_id = self.find_target_id(ref_catalog_coords)
        print(f"Starting with {len(ref_catalog)} reference sources.")

        matched_image_catalogs_with_target = self.match_image_catalogs_to_ref_catalog(
            self.full_image_catalogs, ref_catalog_coords
        )
        matched_image_catalogs_with_target = (
            self.remove_frames_where_target_was_not_matched(
                matched_image_catalogs_with_target, self.target_id
            )
        )
        ref_catalog = self.keep_only_n_brightest_ref_sources_and_target(
            ref_catalog,
            use_only_n_brightest=use_only_n_brightest_ref_sources,
        )
        print("Enforcing that each ref source is exactly once in each frame...")

        self.plot_ref_sources_on_image(ref_catalog)
        (
            ref_catalog,
            matched_image_catalogs_with_target,
        ) = self.enforce_each_ref_source_exactly_once_per_image_and_valid_flux(
            matched_image_catalogs_with_target, ref_catalog, flux_column_name
        )
        self.plot_ref_sources_on_image(ref_catalog)

        self.ref_catalog = ref_catalog
        self.matched_image_catalogs_with_target = matched_image_catalogs_with_target

    def get_ref_catalog_from_catalog(self, catalog: pd.DataFrame):
        ref_catalog: pd.DataFrame = copy.deepcopy(catalog)

        ref_catalog = ref_catalog[ref_catalog["peak"] < self.max_allowed_pixel_value]
        ref_catalog = ref_catalog[
            ref_catalog["ellipticity"] < self.max_allowed_source_ellipticity
        ]
        ref_catalog = ref_catalog[ref_catalog["fwhm"] > self.min_allowed_source_fwhm]
        # ref_catalog = ref_catalog[ref_catalog["flux"] > 8e2]
        ref_catalog.index = list(range(len(ref_catalog)))
        ref_catalog["id"] = list(range(len(ref_catalog)))

        ref_catalog_coords = SkyCoord(
            ref_catalog["ra"] * u.deg, ref_catalog["dec"] * u.deg, frame="icrs"
        )
        return ref_catalog, ref_catalog_coords

    def find_target_id(self, ref_catalog_coords):
        target_id, sep, _ = self.target_coord.match_to_catalog_sky(ref_catalog_coords)
        target_id = int(target_id)  # to convert from array to int
        if sep.degree > MAX_SEPARATION_TO_CATALOG_IN_DEG:
            raise Exception(
                f"Best source match for photometry target is too far away ({sep.degree}°)."
            )
        return target_id

    def match_image_catalogs_to_ref_catalog(self, image_catalogs, ref_catalog_coords):
        """add reference source ids to image_catalog in place"""
        for i_cat, cat in enumerate(image_catalogs):
            if i_cat % 100 == 0:
                print("Matching frame %d/%d ..." % (i_cat, len(image_catalogs) - 1))

            cat_coords = SkyCoord(cat["ra"] * u.deg, cat["dec"] * u.deg, frame="icrs")

            ids, separation_angles, _ = cat_coords.match_to_catalog_sky(
                ref_catalog_coords
            )
            ids[separation_angles.degree > MAX_SEPARATION_TO_CATALOG_IN_DEG] = -1
            cat["id"] = ids.astype(int)

        return image_catalogs

    def remove_frames_where_target_was_not_matched(self, image_catalogs, target_id):
        remove_ids = []
        for i_cat, cat in enumerate(image_catalogs):
            counts = cat["id"].value_counts()
            if (not target_id in counts.index) or counts[target_id] != 1:
                remove_ids.append(i_cat)
        print(
            f"Removing {len(remove_ids)} frames because the target star was not matched exactly once."
        )
        for remove_id in reversed(remove_ids):
            image_catalogs.pop(remove_id)

        return image_catalogs

    def keep_only_n_brightest_ref_sources_and_target(
        self, ref_catalog, use_only_n_brightest: int = None
    ):
        if use_only_n_brightest:
            ref_catalog = ref_catalog.sort_values(by=["flux"], ascending=[False])
            filtered_ref_catalog = ref_catalog.iloc[
                : min(use_only_n_brightest, len(ref_catalog.index))
            ]
            if self.target_id not in filtered_ref_catalog.id:
                filtered_ref_catalog.append(
                    ref_catalog[ref_catalog.id == self.target_id]
                )
            return filtered_ref_catalog
        return ref_catalog

    def enforce_each_ref_source_exactly_once_per_image_and_valid_flux(
        self, image_catalogs: [pd.DataFrame], ref_catalog, flux_column_name
    ):
        """Enforce that all ref_sources have been identified *exactly once* in each frame.
        if a ref_source is not *exactly once* in a frame or the flux_column_value is nan, remove that source.
        """
        times = [cat.iloc[0]["time"] for cat in image_catalogs]
        ids = ref_catalog.id
        source_flux_values = pd.DataFrame(index=times, columns=ids)

        for i_cat, catalog in enumerate(image_catalogs):
            if i_cat % 100 == 0:
                print("Checking frame %d/%d ..." % (i_cat, len(image_catalogs) - 1))

            time = catalog.iloc[0].time
            for id in ids:
                try:
                    flux_value_series = catalog[catalog.id == id][flux_column_name]
                    if len(flux_value_series.index) != 1:
                        raise Exception("ref star not found exactly once")
                    flux_value = flux_value_series.iloc[0]
                except Exception as e:
                    flux_value = np.nan

                source_flux_values.loc[time, id] = flux_value

        any_nan_per_ref_source_series = source_flux_values.isna().any(axis="index")
        remove_ref_sources_ids = any_nan_per_ref_source_series[
            any_nan_per_ref_source_series == True
        ].index

        print(
            f"Removing these ref_sources b/c they are not exactly once in each image or have '{flux_column_name}' value nan: {remove_ref_sources_ids}"
        )
        for remove_sources_id in remove_ref_sources_ids:
            ref_catalog.drop(labels=remove_sources_id, axis="index", inplace=True)

        return ref_catalog, image_catalogs

    def extract_light_curves(
        self, catalogs, ids_to_extract, flux_column_name, verbose=False
    ) -> pd.DataFrame:
        times = [cat.iloc[0]["time"] for cat in catalogs]
        light_curves = pd.DataFrame(index=times, columns=ids_to_extract)

        for id in ids_to_extract:
            column = [
                cat[cat["id"] == id].iloc[0][flux_column_name] for cat in catalogs
            ]
            light_curves[id] = column

        return light_curves

    def plot_ref_sources_on_image(self, ref_catalog):
        if self.one_image_for_plot is None:
            return
        image = self.one_image_for_plot
        mean = np.mean(image)
        std = np.std(image)
        plt.figure()
        plt.imshow(image, vmin=mean - std, vmax=mean + std)
        for ref in ref_catalog.itertuples():
            # print(ref.x, ref.y)
            plt.errorbar(
                ref.x,
                ref.y,
                xerr=ref.fwhm / 2,
                yerr=ref.fwhm / 2,
                marker="x",
                markersize=10,
                linewidth=3,
                color="black",
            )
        plt.show()

    def filter_out_incomplete_catalogs(self, image_catalogs):

        required_columns = ["ra", "dec", "time", "flux"]
        filtered_catalogs = []
        for cat in image_catalogs:
            for required_column in required_columns:
                if required_column not in cat.columns:
                    break
            else:  # nobreak
                filtered_catalogs.append(cat)
        return filtered_catalogs
