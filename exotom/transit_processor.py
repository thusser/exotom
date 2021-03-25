import glob, os, tempfile, time

import batman
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.io import fits
from astropy.table import Table
from astropy.time import Time

from django.core.files import File
from django.core.files.base import ContentFile
from tom_dataproducts.models import DataProductGroup, DataProduct
from tom_targets.models import Target

from exotom.models import Transit
from exotom.photometry import TransitLightCurveExtractor
from exotom.tess_transit_fit import FitResult


class TransitProcessor:
    def __init__(self, data_product_group: DataProductGroup):
        self.data_product_group = data_product_group

        self.data_products = data_product_group.dataproduct_set.all()
        self.check_data_products_validity()

        self.first_data_product = self.data_products[0]
        self.observation_record = self.first_data_product.observation_record
        self.target: Target = self.first_data_product.target

        # this try-except is needed because in the beginning "transit_id" was not written to the parameters dict
        try:
            self.transit: Transit = Transit.objects.get(
                id=self.observation_record.parameters["transit_id"]
            )
        except:
            self.transit = None

        self.transit_name = data_product_group.name
        self.light_curve_name = f"{self.transit_name}_light_curve"

        # objects that get created later
        self.best_fit_result = None
        self.all_light_curves_df = None
        self.best_light_curves_df = None
        self.best_light_curves_dp = None

    def check_data_products_validity(self):
        if len(self.data_products) == 0:
            raise ValueError("DataProductGroup contains no dataproducts.")
        self.check_all_dataproducts_are_photometry_catalogs(self.data_products)

    def check_all_dataproducts_are_photometry_catalogs(self, dps):
        for dp in dps:
            if dp.data_product_type != "image_photometry_catalog":
                raise ValueError(
                    f"DataGroup contains none 'image_photometry_catalog' DataProducts (due to {dp})."
                )

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
            f"Transit processing {len(self.data_products)} data products: {self.data_products}"
        )

        self.extract_and_save_lightcurves()

        self.create_best_light_curve_and_fit_image()

    def extract_and_save_lightcurves(self):
        best_fit_result: FitResult
        (
            all_light_curves_df,
            best_light_curve_df,
            best_fit_result,
        ) = self.get_all_and_best_lightcurves()

        self.best_fit_result = best_fit_result
        self.all_light_curves_df = all_light_curves_df
        self.best_light_curves_df = best_light_curve_df

        self.save_lightcurves_and_fit_report_as_dataproducts(
            all_light_curves_df, best_light_curve_df, best_fit_result
        )

    def get_all_and_best_lightcurves(self):
        target_coord = SkyCoord(self.target.ra * u.deg, self.target.dec * u.deg)

        image_catalogs: [] = self.load_data_from_dataproduct_list(self.data_products)
        transit_lc_extractor = TransitLightCurveExtractor(
            image_catalogs, target_coord, self.transit
        )

        all_light_curves_df = transit_lc_extractor.get_all_light_curves_dataframe(
            flux_column_name="flux"
        )
        (
            best_light_curve_df,
            best_fit_result,
        ) = transit_lc_extractor.get_best_relative_transit_light_curve_dataframe()

        return all_light_curves_df, best_light_curve_df, best_fit_result

    def save_lightcurves_and_fit_report_as_dataproducts(
        self, all_light_curves_df, best_light_curve_df, best_fit_result
    ):
        self.save_dataframe_as_dataproduct_and_csv_file(
            all_light_curves_df,
            product_id=self.light_curve_name + "_all",
            data_product_type="transit_all_light_curves",
        )
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

        plt.figure(figsize=(12, 9))

        plt.title(f"Relative normalized {self.best_light_curves_dp.product_id} and fit")
        plt.scatter(
            times,
            self.best_light_curves_df["target_rel"]
            / self.best_light_curves_df["target_rel"].mean(),
            marker="x",
            linewidth=1,
            color="blue",
        )

        if self.best_fit_result is not None:
            fitted_model = batman.TransitModel(self.best_fit_result.params, times)
            model_flux = (
                fitted_model.light_curve(self.best_fit_result.params)
                * self.best_fit_result.constant_offset
            )
            label = self.get_best_fit_params_legend_string()
            plt.plot(times, model_flux, color="red", label=label)
            plt.legend()

        plt.tight_layout()
        plt.savefig(tmpfile.name, format="jpg", dpi=200)

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
