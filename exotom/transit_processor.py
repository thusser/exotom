import glob, os, tempfile, time

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from astropy.coordinates import SkyCoord, EarthLocation
import astropy.units as u
from astropy.io import fits
from astropy.table import Table
from astropy.time import Time

from django.core.files import File
from django.core.files.base import ContentFile
from tom_dataproducts.models import DataProductGroup, DataProduct
from tom_targets.models import Target, TargetExtra

from exotom.models import Transit
from exotom.photometry import TransitLightCurveExtractor, LightCurvesExtractor
from exotom.tess_transit_fit import FitResult
from local_settings import COORDS_BY_INSTRUMENT


class TransitProcessor:
    def __init__(self, all_lightcurves_dataproduct: DataProduct):

        self.all_lightcurves_dataproduct = all_lightcurves_dataproduct
        self.check_all_lightcurves_dataproduct_validity()

        self.observation_record = self.all_lightcurves_dataproduct.observation_record
        self.target: Target = self.all_lightcurves_dataproduct.target
        self.target_coord = SkyCoord(self.target.ra * u.deg, self.target.dec * u.deg)
        self.earth_location = self.get_earth_location()

        # this try-except is needed because in the beginning "transit_id" was not written to the parameters dict
        try:
            self.transit: Transit = Transit.objects.get(
                target__id=self.observation_record.parameters["target_id"],
                number=self.observation_record.parameters["transit"],
            )
        except (KeyError):
            try:
                self.transit: Transit = Transit.objects.get(
                    id=self.observation_record.parameters["transit_id"]
                )
            except (KeyError, Transit.DoesNotExist):
                self.transit = None

        dp_filename = os.path.splitext(
            os.path.basename(self.all_lightcurves_dataproduct.data.path)
        )[0]
        # remove '_all' and everything after it
        _all_index = dp_filename.index("_all")
        self.light_curve_name = dp_filename[:_all_index]
        print(f"Using light curve name {self.light_curve_name}")

        # objects that get created later
        self.best_fit_result = None
        self.best_light_curves_df = None
        self.best_light_curves_dp = None

    def check_all_lightcurves_dataproduct_validity(self):
        if (
            self.all_lightcurves_dataproduct.data_product_type
            != "transit_all_light_curves"
        ):
            raise ValueError(
                f"all_lightcurves_dataproduct doesnt have type "
                f"transit_all_light_curves but {self.all_lightcurves_dataproduct.data_product_type}."
            )

        try:
            path = self.all_lightcurves_dataproduct.data.path
            if path is None or path == "":
                raise Exception()
        except:
            raise ValueError(
                f"all_lightcurves_dataproduct ({self.all_lightcurves_dataproduct}) does not have well defined DataProduct.data.path"
            )

    def get_earth_location(self):
        try:
            instrument = self.observation_record.parameters["instrument_type"]
        except KeyError:
            # if instrument_type not in parameters, use goettingen camera
            instrument = "0M5 SBIG6303E"
        lat = COORDS_BY_INSTRUMENT[instrument]["latitude"]
        lon = COORDS_BY_INSTRUMENT[instrument]["longitude"]
        height = COORDS_BY_INSTRUMENT[instrument]["elevation"]
        earth_location = EarthLocation(
            lat=lat * u.deg, lon=lon * u.deg, height=height * u.m
        )
        return earth_location

    def process(self):
        """Processes the data products in the data group. Creates three DataProducts
        - one of type "transit_all_light_curves" which contains all potential reference star lightcurves that fulfill
            some basic quality criteria (columns are numbers 0, 1, 2...) and a column "target" for the target star flux.
        - one of type  "transit_best_light_curves" which contains a selection of reference stars which give the best
            target relativ light curve (in columns "target_rel").
        These dataproducts have an associated csv file.
        - one dataproduct which shows and image of the transit with associated jpg file.

        :raises ValueError if data_product_group contains no DataProducts or data_product_types
        other than "photometry_catalog"s.
        """

        print(
            f"Transit processing all lightcurves data product: {self.all_lightcurves_dataproduct}"
        )

        self.extract_and_save_lightcurves()

        self.create_best_light_curve_and_fit_image()

    def extract_and_save_lightcurves(self):

        all_light_curves_df = self.extract_all_lightcurves_df()

        best_fit_result: FitResult
        (
            best_light_curve_df,
            best_fit_result,
        ) = self.extract_best_lightcurves_and_fit(all_light_curves_df)

        self.best_fit_result = best_fit_result
        self.best_light_curves_df = best_light_curve_df

        self.save_lightcurves_and_fit_report_as_dataproducts(
            best_light_curve_df, best_fit_result
        )

    def extract_all_lightcurves_df(self):
        df = pd.read_csv(self.all_lightcurves_dataproduct.data.path)
        return df

    def extract_best_lightcurves_and_fit(self, all_light_curves_df):

        target_extras_list = (
            list(self.transit.target.targetextra_set.all()) if self.transit else None
        )
        transit_lc_extractor = TransitLightCurveExtractor(
            all_light_curves_df,
            self.target_coord,
            target_extras_list,
            self.transit,
            self.earth_location,
        )
        (
            best_light_curve_df,
            best_fit_result,
        ) = transit_lc_extractor.get_best_relative_transit_light_curve_dataframe()

        return best_light_curve_df, best_fit_result

    def save_lightcurves_and_fit_report_as_dataproducts(
        self, best_light_curve_df, best_fit_result
    ):
        self.best_light_curves_dp = self.save_dataframe_as_dataproduct_and_csv_file(
            best_light_curve_df,
            product_id=self.light_curve_name + "_best",
            data_product_type="transit_best_light_curves",
        )
        if self.best_fit_result is not None:
            self.save_fit_report_as_dataproduct_and_txt_file(
                best_fit_result.fit_report,
                product_id=self.light_curve_name + "_fit_report",
                data_product_type="transit_fit_report",
            )

    def save_dataframe_as_dataproduct_and_csv_file(
        self, df, product_id, data_product_type
    ) -> DataProduct:
        try:
            DataProduct.objects.get(product_id=product_id).delete()
        except:
            pass

        dp = DataProduct.objects.create(
            product_id=product_id,
            target=self.target,
            observation_record=self.observation_record,
            data_product_type=data_product_type,
        )
        dfile = ContentFile(df.to_csv())
        dp.data.save(
            product_id + ".csv",
            dfile,
        )
        dp.save()
        return dp

    def save_fit_report_as_dataproduct_and_txt_file(
        self, fit_report, product_id, data_product_type
    ) -> DataProduct:
        try:
            DataProduct.objects.get(product_id=product_id).delete()
        except:
            pass

        dp = DataProduct.objects.create(
            product_id=product_id,
            target=self.target,
            observation_record=self.observation_record,
            data_product_type=data_product_type,
        )
        dfile = ContentFile(fit_report)
        dp.data.save(
            product_id + ".txt",
            dfile,
        )
        dp.save()
        return dp

    def create_best_light_curve_and_fit_image(self):
        tmpfile = tempfile.NamedTemporaryFile()

        times = np.array(self.best_light_curves_df["time"])

        self.save_plot_of_transit_data_and_fit(times, tmpfile.name)

        if tmpfile:
            dp, _ = DataProduct.objects.get_or_create(
                product_id=f"{self.best_light_curves_dp.product_id}_jpeg",
                target=self.best_light_curves_dp.target,
                observation_record=self.best_light_curves_dp.observation_record,
                data_product_type="image_file",
            )
            outfile_name = os.path.basename(self.best_light_curves_dp.data.file.name)
            filename = os.path.splitext(outfile_name)[0] + ".jpg"
            with open(tmpfile.name, "rb") as f:
                dp.data.save(filename, File(f), save=True)
                dp.save()
            tmpfile.close()

    def save_plot_of_transit_data_and_fit(self, times, file_name):
        fig = plt.figure(figsize=(12, 9))
        baseline_function = None
        if self.best_fit_result is not None:
            fit_function = self.best_fit_result.fitted_model
            baseline_function = self.best_fit_result.baseline_model
            label = self.get_best_fit_params_legend_string()

            # plot line at observed mid transit
            plt.axvline(
                x=self.best_fit_result.params.t0,
                color="red",
                linestyle="dashed",
                zorder=10,
            )

            # plot airmass detrended data if baseline_function is given
            times_across_whole_transit = np.linspace(
                min(times[0], Time(self.transit.start_earliest()).jd),
                max(times[-1], Time(self.transit.end_latest()).jd),
                1000,
            )
            if baseline_function is not None:
                plt.plot(
                    times_across_whole_transit,
                    fit_function(times_across_whole_transit)
                    / baseline_function(times_across_whole_transit),
                    color="red",
                    label=label,
                )
            else:
                plt.plot(
                    times_across_whole_transit,
                    fit_function(times_across_whole_transit),
                    color="red",
                    label=label,
                )

            plt.legend()

        if baseline_function is not None:
            plt.scatter(
                times,
                (
                    self.best_light_curves_df["target_rel"]
                    / self.best_light_curves_df["target_rel"].mean()
                )
                / baseline_function(times),
                marker="x",
                linewidth=1,
                color="blue",
            )
        else:
            plt.scatter(
                times,
                self.best_light_curves_df["target_rel"]
                / self.best_light_curves_df["target_rel"].mean(),
                marker="x",
                linewidth=1,
                color="blue",
            )

        ### draw predicted values ###
        # plot horizontal line at predicted depth
        predicted_color = "green"
        try:
            depth = self.target.targetextra_set.get(key="Depth (mmag)").float_value
            plt.axhline(y=np.power(10, -depth / 1000 / 2.5), color=predicted_color)
        except TargetExtra.DoesNotExist:
            pass

        try:
            # draw predicted ingress, mid, egress with 1 sigma errors
            tr: Transit = self.transit
            starts = [
                Time(t).jd for t in [tr.start_earliest(), tr.start, tr.start_latest()]
            ]
            mids = [Time(t).jd for t in [tr.mid_earliest(), tr.mid, tr.mid_latest()]]
            ends = [Time(t).jd for t in [tr.end_earliest(), tr.end, tr.end_latest()]]

            plt.axvline(x=starts[0], color=predicted_color, linestyle="dashed")
            plt.axvline(x=starts[1], color=predicted_color, linestyle="dashed")
            plt.axvline(x=starts[2], color=predicted_color, linestyle="dashed")

            plt.axvline(x=mids[0], color=predicted_color)
            plt.axvline(x=mids[1], color=predicted_color)
            plt.axvline(x=mids[2], color=predicted_color)

            plt.axvline(x=ends[0], color=predicted_color, linestyle="dotted")
            plt.axvline(x=ends[1], color=predicted_color, linestyle="dotted")
            plt.axvline(x=ends[2], color=predicted_color, linestyle="dotted")
        except:
            pass

        ### draw labels etc ###
        plt.title(
            f"Relative normalized {self.best_light_curves_dp.product_id} and fit"
            + " (airmass detrended)"
            if baseline_function is not None
            else ""
        )
        plt.xlabel("t0")
        plt.ylabel("Relative Intensity")
        # add second axis for magnitude
        ax = plt.gca()
        second_y_axis = ax.secondary_yaxis(
            "right",
            functions=(
                lambda x: -2.5 * np.log10(1 / x),
                lambda y: np.power(10, y / 2.5),
            ),
        )
        second_y_axis.set_ylabel("Mag")
        plt.axhline(y=1, color="grey", zorder=-10)

        # plt.tight_layout()
        plt.savefig(file_name, format="jpg", dpi=200)
        plt.close(fig)

    def get_best_fit_params_legend_string(self):
        key_val_list = [
            f"{key}: {val}\n"
            for key, val in self.best_fit_result.params.__dict__.items()
        ]
        label = "".join(key_val_list)
        label_without_last_new_line = label[:-1]
        return label_without_last_new_line

    @staticmethod
    def load_data_from_dataproduct_list(dps: [DataProduct], verbose=True):
        print("Starting data load from dataproduct list")
        start = time.time()
        image_catalogs = []
        files = sorted([dp.data.path for dp in dps])
        print(f"Found {len(files)} files.")
        for i, filename in enumerate(sorted(files), 1):
            if verbose and i % 100 == 0:
                print("(%d/%d) Loading %s..." % (i, len(files), filename))

            cat = pd.read_csv(filename)
            image_catalogs.append(cat)
        print("Load took %.2fs" % (time.time() - start,))
        return image_catalogs

    @staticmethod
    def load_data_from_directory_of_csv_catalogs(data_directory, verbose=False) -> []:
        print("Starting data load from directory of csv catalogs")
        start = time.time()
        image_catalogs = []
        files = sorted(glob.glob(os.path.join(data_directory, "*.csv")))
        print(f"Found {len(files)} files.")
        for i, filename in enumerate(sorted(files), 1):
            if verbose and i % 100 == 0:
                print("(%d/%d) Loading %s..." % (i, len(files), filename))

            cat = pd.read_csv(filename)
            image_catalogs.append(cat)
        print("Load took %.2fs" % (time.time() - start,))
        return image_catalogs

    @staticmethod
    def load_data_from_directory_of_compressed_fits(data_directory, verbose=False):
        print("Starting data load")
        # load all catalogs
        start = time.time()
        image_catalogs = []
        files = sorted(glob.glob(os.path.join(data_directory, "*.fits.gz")))
        for i, filename in enumerate(sorted(files), 1):
            # load data
            if verbose and i % 50 == 0:
                print("(%d/%d) Loading %s..." % (i, len(files), filename))

            if i == 100:
                one_image = fits.open(filename)[0].data

            hdr = fits.getheader(filename, "SCI")
            cat = Table(fits.getdata(filename, "CAT")).to_pandas()

            # add date-obs
            cat["time"] = float(Time(hdr["DATE-OBS"]).jd)

            # append
            image_catalogs.append(cat)
        print("Load took %.2fs" % (time.time() - start,))
        return image_catalogs, one_image


