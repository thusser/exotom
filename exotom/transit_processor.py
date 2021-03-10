import glob, os, tempfile, time

import pandas as pd
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

from exotom.photometry import TransitLightCurveExtractor


class TransitProcessor:
    def process_transit_dataproductgroup(self, data_product_group: DataProductGroup):
        """Processes the data products in the data group. Creates one DataProduct of type "transit_light_curve"
        which is a csv file containing the reference star light curves in one column each and one column
        for the target light curve ("target") and one for the target relativ light curve ("target_rel").

        :raises ValueError if data_product_group contains no DataProducts or data_product_types
        other than "photometry_catalog"s.
        """
        transit_name = data_product_group.name
        dps: [DataProduct] = data_product_group.dataproduct_set.all()

        if len(dps) == 0:
            raise ValueError("DataProductGroup contains no dataproducts.")
        self.check_all_dataproducts_are_photometry_catalogs(dps)

        print(f"Transit processing {len(dps)} data products: {dps}")

        first_dp = dps[0]

        light_curve_name = f"{transit_name}_light_curve"
        target: Target = first_dp.target
        target_coord = SkyCoord(target.ra * u.deg, target.dec * u.deg)

        image_catalogs: [] = self.load_data_from_dataproduct_list(dps)

        transit_lc_extractor = TransitLightCurveExtractor(image_catalogs, target_coord)

        all_light_curves_df = transit_lc_extractor.get_all_light_curves_dataframe(
            flux_column_name="flux"
        )
        all_light_curves_dp = self.save_dataframe_as_dataproduct_and_csv_file(
            all_light_curves_df,
            product_id=light_curve_name + "_all",
            target=target,
            observation_record=first_dp.observation_record,
            data_product_type="transit_all_light_curves",
        )

        best_light_curve_df = (
            transit_lc_extractor.get_best_relative_transit_light_curve_dataframe()
        )
        best_light_curves_dp = self.save_dataframe_as_dataproduct_and_csv_file(
            all_light_curves_df,
            product_id=light_curve_name + "_best",
            target=target,
            observation_record=first_dp.observation_record,
            data_product_type="transit_best_light_curves",
        )

        self.create_light_curve_thumbnail(best_light_curve_df, best_light_curves_dp)

        return all_light_curves_dp, best_light_curves_dp

    def check_all_dataproducts_are_photometry_catalogs(self, dps):
        for dp in dps:
            if dp.data_product_type != "image_photometry_catalog":
                raise ValueError(
                    f"DataGroup contains none 'image_photometry_catalog' DataProducts (due to {dp})."
                )

    def save_dataframe_as_dataproduct_and_csv_file(
        self, df, product_id, target, observation_record, data_product_type
    ) -> DataProduct:
        dp = DataProduct.objects.create(
            product_id=product_id,
            target=target,
            observation_record=observation_record,
            data_product_type=data_product_type,
        )
        dfile = ContentFile(df.to_csv())
        dp.data.save(
            product_id + ".csv",
            dfile,
        )
        dp.save()
        return dp

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

    def create_light_curve_thumbnail(
        self, light_curve_df: pd.DataFrame, light_curve_dp: DataProduct
    ):
        tmpfile = tempfile.NamedTemporaryFile()

        plt.figure()
        plt.title(f"Relative Normalized {light_curve_dp.product_id}")
        plt.scatter(
            light_curve_df.index,
            light_curve_df["target_rel"] / light_curve_df["target_rel"].mean(),
            marker="x",
            linewidth=1,
        )
        plt.savefig(tmpfile.name, format="jpg")

        if tmpfile:
            dp, _ = DataProduct.objects.get_or_create(
                product_id=f"{light_curve_dp.product_id}_jpeg",
                target=light_curve_dp.target,
                observation_record=light_curve_dp.observation_record,
                data_product_type="image_file",
            )
            outfile_name = os.path.basename(light_curve_dp.data.file.name)
            filename = os.path.splitext(outfile_name)[0] + ".jpg"
            with open(tmpfile.name, "rb") as f:
                dp.data.save(filename, File(f), save=True)
                dp.save()
            tmpfile.close()

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
