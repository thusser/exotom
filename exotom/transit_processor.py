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

from exotom.photometry import LightCurveExtractor

MAX_SEPARATION_TO_CATALOG_IN_DEG = 5 / 3600


class TransitProcessor:
    def process_transit_dataproductgroup(self, data_product_group: DataProductGroup):
        """Processes the data products in the data group

        :raises ValueError if data_product_group contains no DataProducts or DataProducts
        other than "photometry_catalog"s.
        """
        dps: [DataProduct] = data_product_group.dataproduct_set.all()

        if len(dps) == 0:
            raise ValueError("DataProductGroup contains no dataproducts.")
        self.check_all_dataproducts_are_photometry_catalogs(dps)

        print(f"Transit processing {len(dps)} data products: {dps}")

        first_dp = dps[0]

        data_directory = os.path.dirname(first_dp.data.path)
        target_coord = SkyCoord(first_dp.target.ra * u.deg, first_dp.target.dec * u.deg)

        image_catalogs: [] = self.load_data_from_directory_of_csv_catalogs(
            data_directory
        )
        lce = LightCurveExtractor(image_catalogs, target_coord)
        light_curve_df: pd.DataFrame = lce.get_best_relative_light_curve_dataframe()

        light_curve_name: str = (
            f"{first_dp.target.name} transit #{first_dp.observation_record.parameters_as_dict['transit']}"
            f"_light_curve"
        )

        light_curve_dp: DataProduct = self.save_light_curve_dataproduct_and_file(
            first_dp, light_curve_df, light_curve_name
        )
        self.create_light_curve_thumbnail(light_curve_df, light_curve_dp)

        return light_curve_dp

    def check_all_dataproducts_are_photometry_catalogs(self, dps):
        for dp in dps:
            if dp.data_product_type != "photometry_catalog":
                raise ValueError(
                    f"DataGroup contains none 'photometry_catalog' DataProducts (due to {dp})."
                )

    def save_light_curve_dataproduct_and_file(
        self, first_dp, light_curve_df, light_curve_name
    ):
        light_curve_dp = DataProduct.objects.create(
            product_id=light_curve_name,
            target=first_dp.target,
            observation_record=first_dp.observation_record,
            data_product_type="transit_light_curve",
        )
        dfile = ContentFile(light_curve_df.to_csv())
        light_curve_dp.data.save(
            light_curve_name + ".csv",
            dfile,
        )
        light_curve_dp.save()
        return light_curve_dp

    @staticmethod
    def load_data_from_directory_of_csv_catalogs(data_directory, verbose=False) -> []:
        print("Starting data load from directory of csv catalogs")
        start = time.time()
        image_catalogs = []
        files = sorted(glob.glob(os.path.join(data_directory, "*.csv")))
        print(f"Found {len(files)} files.")
        for i, filename in enumerate(sorted(files), 1):
            if verbose or i % 100 == 0:
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
            if verbose or i % 50 == 0:
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