class TransitPhotometryCatalogGroup:
    def __init__(self, data_product_group: DataProductGroup):
        self.data_product_group = data_product_group

        self.data_products = data_product_group.dataproduct_set.all()
        self.check_data_products_validity()

        self.first_data_product = self.data_products[0]
        self.observation_record = self.first_data_product.observation_record
        self.target: Target = self.first_data_product.target
        self.target_coord = SkyCoord(self.target.ra * u.deg, self.target.dec * u.deg)

        self.transit_name = data_product_group.name
        self.light_curve_name = f"{self.transit_name}_light_curve"

    def check_data_products_validity(self):
        if len(self.data_products) == 0:
            raise ValueError("DataProductGroup contains no dataproducts.")

        for dp in self.data_products:
            try:
                path = dp.data.path
                if path is None or path == "":
                    raise Exception()
            except:
                raise ValueError(
                    f"Dataproduct {dp} does not have well defined DataProduct.data.path"
                )

        self.check_all_dataproducts_are_photometry_catalogs(self.data_products)

    def check_all_dataproducts_are_photometry_catalogs(self, dps):
        for dp in dps:
            if dp.data_product_type != "image_photometry_catalog":
                raise ValueError(
                    f"DataGroup contains none 'image_photometry_catalog' DataProducts (due to {dp})."
                )

    def create_transit_all_lightcurves_dataproduct(self) -> DataProduct:
        """Processes the data products in the data group. Creates
        - one of type "transit_all_light_curves" which contains all potential reference star lightcurves that fulfill
            some basic quality criteria (columns are numbers 0, 1, 2...) and a column "target" for the target star flux.

        :raises ValueError if data_product_group contains no DataProducts or data_product_types
        other than "photometry_catalog"s.
        """

        print(
            f"Transit processing {len(self.data_products)} data products: {self.data_products}"
        )

        return self.extract_and_save_transit_all_light_curves()

    def extract_and_save_transit_all_light_curves(self):

        self.all_light_curves_df = self.extract_all_lightcurves_df()

        return self.save_all_lightcurves_dataproduct_and_file(self.all_light_curves_df)

    def extract_all_lightcurves_df(self):
        image_catalogs: [] = self.load_data_from_dataproduct_list(self.data_products)

        lce = LightCurvesExtractor(image_catalogs, self.target_coord)
        all_light_curves_df = lce.get_target_and_ref_stars_light_curves_df()

        return all_light_curves_df

    @staticmethod
    def load_data_from_dataproduct_list(dps: [DataProduct], verbose=True):
        print("Starting data load from dataproduct list")
        start = time.time()
        image_catalogs = []
        files = sorted([dp.data.path for dp in dps])
        print(f"Found {len(files)} files.")
        for i, filename in enumerate(sorted(files), 1):
            if verbose and i % 100 == 0:
                print("(%d/%d) Loading %s..." % (i, len(files), filename))

            cat = pd.read_csv(filename)
            image_catalogs.append(cat)
        print("Load took %.2fs" % (time.time() - start,))
        return image_catalogs

    def save_all_lightcurves_dataproduct_and_file(
        self, all_light_curves_df
    ) -> DataProduct:
        product_id = self.light_curve_name + "_all"
        dp = DataProduct.objects.create(
            product_id=product_id,
            target=self.target,
            observation_record=self.observation_record,
            data_product_type="transit_all_light_curves",
        )
        dfile = ContentFile(all_light_curves_df.to_csv())
        dp.data.save(
            product_id + ".csv",
            dfile,
        )
        dp.save()
        return dp
